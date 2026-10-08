"""
Monta a tabela de barras representativas do alimentador (primeira barra com
carga, barra com carga mais distante e folha sem carga), com tensao,
corrente, equivalente de Thevenin, curto monofasico/trifasico, parametros
de linha (r1/x1/r0/x0/c1/c0/distancia) e carga concentrada equivalente —
dados para montar os 3 circuitos equivalentes descritos no enunciado do TCC.
"""
from pathlib import Path

import pandas as pd

from tcc2026.nucleo import dss_core, geometria_eletrica as ge
from tcc2026.nucleo import grafo_alimentador as ga
from tcc2026.nucleo import latex_utils
from tcc2026.faltas import curto_circuito as cc
from tcc2026.faltas import selecao_barras as sb


def preparar_geometria_referencia() -> None:
    """
    Pre-calcula (e deixa em cache) os parametros de sequencia de referencia
    trifasico e monofasico ANTES de compilar o alimentador real, pois o
    motor OpenDSS e um singleton por processo e o calculo usa um circuito
    auxiliar que substituiria o alimentador ja compilado (ver aviso em
    tcc2026.nucleo.geometria_eletrica).

    Entradas:
        nenhuma.
    Saida:
        nenhuma (efeito colateral: aquece o cache das duas funcoes).
    """
    ge.calcular_parametros_sequencia_losangular_cemig()
    ge.calcular_parametros_sequencia_monofasico_cemig()


def selecionar_tres_barras(dss, grafo, origem: str) -> dict:
    """
    Seleciona as 3 barras representativas do estudo e informacoes de apoio
    (distancias, categoria topologica, ultima carga no ramal do caso 3).

    Entradas:
        dss: instancia do motor OpenDSS com o alimentador compilado.
        grafo: grafo eletrico restrito ao componente conexo da origem.
        origem: nome da barra de origem.
    Saida:
        dicionario com "distancias", "categorias", "barras_com_carga" e as
        chaves "caso_1", "caso_2", "caso_3" (nomes de barra) e
        "ultima_carga_caso_3" (barra com carga mais proxima da folha do caso 3).
    """
    distancias = ga.distancias_desde_origem(grafo, origem)
    categorias = ga.classificar_barras(grafo, origem)
    barras_mt = ga.barras_de_media_tensao(grafo)
    carregadas = sb.barras_com_carga(dss, grafo, barras_mt)

    barra_1 = sb.selecionar_barra_primeira_carga(carregadas, distancias)
    barra_2 = sb.selecionar_barra_carga_mais_distante(carregadas, distancias)
    barra_3 = sb.selecionar_folha_sem_carga(categorias, carregadas, distancias)
    ultima_carga_3 = sb.encontrar_ultima_carga_no_ramal(grafo, origem, barra_3, carregadas)

    return {
        "distancias": distancias,
        "categorias": categorias,
        "barras_com_carga": carregadas,
        "caso_1": barra_1,
        "caso_2": barra_2,
        "caso_3": barra_3,
        "ultima_carga_caso_3": ultima_carga_3,
    }


def montar_dados_operacionais(dss, grafo, origem: str, selecao: dict) -> dict:
    """
    Le a tensao e a corrente de operacao (pre-falta) nas 3 barras
    selecionadas. Precisa ser chamada com o alimentador resolvido em fluxo
    de potencia NORMAL (a tensao/corrente de barra nao fica disponivel do
    jeito usual depois de rodar o modo FaultStudy).

    Entradas:
        dss: instancia do motor OpenDSS resolvida em fluxo de potencia normal.
        grafo: grafo eletrico restrito ao componente conexo da origem.
        origem: nome da barra de origem.
        selecao: dicionario devolvido por selecionar_tres_barras.
    Saida:
        dicionario {chave_caso: {"tensao_pu": ..., "corrente_a": ...}}.
    """
    dados = {}
    for chave_caso in ("caso_1", "caso_2", "caso_3"):
        barra = selecao[chave_caso]
        tensao_pu = cc.tensao_na_barra_pu(dss, barra)
        corrente_a = cc.potencia_e_corrente_a_jusante(dss, grafo, origem, barra)["corrente_media_a"]
        dados[chave_caso] = {"tensao_pu": tensao_pu, "corrente_a": corrente_a}
    return dados


def montar_tabela_principal(dss, selecao: dict, dados_operacionais: dict) -> pd.DataFrame:
    """
    Monta a tabela principal (tensao, corrente, Thevenin, curtos) para as 3
    barras selecionadas.

    Entradas:
        dss: instancia do motor OpenDSS, ja resolvida em modo FaultStudy
            (ver curto_circuito.executar_estudo_curto_circuito), no mesmo
            ponto de carga usado para montar_dados_operacionais.
        selecao: dicionario devolvido por selecionar_tres_barras.
        dados_operacionais: dicionario devolvido por montar_dados_operacionais
            (tensao/corrente de operacao, lidas ANTES do modo FaultStudy).
    Saida:
        DataFrame com uma linha por caso (1, 2, 3).
    """
    linhas = []
    rotulos = {
        "caso_1": "Caso 1 — primeira barra com carga",
        "caso_2": "Caso 2 — barra com carga mais distante",
        "caso_3": "Caso 3 — folha sem carga",
    }
    for chave_caso, rotulo in rotulos.items():
        barra = selecao[chave_caso]
        thevenin = cc.thevenin_na_barra(dss, barra)
        linhas.append({
            "caso": rotulo,
            "barra": barra,
            "distancia_origem_km": selecao["distancias"][barra],
            "tensao_pu": dados_operacionais[chave_caso]["tensao_pu"],
            "corrente_barra_a": dados_operacionais[chave_caso]["corrente_a"],
            "z1_thevenin_ohm": thevenin["z1_ohm"],
            "z0_thevenin_ohm": thevenin["z0_ohm"],
            "isc_trifasico_a": cc.curto_circuito_trifasico_a(dss, barra),
            "isc_monofasico_a": cc.curto_circuito_monofasico_a(dss, barra),
        })
    return pd.DataFrame(linhas)


def montar_tabela_parametros_linha(grafo, origem: str, selecao: dict) -> pd.DataFrame:
    """
    Monta a tabela de parametros de linha (r1/x1/r0/x0/c1/c0/distancia) de
    cada segmento dos 3 circuitos equivalentes: casos 1 e 2 tem um unico
    segmento (origem ate a barra); o caso 3 tem dois segmentos em serie
    (origem ate a ultima carga do ramal, e dessa carga ate a barra folha).

    Entradas:
        grafo: grafo eletrico restrito ao componente conexo da origem.
        origem: nome da barra de origem.
        selecao: dicionario devolvido por selecionar_tres_barras.
    Saida:
        DataFrame com uma linha por segmento (3 segmentos no total).
    """
    linhas = []

    def _linha(rotulo, barra_ini, barra_fim):
        caminho = ga.caminho_entre_barras(grafo, barra_ini, barra_fim)
        acumulado = ge.acumular_parametros_linha_caminho(grafo, caminho)
        linhas.append({
            "segmento": rotulo,
            "de": barra_ini,
            "para": barra_fim,
            "distancia_km": acumulado["distancia_km"],
            "r1_ohm": acumulado["r1_ohm"],
            "x1_ohm": acumulado["x1_ohm"],
            "r0_ohm": acumulado["r0_ohm"],
            "x0_ohm": acumulado["x0_ohm"],
            "c1_nf": acumulado["c1_nf"],
            "c0_nf": acumulado["c0_nf"],
        })

    _linha("Caso 1 — fonte até a barra", origem, selecao["caso_1"])
    _linha("Caso 2 — fonte até a barra", origem, selecao["caso_2"])
    if selecao["ultima_carga_caso_3"] is not None:
        _linha("Caso 3 — fonte até a última carga do ramal", origem, selecao["ultima_carga_caso_3"])
        _linha("Caso 3 — última carga até a barra da falta", selecao["ultima_carga_caso_3"], selecao["caso_3"])
    else:
        _linha("Caso 3 — fonte até a barra da falta (ramal sem carga)", origem, selecao["caso_3"])
    return pd.DataFrame(linhas)


def montar_tabela_cargas_concentradas(dss, grafo, origem: str, selecao: dict) -> pd.DataFrame:
    """
    Monta a tabela de carga concentrada equivalente (potencia ativa e
    reativa a jusante) nos pontos relevantes dos 3 circuitos equivalentes.

    Entradas:
        dss: instancia do motor OpenDSS resolvida em fluxo de potencia normal.
        grafo: grafo eletrico restrito ao componente conexo da origem.
        origem: nome da barra de origem.
        selecao: dicionario devolvido por selecionar_tres_barras.
    Saida:
        DataFrame com p_kw, q_kvar (q>0 indutivo/QL, q<0 capacitivo/Qc) e
        corrente_media_a para cada ponto de carga concentrada relevante.
    """
    pontos = {
        "Caso 1 — carga concentrada na barra": selecao["caso_1"],
        "Caso 2 — carga concentrada na barra": selecao["caso_2"],
    }
    if selecao["ultima_carga_caso_3"] is not None:
        pontos["Caso 3 — carga concentrada (última carga do ramal)"] = selecao["ultima_carga_caso_3"]

    linhas = []
    for rotulo, barra in pontos.items():
        resultado = cc.potencia_e_corrente_a_jusante(dss, grafo, origem, barra)
        linhas.append({
            "ponto": rotulo,
            "barra": barra,
            "p_ativa_kw": resultado["p_kw"],
            "q_indutivo_ql_kvar": resultado["q_kvar"] if resultado["q_kvar"] > 0 else 0.0,
            "q_capacitivo_qc_kvar": resultado["q_kvar"] if resultado["q_kvar"] < 0 else 0.0,
            "corrente_media_a": resultado["corrente_media_a"],
        })
    return pd.DataFrame(linhas)


def executar_tabela_barras(pasta_saida: Path) -> dict:
    """
    Executa a secao completa: seleciona as 3 barras representativas,
    calcula tensao/corrente/Thevenin/curtos, parametros de linha e carga
    concentrada, e salva tudo (CSV + tabelas LaTeX) na pasta de resultados.

    Entradas:
        pasta_saida: pasta de resultados desta secao (sera criada se nao existir).
    Saida:
        dicionario com "selecao", "tabela_principal", "tabela_linhas" e
        "tabela_cargas" (DataFrames/dict).
    """
    pasta_saida = Path(pasta_saida)
    pasta_saida.mkdir(parents=True, exist_ok=True)

    preparar_geometria_referencia()

    dss = dss_core.compilar_alimentador()
    dss_core.definir_modo_instantaneo(dss)
    if not dss_core.resolver_fluxo_potencia(dss):
        raise RuntimeError("Fluxo de potencia nao convergiu no ponto de operacao padrao.")

    grafo_completo = ga.construir_grafo_eletrico(dss)
    origem = ga.obter_barra_origem(dss)
    grafo = ga.componente_conexa_da_origem(grafo_completo, origem)

    selecao = selecionar_tres_barras(dss, grafo, origem)
    tabela_cargas = montar_tabela_cargas_concentradas(dss, grafo, origem, selecao)
    tabela_linhas = montar_tabela_parametros_linha(grafo, origem, selecao)
    dados_operacionais = montar_dados_operacionais(dss, grafo, origem, selecao)

    cc.executar_estudo_curto_circuito(dss)
    tabela_principal = montar_tabela_principal(dss, selecao, dados_operacionais)

    tabela_principal.to_csv(pasta_saida / "tabela_principal.csv", index=False)
    tabela_linhas.to_csv(pasta_saida / "tabela_parametros_linha.csv", index=False)
    tabela_cargas.to_csv(pasta_saida / "tabela_cargas_concentradas.csv", index=False)
    pd.DataFrame([{
        "caso_1": selecao["caso_1"], "caso_2": selecao["caso_2"], "caso_3": selecao["caso_3"],
        "ultima_carga_caso_3": selecao["ultima_carga_caso_3"],
    }]).to_csv(pasta_saida / "barras_selecionadas.csv", index=False)

    tabela_principal_latex = tabela_principal.copy()
    tabela_principal_latex["z1_thevenin_ohm"] = tabela_principal_latex["z1_thevenin_ohm"].apply(
        lambda z: latex_utils.formatar_complexo_br(z, 3))
    tabela_principal_latex["z0_thevenin_ohm"] = tabela_principal_latex["z0_thevenin_ohm"].apply(
        lambda z: latex_utils.formatar_complexo_br(z, 3))
    latex_utils.salvar_tabela_latex(
        tabela_principal_latex.rename(columns={
            "caso": "Caso", "barra": "Barra", "distancia_origem_km": "Dist. (km)",
            "tensao_pu": "V (pu)", "corrente_barra_a": "I (A)", "z1_thevenin_ohm": "Z1 Th. (Ω)",
            "z0_thevenin_ohm": "Z0 Th. (Ω)", "isc_trifasico_a": "Icc 3φ (A)",
            "isc_monofasico_a": "Icc 1φ-T (A)",
        }),
        pasta_saida / "tabela_principal.txt",
        legenda="Tensão, corrente, equivalente de Thevenin e correntes de curto-circuito nas barras selecionadas (JMLT310 reduzido)",
        rotulo="falta_tres_barras_principal",
        contexto="Secao 2 - tabela principal das 3 barras representativas (Thevenin e curto-circuito).",
        decimais={"Dist. (km)": 3, "V (pu)": 4, "I (A)": 2, "Icc 3φ (A)": 1, "Icc 1φ-T (A)": 1},
        alinhamento="lcccccccc",
    )
    latex_utils.salvar_tabela_latex(
        tabela_linhas.rename(columns={
            "segmento": "Segmento", "de": "De", "para": "Até", "distancia_km": "km",
            "r1_ohm": "R1 (Ω)", "x1_ohm": "X1 (Ω)", "r0_ohm": "R0 (Ω)",
            "x0_ohm": "X0 (Ω)", "c1_nf": "C1 (nF)", "c0_nf": "C0 (nF)",
        }),
        pasta_saida / "tabela_parametros_linha.txt",
        legenda="Parâmetros de sequência das linhas dos circuitos equivalentes (geometria de referência Cemig)",
        rotulo="falta_tres_barras_linhas",
        contexto="Secao 2 - r1/x1/r0/x0/c1/c0 e distancia de cada segmento dos 3 circuitos equivalentes.",
        decimais={"km": 3, "R1 (Ω)": 3, "X1 (Ω)": 3, "R0 (Ω)": 3, "X0 (Ω)": 3, "C1 (nF)": 1, "C0 (nF)": 1},
        alinhamento="lllccccccc",
    )
    latex_utils.salvar_tabela_latex(
        tabela_cargas.rename(columns={
            "ponto": "Ponto", "barra": "Barra", "p_ativa_kw": "P (kW)",
            "q_indutivo_ql_kvar": "QL (kvar)", "q_capacitivo_qc_kvar": "Qc (kvar)",
            "corrente_media_a": "I (A)",
        }),
        pasta_saida / "tabela_cargas_concentradas.txt",
        legenda="Carga concentrada equivalente nos pontos de corte dos circuitos equivalentes",
        rotulo="falta_tres_barras_cargas",
        contexto="Secao 2 - potencia ativa/reativa e corrente concentradas a jusante de cada ponto.",
        decimais={"P (kW)": 3, "QL (kvar)": 3, "Qc (kvar)": 3, "I (A)": 2},
        alinhamento="llcccc",
    )

    return {
        "selecao": selecao,
        "tabela_principal": tabela_principal,
        "tabela_linhas": tabela_linhas,
        "tabela_cargas": tabela_cargas,
    }
