"""
Padronizacao visual dos graficos (seaborn): estilo sobrio, sem titulos
grandes/verbosos, e utilitarios de salvamento com registro de descricao
para a pasta de resultados.
"""
import json
from pathlib import Path

import matplotlib.pyplot as plt
import seaborn as sns


def aplicar_estilo_padrao() -> None:
    """
    Aplica o estilo seaborn padrao do projeto (fundo claro, sem grade
    pesada, paleta neutra) a todas as figuras seguintes.

    Entradas:
        nenhuma.
    Saida:
        nenhuma (altera o estado global do matplotlib/seaborn).
    """
    sns.set_theme(style="whitegrid", context="talk", font_scale=0.75)
    plt.rcParams["axes.titlesize"] = 11
    plt.rcParams["axes.titleweight"] = "normal"
    plt.rcParams["figure.dpi"] = 140
    plt.rcParams["savefig.dpi"] = 160
    plt.rcParams["savefig.bbox"] = "tight"


def salvar_figura(fig: plt.Figure, caminho_arquivo: Path, descricao: str) -> Path:
    """
    Salva a figura em disco e registra uma legenda/descricao curta em um
    arquivo de indice (descricoes.json) na mesma pasta, para compor o
    relatorio de resultados.

    Entradas:
        fig: figura matplotlib/seaborn a salvar.
        caminho_arquivo: caminho completo do arquivo de imagem (.png).
        descricao: texto curto descrevendo o que a figura mostra.
    Saida:
        o proprio caminho_arquivo (Path), apos salvar.
    """
    caminho_arquivo = Path(caminho_arquivo)
    caminho_arquivo.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(caminho_arquivo)
    plt.close(fig)
    registrar_descricao_imagem(caminho_arquivo, descricao)
    return caminho_arquivo


def plotar_estimado_e_erro_por_carregamento(tabela, pasta_saida: Path, prefixo: str, descricao_metodo: str) -> None:
    """
    Gera duas figuras a partir de uma varredura de carregamento (uma linha
    por fator_carregamento, colorida em escala viridis): distancia
    estimada x real, e erro (estimado - real) x real.

    Entradas:
        tabela: DataFrame com colunas "fator_carregamento", "distancia_real_km",
            "distancia_estimada_km" (uma linha por barra testada em cada fator).
        pasta_saida: pasta de resultados onde salvar as figuras.
        prefixo: prefixo do nome dos arquivos gerados.
        descricao_metodo: nome do metodo/escopo, usado na legenda das figuras
            (registrado em descricoes.json).
    Saida:
        nenhuma (salva os dois .png em pasta_saida).
    """
    aplicar_estilo_padrao()
    fatores = sorted(tabela["fator_carregamento"].unique())
    paleta = sns.color_palette("viridis", n_colors=len(fatores))

    fig, eixo = plt.subplots(figsize=(7, 5.5))
    for cor, fator in zip(paleta, fatores):
        sub = tabela[tabela["fator_carregamento"] == fator].sort_values("distancia_real_km")
        eixo.plot(sub["distancia_real_km"], sub["distancia_estimada_km"], marker="o", color=cor,
                  label=f"load_scale={fator:g}", linewidth=1.2, markersize=4)
    limite = max(tabela["distancia_real_km"].max(), tabela["distancia_estimada_km"].max()) * 1.05
    eixo.plot([0, limite], [0, limite], linestyle="--", color="black", linewidth=1, label="Real (y = x)")
    eixo.set_xlabel("Distância real da falta (km)")
    eixo.set_ylabel("Distância estimada (km)")
    eixo.legend(fontsize=7, ncol=2)
    sns.despine(ax=eixo)
    salvar_figura(
        fig, pasta_saida / f"{prefixo}_estimado_vs_real_carregamento.png",
        f"{descricao_metodo} -- distância estimada vs. real, por fator de carregamento (load_scale)."
    )

    fig, eixo = plt.subplots(figsize=(7, 5.5))
    for cor, fator in zip(paleta, fatores):
        sub = tabela[tabela["fator_carregamento"] == fator].sort_values("distancia_real_km")
        erro = sub["distancia_estimada_km"] - sub["distancia_real_km"]
        eixo.plot(sub["distancia_real_km"], erro, marker="o", color=cor,
                  label=f"load_scale={fator:g}", linewidth=1.2, markersize=4)
    eixo.axhline(0, color="black", linestyle="--", linewidth=1)
    eixo.set_xlabel("Distância real da falta (km)")
    eixo.set_ylabel("Erro (km)")
    eixo.legend(fontsize=7, ncol=2)
    sns.despine(ax=eixo)
    salvar_figura(
        fig, pasta_saida / f"{prefixo}_erro_vs_real_carregamento.png",
        f"{descricao_metodo} -- erro (estimado − real) vs. distância real, por fator de carregamento (load_scale)."
    )


def registrar_descricao_imagem(caminho_arquivo: Path, descricao: str) -> None:
    """
    Adiciona/atualiza a entrada de uma imagem no indice descricoes.json da
    pasta de resultados correspondente.

    Entradas:
        caminho_arquivo: caminho da imagem ja salva.
        descricao: texto curto descrevendo a imagem.
    Saida:
        nenhuma (escreve/atualiza o arquivo descricoes.json em disco).
    """
    caminho_arquivo = Path(caminho_arquivo)
    indice_path = caminho_arquivo.parent / "descricoes.json"
    indice = json.loads(indice_path.read_text(encoding="utf-8")) if indice_path.exists() else {}
    indice[caminho_arquivo.name] = descricao
    indice_path.write_text(json.dumps(indice, indent=2, ensure_ascii=False), encoding="utf-8")
