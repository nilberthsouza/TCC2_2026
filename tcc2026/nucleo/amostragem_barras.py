"""
Amostragem de barras do alimentador para os estudos de validacao dos
metodos de localizacao de falta (Takagi, reatancia compensada e
corrigida): barras de ramificacao, barras folha e barras aleatorias
(semente fixa).
"""
import random


def _espacar_uniformemente(lista_ordenada: list, n: int) -> list:
    """
    Seleciona ate n itens de uma lista ja ordenada, igualmente espacados
    (sempre incluindo o primeiro e o ultimo).

    Entradas:
        lista_ordenada: lista de itens, ja ordenada pelo criterio de interesse.
        n: quantidade maxima de itens a selecionar.
    Saida:
        lista com ate n itens de lista_ordenada, igualmente espacados.
    """
    if len(lista_ordenada) <= n:
        return list(lista_ordenada)
    indices = sorted({round(i * (len(lista_ordenada) - 1) / (n - 1)) for i in range(n)})
    return [lista_ordenada[i] for i in indices]


def selecionar_barras_ramificacao(categorias: dict, distancias: dict, quantidade: int = 20) -> list:
    """
    Seleciona ate `quantidade` barras de ramificacao (grau >= 3),
    distribuidas uniformemente pela distancia ate a origem.

    Entradas:
        categorias: dicionario {barra: categoria} (ver grafo_alimentador.classificar_barras).
        distancias: dicionario {barra: distancia_km} desde a origem.
        quantidade: numero maximo de barras a selecionar para os graficos.
    Saida:
        lista de nomes de barra.
    """
    candidatas = sorted((b for b, c in categorias.items() if c == "ramificacao"), key=distancias.get)
    return _espacar_uniformemente(candidatas, quantidade)


def selecionar_barras_folha(categorias: dict, distancias: dict, quantidade: int = 20) -> list:
    """
    Seleciona ate `quantidade` barras folha (fim de ramal MT ou secundario
    de transformador, grau == 1), distribuidas uniformemente pela
    distancia ate a origem.

    Entradas:
        categorias: dicionario {barra: categoria}.
        distancias: dicionario {barra: distancia_km} desde a origem.
        quantidade: numero maximo de barras a selecionar para os graficos.
    Saida:
        lista de nomes de barra.
    """
    candidatas = sorted(
        (b for b, c in categorias.items() if c in ("folha_mt", "folha_secundario_trafo")), key=distancias.get)
    return _espacar_uniformemente(candidatas, quantidade)


def selecionar_barras_aleatorias(barras_mt: set, origem: str, quantidade: int = 20, semente: int = 42) -> list:
    """
    Seleciona `quantidade` barras MT aleatorias (semente fixa, resultado
    reprodutivel), excluindo a barra de origem.

    Entradas:
        barras_mt: conjunto de barras MT do alimentador.
        origem: nome da barra de origem (excluida da selecao).
        quantidade: numero de barras a sortear.
        semente: semente do gerador aleatorio.
    Saida:
        lista de nomes de barra, em ordem de sorteio.
    """
    candidatas = sorted(b for b in barras_mt if b != origem)
    gerador = random.Random(semente)
    return gerador.sample(candidatas, min(quantidade, len(candidatas)))
