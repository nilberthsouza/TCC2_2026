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
        partes_bus1 = linhas.bus1.split(".")
        numeros_fase = tuple(int(p) for p in partes_bus1[1:]) if len(partes_bus1) > 1 else ()
        grafo.add_edge(
            b1, b2,
            comprimento_km=float(linhas.length),
            linecode=linhas.linecode,
            fases=int(linhas.phases),
            numeros_fase=numeros_fase,
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


def subarvore_a_partir_de(grafo: nx.Graph, barra_origem: str, barra_raiz: str) -> set:
    """
    Obtem o conjunto de barras do ramal que pende de "barra_raiz" (ela
    propria e tudo que esta eletricamente a jusante dela), removendo a
    aresta que liga barra_raiz ao resto da rede em direcao a origem. Como a
    rede MT reduzida e radial, isso equivale a "cortar" o alimentador logo
    antes de barra_raiz.

    Entradas:
        grafo: grafo eletrico restrito ao componente conexo da origem.
        barra_origem: nome da barra de origem do alimentador completo.
        barra_raiz: barra onde a sub-arvore comeca (ela fica incluida).
    Saida:
        conjunto com os nomes de todas as barras da sub-arvore (incluindo
        barra_raiz); se barra_raiz == barra_origem, retorna todas as barras
        do grafo.
    """
    if barra_raiz == barra_origem:
        return set(grafo.nodes)
    caminho = nx.shortest_path(grafo, barra_origem, barra_raiz, weight="comprimento_km")
    barra_pai = caminho[-2]
    grafo_cortado = grafo.copy()
    grafo_cortado.remove_edge(barra_pai, barra_raiz)
    return nx.node_connected_component(grafo_cortado, barra_raiz)


def barras_trecho_monofasico(grafo: nx.Graph, barra_raiz: str) -> set:
    """
    Obtem as barras de um trecho estritamente monofasico a partir de uma
    barra raiz: percorre so arestas do tipo "linha" com 1 fase (nunca
    atravessa uma transicao para 3 fases) e inclui tambem a barra
    secundaria (BT) de qualquer transformador ligado a uma dessas barras
    (carga do trecho), sem continuar a navegacao a partir dela.

    Entradas:
        grafo: grafo eletrico restrito ao componente conexo da origem.
        barra_raiz: barra MT monofasica onde o trecho comeca.
    Saida:
        conjunto de nomes de barra do trecho monofasico (MT + secundarios
        BT dos transformadores desse trecho), todas na MESMA fase da
        barra_raiz (um ramal monofasico so pode trocar de fase passando
        por um transformador, que nao e atravessado na busca).
    """
    fase_do_trecho = None
    visitados = {barra_raiz}
    pilha = [barra_raiz]
    while pilha:
        atual = pilha.pop()
        for vizinho in grafo.neighbors(atual):
            if vizinho in visitados:
                continue
            dados = grafo.edges[atual, vizinho]
            if dados["tipo"] == "linha" and dados["fases"] == 1:
                fase_aresta = dados["numeros_fase"][0] if dados["numeros_fase"] else None
                if fase_do_trecho is None:
                    fase_do_trecho = fase_aresta
                if fase_aresta != fase_do_trecho:
                    continue
                visitados.add(vizinho)
                pilha.append(vizinho)
            elif dados["tipo"] == "transformador":
                visitados.add(vizinho)
    return visitados


def selecionar_trecho_monofasico_mais_diverso(grafo: nx.Graph, barra_origem: str) -> str:
    """
    Procura, entre todos os trechos estritamente monofasicos do
    alimentador, o que tem mais barras (maior diversidade topologica:
    ramificacoes e transformadores) e devolve sua barra raiz (o ponto onde
    esse trecho se deriva da rede trifasica).

    Entradas:
        grafo: grafo eletrico restrito ao componente conexo da origem.
        barra_origem: nome da barra de origem do alimentador.
    Saida:
        nome da barra raiz do trecho monofasico mais diverso.
    """
    distancias = distancias_desde_origem(grafo, barra_origem)
    g1f = nx.Graph()
    g1f.add_edges_from(
        (a, b) for a, b, d in grafo.edges(data=True) if d["tipo"] == "linha" and d["fases"] == 1
    )
    melhor_raiz, melhor_tamanho = None, -1
    for componente in nx.connected_components(g1f):
        raiz = min(componente, key=lambda n: distancias[n])
        tamanho = len(barras_trecho_monofasico(grafo, raiz))
        if tamanho > melhor_tamanho:
            melhor_raiz, melhor_tamanho = raiz, tamanho
    return melhor_raiz


def selecionar_trecho_trifasico_pequeno(grafo: nx.Graph, barra_origem: str,
                                         tamanho_min: int = 6, tamanho_max: int = 30) -> str:
    """
    Procura, entre as barras de ramificacao da rede trifasica, uma boa
    raiz para um trecho trifasico pequeno com diversidade de carga: dentro
    da faixa de tamanho de sub-arvore informada, escolhe a que tem mais
    transformadores (maior diversidade de carga).

    Entradas:
        grafo: grafo eletrico restrito ao componente conexo da origem.
        barra_origem: nome da barra de origem do alimentador.
        tamanho_min, tamanho_max: faixa aceitavel de numero de barras da
            sub-arvore (grande o suficiente para ter alguma diversidade,
            pequena o suficiente para ser um "trecho pequeno").
    Saida:
        nome da barra raiz escolhida.
    """
    categorias = classificar_barras(grafo, barra_origem)
    candidatas = [b for b, cat in categorias.items() if cat == "ramificacao"]
    melhor_raiz, melhor_trafos = None, -1
    for barra in candidatas:
        subarvore = subarvore_a_partir_de(grafo, barra_origem, barra)
        if not (tamanho_min <= len(subarvore) <= tamanho_max):
            continue
        n_trafos = sum(
            1 for a, b, d in grafo.edges(data=True)
            if d["tipo"] == "transformador" and (a in subarvore or b in subarvore)
        )
        if n_trafos > melhor_trafos:
            melhor_raiz, melhor_trafos = barra, n_trafos
    return melhor_raiz


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
