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
