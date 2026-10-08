"""
Construcao do grafo eletrico do alimentador (barras MT + ligacoes primario-
secundario de transformador) a partir do circuito OpenDSS compilado, e
funcoes de topologia: distancias, folhas, barras de ramificacao e barra
mais distante com carga.
"""
import networkx as nx
import py_dss_interface


def nome_barra_base(barra_com_fases: str) -> str:
    """
    Remove os sufixos de fase/terminal de um nome de barra do OpenDSS.

    Entradas:
        barra_com_fases: nome no formato "barra.1.2.3" ou "barra".
    Saida:
        nome da barra em maiusculas, sem sufixo de fase.
    """
    return barra_com_fases.split(".")[0].upper()


def obter_barra_origem(dss: py_dss_interface.DSS) -> str:
    """
    Identifica a barra de origem (slack) do circuito, a partir da fonte de
    tensao (Vsource) criada pelo comando "New Circuit...".

    Entradas:
        dss: instancia do motor OpenDSS com o alimentador compilado.
    Saida:
        nome da barra de origem, sem sufixo de fase.
    """
    vsources = dss.vsources
    dss.circuit.set_active_element(f"Vsource.{vsources.names[0]}")
    return nome_barra_base(dss.cktelement.bus_names[0])


def construir_grafo_eletrico(dss: py_dss_interface.DSS) -> nx.Graph:
    """
    Monta o grafo eletrico do alimentador: um no por barra MT/BT e uma
    aresta por trecho de linha MT (peso = comprimento em km) ou por
    transformador (peso 0, liga barra primaria a barra secundaria).

    Entradas:
        dss: instancia do motor OpenDSS com o alimentador compilado.
    Saida:
        networkx.Graph nao direcionado, com atributos de aresta:
            comprimento_km, linecode, fases, tipo ("linha"/"transformador"),
            nome_elemento, kva (so para transformador).
    """
    grafo = nx.Graph()
    linhas = dss.lines
    for nome in linhas.names:
        linhas.name = nome
        b1 = nome_barra_base(linhas.bus1)
        b2 = nome_barra_base(linhas.bus2)
        grafo.add_edge(
            b1, b2,
            comprimento_km=float(linhas.length),
            linecode=linhas.linecode,
            fases=int(linhas.phases),
            tipo="linha",
            nome_elemento=nome,
        )
    trafos = dss.transformers
    for nome in trafos.names:
        dss.circuit.set_active_element(f"Transformer.{nome}")
        buses = dss.cktelement.bus_names
        b1 = nome_barra_base(buses[0])
        b2 = nome_barra_base(buses[1])
        trafos.name = nome
        grafo.add_edge(
            b1, b2,
            comprimento_km=0.0,
            linecode=None,
            fases=None,
            tipo="transformador",
            nome_elemento=nome,
            kva=float(trafos.kva),
        )
    return grafo


def componente_conexa_da_origem(grafo: nx.Graph, barra_origem: str) -> nx.Graph:
    """
    Restringe o grafo ao componente conexo que contem a barra de origem,
    descartando ilhas desconectadas da fonte (sem elemento com potencia).

    Entradas:
        grafo: grafo eletrico completo (ver construir_grafo_eletrico).
        barra_origem: nome da barra de origem.
    Saida:
        subgrafo (copia) contendo apenas as barras alcancaveis a partir da
        barra de origem.
    """
    nos_alcancaveis = nx.node_connected_component(grafo, barra_origem)
    return grafo.subgraph(nos_alcancaveis).copy()


def distancias_desde_origem(grafo: nx.Graph, barra_origem: str) -> dict:
    """
    Calcula a distancia (km) de cada barra do grafo at a barra de origem,
    pelo caminho mais curto (unico, pois a rede MT reduzida e radial).

    Entradas:
        grafo: grafo eletrico (idealmente ja restrito ao componente conexo
            da origem, ver componente_conexa_da_origem).
        barra_origem: nome da barra de origem.
    Saida:
        dicionario {nome_da_barra: distancia_km}.
    """
    return nx.single_source_dijkstra_path_length(grafo, barra_origem, weight="comprimento_km")


def distancia_tronco(grafo: nx.Graph, barra_origem: str) -> tuple[str, float]:
    """
    Determina o "tronco" do alimentador: o caminho mais longo (em km) entre
    a barra de origem e qualquer folha da rede.

    Entradas:
        grafo: grafo eletrico restrito ao componente conexo da origem.
        barra_origem: nome da barra de origem.
    Saida:
        tupla (barra_mais_distante, distancia_km).
    """
    distancias = distancias_desde_origem(grafo, barra_origem)
    barra_mais_distante = max(distancias, key=distancias.get)
    return barra_mais_distante, distancias[barra_mais_distante]


def classificar_barras(grafo: nx.Graph, barra_origem: str) -> dict:
    """
    Classifica cada barra do grafo por grau topologico: origem, ramificacao
    (grau >= 3), folha secundaria de transformador (grau == 1, alcancada
    por uma aresta tipo "transformador"), folha MT (grau == 1, fim de ramal
    MT sem transformador) ou passagem (grau == 2).

    Entradas:
        grafo: grafo eletrico restrito ao componente conexo da origem.
        barra_origem: nome da barra de origem.
    Saida:
        dicionario {nome_da_barra: categoria}, categoria em
        {"origem", "ramificacao", "folha_secundario_trafo", "folha_mt", "passagem"}.
    """
    categorias = {}
    for barra in grafo.nodes:
        grau = grafo.degree(barra)
        if barra == barra_origem:
            categorias[barra] = "origem"
        elif grau >= 3:
            categorias[barra] = "ramificacao"
        elif grau == 1:
            (vizinho,) = grafo.neighbors(barra)
            tipo_aresta = grafo.edges[barra, vizinho]["tipo"]
            categorias[barra] = "folha_secundario_trafo" if tipo_aresta == "transformador" else "folha_mt"
        else:
            categorias[barra] = "passagem"
    return categorias


def barras_de_media_tensao(grafo: nx.Graph) -> set:
    """
    Identifica as barras de media tensao: todas as barras que participam de
    pelo menos uma aresta do tipo "linha" (segmento/chave MT). As barras que
    so aparecem como extremidade secundaria de transformador sao de baixa
    tensao e ficam de fora.

    Entradas:
        grafo: grafo eletrico (completo ou restrito ao componente conexo).
    Saida:
        conjunto com os nomes das barras MT.
    """
    barras_mt = set()
    for b1, b2, dados in grafo.edges(data=True):
        if dados["tipo"] == "linha":
            barras_mt.add(b1)
            barras_mt.add(b2)
    return barras_mt


def comprimento_total_linhas_km(grafo: nx.Graph) -> float:
    """
    Soma o comprimento de todos os trechos de linha MT do grafo (exclui
    ligacoes de transformador, que tem peso 0).

    Entradas:
        grafo: grafo eletrico (completo ou restrito ao componente conexo).
    Saida:
        comprimento total em km.
    """
    return sum(
        dados["comprimento_km"] for _, _, dados in grafo.edges(data=True)
        if dados["tipo"] == "linha"
    )


def caminho_entre_barras(grafo: nx.Graph, barra_a: str, barra_b: str) -> list:
    """
    Obtem a sequencia de barras do caminho mais curto entre duas barras.

    Entradas:
        grafo: grafo eletrico.
        barra_a, barra_b: nomes das barras de origem e destino do caminho.
    Saida:
        lista de nomes de barras, de barra_a a barra_b (inclusive).
    """
    return nx.shortest_path(grafo, barra_a, barra_b, weight="comprimento_km")
