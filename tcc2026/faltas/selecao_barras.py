"""
Selecao das barras representativas para a tabela de 3 casos (ver
tcc2026.faltas.tabela_barras): primeira barra com carga, barra com carga
mais distante da origem e folha sem carga conectada.
"""
import py_dss_interface

from tcc2026.nucleo import grafo_alimentador as ga


def barras_mt_com_transformador(grafo, barras_mt: set) -> set:
    """
    Identifica as barras MT que sao o lado primario de pelo menos um
    transformador (ou seja, alimentam carga BT a jusante).

    Entradas:
        grafo: grafo eletrico do alimentador (ver grafo_alimentador).
        barras_mt: conjunto de barras MT (ver grafo_alimentador.barras_de_media_tensao).
    Saida:
        conjunto de nomes de barras MT com transformador.
    """
    resultado = set()
    for b1, b2, dados in grafo.edges(data=True):
        if dados["tipo"] == "transformador":
            if b1 in barras_mt:
                resultado.add(b1)
            if b2 in barras_mt:
                resultado.add(b2)
    return resultado


def barras_mt_com_carga_mt_direta(dss: py_dss_interface.DSS, barras_mt: set) -> set:
    """
    Identifica as barras MT que tem um objeto Load de media tensao
    conectado diretamente a elas (cargas MT, poucos consumidores de grande
    porte ligados direto na rede primaria).

    Entradas:
        dss: instancia do motor OpenDSS com o alimentador compilado.
        barras_mt: conjunto de barras MT.
    Saida:
        conjunto de nomes de barras MT com carga MT direta.
    """
    resultado = set()
    cargas = dss.loads
    for nome in cargas.names:
        dss.circuit.set_active_element(f"Load.{nome}")
        barra = ga.nome_barra_base(dss.cktelement.bus_names[0])
        if barra in barras_mt:
            resultado.add(barra)
    return resultado


def barras_com_carga(dss: py_dss_interface.DSS, grafo, barras_mt: set) -> set:
    """
    Uniao das barras MT que efetivamente alimentam alguma carga: por
    transformador (carga BT a jusante) ou por carga MT direta.

    Entradas:
        dss: instancia do motor OpenDSS com o alimentador compilado.
        grafo: grafo eletrico do alimentador.
        barras_mt: conjunto de barras MT.
    Saida:
        conjunto de nomes de barras MT com carga (direta ou via transformador).
    """
    return barras_mt_com_transformador(grafo, barras_mt) | barras_mt_com_carga_mt_direta(dss, barras_mt)


def selecionar_barra_primeira_carga(barras_com_carga: set, distancias: dict) -> str:
    """
    Seleciona a primeira barra com carga conectada, ou seja, a barra com
    carga mais proxima da origem do alimentador.

    Entradas:
        barras_com_carga: conjunto de barras MT com carga (ver barras_com_carga).
        distancias: dicionario {barra: distancia_km} desde a origem (ver
            grafo_alimentador.distancias_desde_origem).
    Saida:
        nome da barra selecionada.
    """
    candidatas = {b: distancias[b] for b in barras_com_carga if b in distancias}
    return min(candidatas, key=candidatas.get)


def selecionar_barra_carga_mais_distante(barras_com_carga: set, distancias: dict) -> str:
    """
    Seleciona a barra com carga conectada mais distante da origem do
    alimentador.

    Entradas:
        barras_com_carga: conjunto de barras MT com carga.
        distancias: dicionario {barra: distancia_km} desde a origem.
    Saida:
        nome da barra selecionada.
    """
    candidatas = {b: distancias[b] for b in barras_com_carga if b in distancias}
    return max(candidatas, key=candidatas.get)


def selecionar_folha_sem_carga(categorias: dict, barras_com_carga: set, distancias: dict) -> str:
    """
    Seleciona uma barra folha MT (fim de ramal, sem transformador) que nao
    tenha nenhuma carga conectada. Entre as candidatas, escolhe a mais
    distante da origem (ramal mais longo, cenario mais relevante para
    avaliar tempo de propagacao da falta ate o rele).

    Entradas:
        categorias: dicionario {barra: categoria} (ver grafo_alimentador.classificar_barras).
        barras_com_carga: conjunto de barras MT com carga.
        distancias: dicionario {barra: distancia_km} desde a origem.
    Saida:
        nome da barra folha selecionada.
    """
    candidatas = {
        b: distancias[b] for b, cat in categorias.items()
        if cat == "folha_mt" and b not in barras_com_carga and b in distancias
    }
    if not candidatas:
        raise RuntimeError("Nenhuma folha MT sem carga encontrada no alimentador.")
    return max(candidatas, key=candidatas.get)


def encontrar_ultima_carga_no_ramal(grafo, origem: str, barra_alvo: str, barras_com_carga: set) -> str | None:
    """
    Percorre o caminho da origem ate a barra_alvo e identifica a ultima
    barra com carga antes da barra_alvo (a carga mais proxima do fim do
    ramal), usada no circuito equivalente do caso 3 (folha sem carga).

    Entradas:
        grafo: grafo eletrico do alimentador.
        origem: nome da barra de origem.
        barra_alvo: nome da barra final do ramal (ex.: a folha sem carga).
        barras_com_carga: conjunto de barras MT com carga.
    Saida:
        nome da ultima barra com carga no caminho, ou None se nenhuma
        barra do caminho tiver carga.
    """
    caminho = ga.caminho_entre_barras(grafo, origem, barra_alvo)
    for barra in reversed(caminho[:-1]):
        if barra in barras_com_carga:
            return barra
    return None
