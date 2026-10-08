"""
Geracao de tabelas em LaTeX no padrao booktabs (toprule/midrule/bottomrule)
usado no texto do TCC, com numeros no formato brasileiro (virgula decimal
via "{,}", compativel com o pacote siunitx/booktabs). Cada tabela tambem e
salva em um .txt individual, com um comentario de contexto no topo.
"""
import math
from pathlib import Path

import pandas as pd


def formatar_numero_br(valor, decimais: int = 2) -> str:
    """
    Formata um numero no padrao brasileiro para LaTeX (virgula decimal
    protegida por chaves, ex.: 3.567 -> "3{,}57"). Valores nao numericos
    (None, NaN, texto) sao repassados como "---" ou como o proprio texto.

    Entradas:
        valor: numero a formatar (ou texto/None/NaN).
        decimais: quantidade de casas decimais.
    Saida:
        string pronta para uso dentro de uma celula de tabela LaTeX.
    """
    if valor is None:
        return "---"
    if isinstance(valor, str):
        return valor
    if isinstance(valor, float) and math.isnan(valor):
        return "---"
    texto = f"{valor:.{decimais}f}"
    return texto.replace(".", "{,}")


def gerar_tabela_latex(tabela: pd.DataFrame, legenda: str, rotulo: str,
                        decimais: dict | int = 2, alinhamento: str | None = None) -> str:
    """
    Gera o codigo LaTeX de uma tabela no estilo booktabs (toprule/midrule/
    bottomrule), uma coluna por campo do DataFrame.

    Entradas:
        tabela: DataFrame com os dados (colunas = cabecalho da tabela).
        legenda: texto da \\caption.
        rotulo: rotulo da \\label (sem o prefixo "tab:", que e adicionado
            automaticamente).
        decimais: numero de casas decimais para colunas numericas; pode ser
            um unico inteiro (aplicado a todas) ou um dict {coluna: casas}.
        alinhamento: string de alinhamento das colunas (ex.: "lccc"); se
            None, usa "c" (centralizado) para todas as colunas.
    Saida:
        string com o bloco LaTeX completo (\\begin{table}...\\end{table}).
    """
    colunas = list(tabela.columns)
    if alinhamento is None:
        alinhamento = "c" * len(colunas)
    if isinstance(decimais, int):
        decimais = {c: decimais for c in colunas}

    linhas_corpo = []
    for _, linha in tabela.iterrows():
        celulas = [formatar_numero_br(linha[c], decimais.get(c, 2)) for c in colunas]
        linhas_corpo.append("    " + " & ".join(celulas) + r" \\")

    cabecalho = "    " + " & ".join(rf"\textbf{{{c}}}" for c in colunas) + r" \\"

    return "\n".join([
        r"\begin{table}[htbp]",
        r"  \centering",
        rf"  \caption{{{legenda}}}",
        rf"  \label{{tab:{rotulo}}}",
        rf"  \begin{{tabular}}{{{alinhamento}}}",
        r"    \toprule",
        cabecalho,
        r"    \midrule",
        *linhas_corpo,
        r"    \bottomrule",
        r"  \end{tabular}",
        r"\end{table}",
    ])


def salvar_tabela_latex(tabela: pd.DataFrame, caminho_txt: Path, legenda: str,
                         rotulo: str, contexto: str, decimais: dict | int = 2,
                         alinhamento: str | None = None) -> Path:
    """
    Gera a tabela LaTeX (ver gerar_tabela_latex) e salva em um arquivo .txt
    individual, com uma linha de comentario "% contexto: ..." no topo
    explicando de onde vem a tabela.

    Entradas:
        tabela: DataFrame com os dados.
        caminho_txt: caminho do arquivo .txt de saida.
        legenda, rotulo, decimais, alinhamento: ver gerar_tabela_latex.
        contexto: descricao curta do contexto/origem da tabela, salva como
            comentario LaTeX (%) na primeira linha do arquivo.
    Saida:
        o proprio caminho_txt (Path), apos salvar.
    """
    caminho_txt = Path(caminho_txt)
    caminho_txt.parent.mkdir(parents=True, exist_ok=True)
    codigo = gerar_tabela_latex(tabela, legenda, rotulo, decimais, alinhamento)
    conteudo = f"% Contexto: {contexto}\n\n{codigo}\n"
    caminho_txt.write_text(conteudo, encoding="utf-8")
    return caminho_txt
