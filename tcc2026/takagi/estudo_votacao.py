"""
Secao 8: Algoritmo 3 (consolidacao por votacao multi-folha) aplicado as
300 barras MT do alimentador completo, comparando o metodo de Takagi
compensado com o da reatancia compensada e corrigida -- quantos
candidatos distintos cada metodo deixa, em media, apos o criterio de
validade do Algoritmo 1, e com que taxa de acerto a barra mais votada
coincide com a barra de falta real. Reusa a mesma amostragem (geometria
Cemig aplicada as linhas trifasicas e monofasicas) das Secoes 6a/6b.
"""
import random
from pathlib import Path

import pandas as pd

from tcc2026.nucleo import amostragem_barras as ab, avaliacao_multifolha as amf, latex_utils
from tcc2026.takagi import estudo_takagi as et6a

SEMENTE_ALEATORIA = 42
QUANTIDADE_AMOSTRA_DETALHADA = 6  # por categoria (ramificacao/folha/aleatoria) = 18 linhas na tabela


def preparar_votacao(pasta_saida: Path) -> dict:
    """
    Prepara o alimentador (geometria Cemig), mede as 300 barras MT (mesma
    rotina da Secao 6a) e pre-calcula a impedancia e a lista de barras por
    distancia acumulada de cada uma das 34 folhas candidatas.

    Entradas:
        pasta_saida: pasta de resultados desta secao.
    Saida:
        dicionario com "medidas", "categorias", "impedancias_folhas",
        "caminhos_distancias", "origem".
    """
    preparo = et6a.preparar_amostras_e_medidas(pasta_saida)
    folhas_mt = sorted(b for b, c in preparo["categorias"].items() if c == "folha_mt")
    grafo = preparo["grafo"]
    impedancias_folhas = amf.impedancias_por_folha(grafo, preparo["origem"], folhas_mt)
    caminhos_distancias = amf.caminho_distancias_por_folha(grafo, preparo["origem"], folhas_mt)
    return {
        "medidas": preparo["medidas"], "categorias": preparo["categorias"],
        "impedancias_folhas": impedancias_folhas, "caminhos_distancias": caminhos_distancias,
        "origem": preparo["origem"], "grafo": grafo,
    }


def _avaliar_takagi(falta, z1l, z0l, l_km):
    return amf.avaliar_algoritmo1_caminho_takagi(
        falta["va_pos"], falta["ia_pos"], falta["ia_pre"],
        falta["i0_pos"], falta["i0_pre"], z1l, z0l, l_km)


def _avaliar_reatancia(falta, z1l, z0l, l_km):
    return amf.avaliar_algoritmo1_caminho_reatancia(falta["va_pos"], falta["ia_pos"], falta["i0_pos"], z1l, z0l, l_km)


METODOS = {
    "takagi": ("Takagi compensado", _avaliar_takagi),
    "reatancia": ("Reatância compensada e corrigida", _avaliar_reatancia),
}


def executar_votacao_populacao(preparo: dict) -> dict:
    """
    Aplica a consolidacao por votacao (Algoritmo 3) as 300 barras MT, para
    os dois metodos (Takagi, reatancia compensada e corrigida).

    Entradas:
        preparo: dicionario devolvido por preparar_votacao.
    Saida:
        dicionario {"takagi": DataFrame, "reatancia": DataFrame}, cada um
        no formato de avaliacao_multifolha.avaliar_votacao_populacao.
    """
    resultados = {}
    for chave, (_, avaliar_fn) in METODOS.items():
        resultados[chave] = amf.avaliar_votacao_populacao(
            preparo["medidas"], preparo["impedancias_folhas"], preparo["caminhos_distancias"], avaliar_fn)
    return resultados


def montar_tabela_resumo_global(resultados: dict, pasta_saida: Path) -> pd.DataFrame:
    """
    Monta a tabela-resumo global: para cada metodo, media de candidatos
    distintos apos votacao (de 34 folhas), taxa de "sem solucao", media da
    razao de concordancia do vencedor (votos_vencedor/votos_totais) e taxa
    de acerto da barra consolidada (barra mais votada == barra de falta real).

    Entradas:
        resultados: dicionario devolvido por executar_votacao_populacao.
        pasta_saida: pasta de resultados desta secao.
    Saida:
        DataFrame com uma linha por metodo.
    """
    linhas = []
    for chave, (rotulo, _) in METODOS.items():
        tabela = resultados[chave]
        com_solucao = tabela[~tabela["sem_solucao"]]
        linhas.append({
            "metodo": rotulo,
            "n_folhas": 34,
            "media_candidatos_distintos": com_solucao["n_candidatos_distintos"].mean(),
            "taxa_sem_solucao_pct": 100.0 * tabela["sem_solucao"].mean(),
            "media_concordancia_pct": 100.0 * (com_solucao["votos_vencedor"] / com_solucao["votos_totais"]).mean(),
            "taxa_acerto_pct": 100.0 * tabela["barra_correta_consolidada"].mean(),
        })
    tabela_resumo = pd.DataFrame(linhas)
    tabela_resumo.to_csv(pasta_saida / "votacao_resumo_global.csv", index=False)
    latex_utils.salvar_tabela_latex(
        tabela_resumo.rename(columns={
            "metodo": "Método", "n_folhas": "N folhas",
            "media_candidatos_distintos": "Candidatos distintos (média)",
            "taxa_sem_solucao_pct": "Sem solução (\\%)",
            "media_concordancia_pct": "Concordância do vencedor (\\%)",
            "taxa_acerto_pct": "Acerto da barra (\\%)",
        }),
        pasta_saida / "votacao_resumo_global.txt",
        legenda="Algoritmo 3 (votação multi-folha) nas 300 barras MT: resumo global por método",
        rotulo="votacao_resumo_global",
        contexto="Secao 8 - resumo global da consolidacao por votacao (Algoritmo 3), 300 barras MT, "
                 "34 folhas candidatas por falta.",
        decimais={"N folhas": 0, "Candidatos distintos (média)": 2, "Sem solução (\\%)": 1,
                  "Concordância do vencedor (\\%)": 1, "Acerto da barra (\\%)": 1},
        alinhamento="lcccccc",
    )
    return tabela_resumo


def montar_tabela_comparativa_amostra(resultados: dict, preparo: dict, pasta_saida: Path) -> pd.DataFrame:
    """
    Monta a tabela detalhada lado a lado (Takagi x reatância compensada e
    corrigida) para uma amostra de barras espalhada entre as categorias
    ramificação/folha/aleatória (mesmo estilo da tabela de referência da
    literatura: barra, distância estimada, real, erro, erro~\\%, votos).

    Entradas:
        resultados: dicionario devolvido por executar_votacao_populacao.
        preparo: dicionario devolvido por preparar_votacao.
        pasta_saida: pasta de resultados desta secao.
    Saida:
        DataFrame com uma linha por barra amostrada, colunas de ambos os
        metodos lado a lado.
    """
    categorias = preparo["categorias"]
    distancias = dict(zip(preparo["medidas"]["barra"], preparo["medidas"]["distancia_real_km"]))
    barras_ramificacao = ab.selecionar_barras_ramificacao(categorias, distancias, QUANTIDADE_AMOSTRA_DETALHADA)
    barras_folha = ab.selecionar_barras_folha(categorias, distancias, QUANTIDADE_AMOSTRA_DETALHADA)
    gerador = random.Random(SEMENTE_ALEATORIA)
    barras_aleatorias = gerador.sample(list(preparo["medidas"]["barra"]), QUANTIDADE_AMOSTRA_DETALHADA)

    amostra = []
    for categoria, lista in (("Ramificação", barras_ramificacao), ("Folha", barras_folha),
                              ("Aleatória", barras_aleatorias)):
        for barra in lista:
            amostra.append((categoria, barra))

    tab_takagi = resultados["takagi"].set_index("barra")
    tab_reat = resultados["reatancia"].set_index("barra")

    linhas = []
    for categoria, barra in amostra:
        linha = {"categoria": categoria, "barra": barra, "distancia_real_km": distancias[barra]}
        for chave, tabela in (("takagi", tab_takagi), ("reatancia", tab_reat)):
            r = tabela.loc[barra]
            if r["sem_solucao"]:
                linha[f"d_estimado_{chave}"] = float("nan")
                linha[f"erro_{chave}"] = float("nan")
                linha[f"erro_pct_{chave}"] = float("nan")
                linha[f"votos_{chave}"] = "sem solução"
            else:
                erro = r["erro_km"]
                linha[f"d_estimado_{chave}"] = r["distancia_estimada_km"]
                linha[f"erro_{chave}"] = erro
                linha[f"erro_pct_{chave}"] = 100.0 * erro / distancias[barra] if distancias[barra] > 0 else float("nan")
                linha[f"votos_{chave}"] = f"{int(r['votos_vencedor'])}/{int(r['votos_totais'])}"
        linhas.append(linha)
    tabela_amostra = pd.DataFrame(linhas)
    tabela_amostra.to_csv(pasta_saida / "votacao_amostra_comparativa.csv", index=False)

    def _fmt(v, casas=4):
        return "---" if pd.isna(v) else f"{v:.{casas}f}".replace(".", ",")

    def _fmt_pct(v):
        return "---" if pd.isna(v) else f"{v:+.2f}\\%".replace(".", ",")

    linhas_tex = []
    for _, linha in tabela_amostra.iterrows():
        linhas_tex.append(
            f"    {linha['categoria']} & {linha['barra']} & {_fmt(linha['distancia_real_km'], 3)} & "
            f"{_fmt(linha['d_estimado_takagi'])} & {_fmt_pct(linha['erro_pct_takagi'])} & {linha['votos_takagi']} & "
            f"{_fmt(linha['d_estimado_reatancia'])} & {_fmt_pct(linha['erro_pct_reatancia'])} & "
            f"{linha['votos_reatancia']} \\\\"
        )
    corpo_tabela = "\n".join(linhas_tex)
    texto_tex = (
        "% Contexto: Secao 8 - comparacao lado a lado Takagi x reatancia, consolidacao por votacao, "
        "amostra de barras.\n\n"
        "\\begin{table}[htbp]\n  \\centering\n  \\small\n"
        "  \\caption{Comparação lado a lado entre Takagi compensado e reatância compensada e corrigida, "
        "consolidação por votação (Algoritmo 3), amostra de barras.}\n"
        "  \\label{tab:votacao_amostra}\n  \\resizebox{\\textwidth}{!}{%\n"
        "  \\begin{tabular}{llc ccc ccc}\n    \\toprule\n"
        "    & & & \\multicolumn{3}{c}{\\textbf{Takagi compensado}} & "
        "\\multicolumn{3}{c}{\\textbf{Reatância compensada e corrigida}} \\\\\n"
        "    \\cmidrule(lr){4-6} \\cmidrule(lr){7-9}\n"
        "    \\textbf{Categoria} & \\textbf{Barra} & \\textbf{$d_{real}$ (km)} & "
        "\\textbf{$d_{est}$ (km)} & \\textbf{Erro (\\%)} & \\textbf{Votos} & "
        "\\textbf{$d_{est}$ (km)} & \\textbf{Erro (\\%)} & \\textbf{Votos} \\\\\n    \\midrule\n"
        f"{corpo_tabela}\n    \\bottomrule\n  \\end{{tabular}}\n  }}\n"
        "  \\fonte{Elaborado pelo autor.}\n\\end{table}\n"
    )
    (pasta_saida / "votacao_amostra_comparativa.txt").write_text(texto_tex, encoding="utf-8")
    return tabela_amostra


def executar_estudo_votacao(pasta_saida: Path) -> dict:
    """
    Executa a secao 8 completa: prepara a amostragem, aplica a votacao
    (Algoritmo 3) para Takagi e reatancia compensada e corrigida nas 300
    barras MT, gera a tabela-resumo global e a tabela comparativa detalhada
    (amostra de barras).

    Entradas:
        pasta_saida: pasta de resultados desta secao (sera criada se nao existir).
    Saida:
        dicionario com "resultados" (por metodo), "tabela_resumo_global",
        "tabela_amostra".
    """
    pasta_saida = Path(pasta_saida)
    pasta_saida.mkdir(parents=True, exist_ok=True)

    preparo = preparar_votacao(pasta_saida)
    resultados = executar_votacao_populacao(preparo)
    for chave, tabela in resultados.items():
        tabela.to_csv(pasta_saida / f"votacao_{chave}_completa.csv", index=False)

    tabela_resumo_global = montar_tabela_resumo_global(resultados, pasta_saida)
    tabela_amostra = montar_tabela_comparativa_amostra(resultados, preparo, pasta_saida)

    return {"resultados": resultados, "tabela_resumo_global": tabela_resumo_global, "tabela_amostra": tabela_amostra}
