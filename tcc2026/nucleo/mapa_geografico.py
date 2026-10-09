"""
Mapa geografico do alimentador: le as coordenadas (buscoords.csv) e desenha
o circuito (linhas + barras) sobre o plano longitude/latitude, com opcao de
destacar um subconjunto de barras (ex.: um trecho extraido).
"""
import csv
from pathlib import Path

import matplotlib.pyplot as plt

from tcc2026.configuracao import PASTA_ALIMENTADOR_REDUZIDO
from tcc2026.nucleo import graficos


def carregar_coordenadas(pasta_alimentador: Path = PASTA_ALIMENTADOR_REDUZIDO) -> dict:
    """
    Le o arquivo buscoords.csv do alimentador (colunas PAC, long, lat) e
    devolve as coordenadas por barra.

    Entradas:
        pasta_alimentador: pasta com o arquivo buscoords.csv.
    Saida:
        dicionario {barra: (longitude, latitude)}, barra em maiusculas, sem
        sufixo de fase.
    """
    caminho = pasta_alimentador / "buscoords.csv"
    coordenadas = {}
    with open(caminho, encoding="utf-8", errors="replace") as arquivo:
        leitor = csv.reader(arquivo)
        next(leitor, None)
        for linha in leitor:
            if len(linha) >= 3:
                try:
                    coordenadas[linha[0].strip().upper()] = (float(linha[1]), float(linha[2]))
                except ValueError:
                    continue
    return coordenadas


def plotar_mapa_geografico(grafo, coordenadas: dict, caminho_arquivo: Path, descricao: str,
                            barras_destaque: set | None = None,
                            barra_origem: str | None = None) -> Path:
    """
    Desenha o circuito (linhas MT + ligacoes de transformador) sobre o
    plano longitude/latitude, com as barras de um subconjunto opcional
    destacadas em outra cor.

    Entradas:
        grafo: grafo eletrico do alimentador (ver grafo_alimentador.construir_grafo_eletrico).
        coordenadas: dicionario {barra: (longitude, latitude)} (ver carregar_coordenadas).
        caminho_arquivo: caminho do arquivo .png de saida.
        descricao: descricao curta da figura, registrada em descricoes.json.
        barras_destaque: conjunto opcional de barras a destacar (ex.: um
            trecho extraido); barras sem coordenada disponivel sao ignoradas.
        barra_origem: barra de origem do alimentador, desenhada com marcador
            proprio, se informada e tiver coordenada disponivel.
    Saida:
        o proprio caminho_arquivo, apos salvar.
    """
    barras_destaque = barras_destaque or set()
    graficos.aplicar_estilo_padrao()
    fig, eixo = plt.subplots(figsize=(8, 8))

    for b1, b2 in grafo.edges():
        if b1 in coordenadas and b2 in coordenadas:
            (x1, y1), (x2, y2) = coordenadas[b1], coordenadas[b2]
            cor = "#c53030" if (b1 in barras_destaque and b2 in barras_destaque) else "#cbd5e0"
            zorder = 3 if cor == "#c53030" else 1
            eixo.plot([x1, x2], [y1, y2], color=cor, linewidth=1.0, zorder=zorder)

    xs_fundo = [coordenadas[b][0] for b in grafo.nodes() if b in coordenadas and b not in barras_destaque]
    ys_fundo = [coordenadas[b][1] for b in grafo.nodes() if b in coordenadas and b not in barras_destaque]
    eixo.scatter(xs_fundo, ys_fundo, s=6, color="#a0aec0", zorder=2)

    if barras_destaque:
        xs_dest = [coordenadas[b][0] for b in barras_destaque if b in coordenadas]
        ys_dest = [coordenadas[b][1] for b in barras_destaque if b in coordenadas]
        eixo.scatter(xs_dest, ys_dest, s=22, color="#c53030", zorder=4)

    if barra_origem and barra_origem in coordenadas:
        x0, y0 = coordenadas[barra_origem]
        eixo.scatter([x0], [y0], s=90, color="#2b6cb0", marker="s", zorder=5)

    eixo.set_xlabel("Longitude")
    eixo.set_ylabel("Latitude")
    eixo.set_aspect("equal", adjustable="datalim")
    fig.tight_layout()
    return graficos.salvar_figura(fig, caminho_arquivo, descricao)
