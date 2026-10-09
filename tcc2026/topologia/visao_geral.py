"""
Visao geral do alimentador JMLT310 (rede reduzida): fluxo de potencia,
curva horaria, topologia MT (tronco, folhas, ramificacoes, transformadores,
linecodes) e verificacao/adaptacao da geometria das linhas.
"""
from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from tcc2026.nucleo import dss_core, geometria_eletrica as ge
from tcc2026.nucleo import grafo_alimentador as ga
from tcc2026.nucleo import graficos, latex_utils
from tcc2026.nucleo import mapa_geografico as mg


def resumo_fluxo_potencia(pasta_saida: Path) -> dict:
    """
    Resolve o fluxo de potencia do alimentador (ponto de operacao padrao,
    hora 0) e salva o resumo em CSV.

    Entradas:
        pasta_saida: pasta onde salvar "fluxo_potencia_resumo.csv".
    Saida:
        dicionario com p_ativa_kw, p_reativa_kvar, perdas_ativa_kw,
        perdas_reativa_kvar, perdas_percentual, tensao_min/media/max_pu.
    """
    dss = dss_core.compilar_alimentador()
    dss_core.definir_modo_instantaneo(dss)
    convergiu = dss_core.resolver_fluxo_potencia(dss)
    if not convergiu:
        raise RuntimeError("Fluxo de potencia nao convergiu no ponto de operacao padrao.")
    resumo = dss_core.resumo_potencia_e_perdas(dss)
    pd.DataFrame([resumo]).to_csv(pasta_saida / "fluxo_potencia_resumo.csv", index=False)
    return resumo


def curvas_diarias(pasta_saida: Path) -> pd.DataFrame:
    """
    Simula o alimentador hora a hora (24h) e gera um grafico seaborn
    separado para cada grandeza (potencia ativa, potencia reativa, perdas
    ativas e tensao), sem titulos grandes.

    Entradas:
        pasta_saida: pasta onde salvar "curva_horaria.csv" e os .png.
    Saida:
        DataFrame com a curva horaria completa (ver dss_core.simular_dia_horario).
    """
    dss = dss_core.compilar_alimentador()
    curva = dss_core.simular_dia_horario(dss, horas=24)
    curva.to_csv(pasta_saida / "curva_horaria.csv", index=False)

    graficos.aplicar_estilo_padrao()
    especificacoes = [
        ("p_ativa_kw", "Potência ativa (kW)", "curva_potencia_ativa.png",
         "Curva horária de potência ativa total entregue pela fonte (kW), 24 h."),
        ("p_reativa_kvar", "Potência reativa (kvar)", "curva_potencia_reativa.png",
         "Curva horária de potência reativa total entregue pela fonte (kvar), 24 h."),
        ("perdas_ativa_kw", "Perdas ativas (kW)", "curva_perdas.png",
         "Curva horária de perdas ativas totais do alimentador (kW), 24 h."),
        ("tensao_media_pu", "Tensão média (pu)", "curva_tensao_media.png",
         "Curva horária da tensão média nas barras do alimentador (pu), 24 h."),
    ]
    for coluna, rotulo_y, nome_arquivo, descricao in especificacoes:
        fig, eixo = plt.subplots(figsize=(7, 3.5))
        sns.lineplot(data=curva, x="hora", y=coluna, marker="o", ax=eixo, color="#2b6cb0")
        eixo.set_xlabel("Hora")
        eixo.set_ylabel(rotulo_y)
        eixo.set_title("")
        sns.despine(ax=eixo)
        graficos.salvar_figura(fig, pasta_saida / nome_arquivo, descricao)
    return curva


def analise_topologia(pasta_saida: Path) -> dict:
    """
    Calcula a topologia MT do alimentador: distancia do tronco, numero de
    folhas, barras de ramificacao, barras MT, km total de linhas MT e
    top-5 linecodes mais usados. Salva as tabelas em CSV e a tabela dos
    linecodes tambem em LaTeX.

    Entradas:
        pasta_saida: pasta onde salvar os CSVs/LaTeX desta analise.
    Saida:
        dicionario-resumo com os principais numeros da topologia.
    """
    dss = dss_core.compilar_alimentador()
    grafo_completo = ga.construir_grafo_eletrico(dss)
    origem = ga.obter_barra_origem(dss)
    grafo = ga.componente_conexa_da_origem(grafo_completo, origem)

    barra_tronco, distancia_tronco_km = ga.distancia_tronco(grafo, origem)
    categorias = ga.classificar_barras(grafo, origem)
    contagem = Counter(categorias.values())
    barras_mt = ga.barras_de_media_tensao(grafo)
    km_total_mt = ga.comprimento_total_linhas_km(grafo)

    pd.DataFrame(
        sorted(categorias.items()), columns=["barra", "categoria"]
    ).to_csv(pasta_saida / "barras_classificadas.csv", index=False)

    linhas = dss.lines
    contagem_linecode = Counter()
    km_por_linecode = Counter()
    for b1, b2, dados in grafo_completo.edges(data=True):
        if dados["tipo"] == "linha":
            contagem_linecode[dados["linecode"]] += 1
            km_por_linecode[dados["linecode"]] += dados["comprimento_km"]

    linhas_lc = dss.linecodes
    linhas_nome_valida = set(linhas_lc.names)
    top5 = []
    for codigo, uso in contagem_linecode.most_common(5):
        if codigo in linhas_nome_valida:
            linhas_lc.name = codigo
            r1, x1, fases = linhas_lc.r1, linhas_lc.x1, linhas_lc.phases
        else:
            r1, x1, fases = float("nan"), float("nan"), None
        top5.append({
            "linecode": codigo,
            "trechos": uso,
            "km_total": round(km_por_linecode[codigo], 3),
            "fases": fases,
            "r1_ohm_km": r1,
            "x1_ohm_km": x1,
        })
    tabela_top5 = pd.DataFrame(top5)
    tabela_top5.to_csv(pasta_saida / "top5_linecodes.csv", index=False)
    latex_utils.salvar_tabela_latex(
        tabela_top5.rename(columns={
            "linecode": "Linecode", "trechos": "Trechos", "km_total": "km",
            "fases": "Fases", "r1_ohm_km": "R1 (Ω/km)", "x1_ohm_km": "X1 (Ω/km)",
        }),
        pasta_saida / "tabela_top5_linecodes.txt",
        legenda="Cinco linecodes mais usados no alimentador JMLT310 reduzido",
        rotulo="top5_linecodes",
        contexto="Visao geral do alimentador - top 5 linecodes mais usados (numero de trechos).",
        decimais={"Trechos": 0, "km": 3, "Fases": 0, "R1 (Ω/km)": 4, "X1 (Ω/km)": 4},
        alinhamento="lccccc",
    )

    trafos = dss.transformers
    num_transformadores = len(trafos.names)
    potencias_kva = []
    for nome in trafos.names:
        trafos.name = nome
        potencias_kva.append(trafos.kva)
    tabela_trafos = pd.Series(potencias_kva).value_counts().sort_index()
    tabela_trafos.to_csv(pasta_saida / "transformadores_por_kva.csv", header=["quantidade"])

    graficos.aplicar_estilo_padrao()
    fig, eixo = plt.subplots(figsize=(7, 3.5))
    sns.barplot(x=tabela_trafos.index.astype(str), y=tabela_trafos.values, ax=eixo, color="#2b6cb0")
    eixo.set_xlabel("Potência nominal (kVA)")
    eixo.set_ylabel("Quantidade de transformadores")
    eixo.set_title("")
    sns.despine(ax=eixo)
    graficos.salvar_figura(
        fig, pasta_saida / "histograma_transformadores.png",
        "Histograma da quantidade de transformadores por potência nominal (kVA)."
    )

    usa_geometria = ge.verificar_uso_linegeometry(dss)
    parametros_geometria_referencia = None
    if not usa_geometria:
        parametros_geometria_referencia = ge.calcular_parametros_sequencia_losangular_cemig()

    resumo = {
        "barra_origem": origem,
        "barra_tronco_mais_distante": barra_tronco,
        "distancia_tronco_km": distancia_tronco_km,
        "num_folhas_mt": contagem.get("folha_mt", 0),
        "num_folhas_secundario_trafo": contagem.get("folha_secundario_trafo", 0),
        "num_ramificacoes": contagem.get("ramificacao", 0),
        "num_passagem": contagem.get("passagem", 0),
        "num_transformadores": num_transformadores,
        "num_barras_mt": len(barras_mt),
        "km_total_linhas_mt": km_total_mt,
        "usa_linegeometry_original": usa_geometria,
        "parametros_geometria_referencia_cemig": parametros_geometria_referencia,
    }
    pd.DataFrame([{k: v for k, v in resumo.items() if k != "parametros_geometria_referencia_cemig"}]
                 ).to_csv(pasta_saida / "topologia_resumo.csv", index=False)
    return resumo


def mapa_geral(pasta_saida: Path) -> Path:
    """
    Gera o mapa geografico do alimentador completo (sem nenhum trecho
    destacado), a partir das coordenadas de barras do alimentador
    (buscoords.csv).

    Entradas:
        pasta_saida: pasta onde salvar "mapa_alimentador.png".
    Saida:
        Path da figura gerada.
    """
    dss = dss_core.compilar_alimentador()
    grafo_completo = ga.construir_grafo_eletrico(dss)
    origem = ga.obter_barra_origem(dss)
    grafo = ga.componente_conexa_da_origem(grafo_completo, origem)
    coordenadas = mg.carregar_coordenadas()
    return mg.plotar_mapa_geografico(
        grafo, coordenadas, pasta_saida / "mapa_alimentador.png",
        "Mapa geográfico do alimentador JMLT310 reduzido (origem em azul).",
        barra_origem=origem,
    )


def executar_visao_geral(pasta_saida: Path) -> dict:
    """
    Executa a visao geral completa do alimentador: fluxo de potencia,
    curvas horarias e topologia MT, salvando todos os resultados na pasta
    informada.

    Entradas:
        pasta_saida: pasta de resultados desta secao (sera criada se nao existir).
    Saida:
        dicionario com as chaves "fluxo_potencia", "topologia" (resumos) e
        "curva_horaria" (DataFrame).
    """
    pasta_saida = Path(pasta_saida)
    pasta_saida.mkdir(parents=True, exist_ok=True)
    fluxo = resumo_fluxo_potencia(pasta_saida)
    curva = curvas_diarias(pasta_saida)
    topologia = analise_topologia(pasta_saida)
    mapa_geral(pasta_saida)
    return {"fluxo_potencia": fluxo, "curva_horaria": curva, "topologia": topologia}
