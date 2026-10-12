"""
Secao 10: analise de sensibilidade dos metodos de localizacao de falta a
tres parametros -- resistencia de falta (Rf), carregamento (load_scale) e
resistencia de referencia do condutor (R1) -- no sentido classico de
controle: a sensibilidade S de uma saida d (distancia estimada) a um
parametro p e definida como S = (dd/dp)*(p/d) (adimensional, variacao
percentual relativa da saida por variacao percentual do parametro),
calculada de forma fechada quando o equacionamento permite (Rf), ou
estimada por regressao/perturbacao finita em torno do ponto de operacao
nominal quando nao ha forma fechada tratavel (carregamento, R1).
"""
from pathlib import Path

import numpy as np
import pandas as pd

from tcc2026.extracao import extrator_trecho as et
from tcc2026.nucleo import (dss_core, geometria_eletrica as ge, grafo_alimentador as ga,
                             latex_utils, varredura_falta_rele as vf)
from tcc2026.reatancia import metodo_reatancia as mr
from tcc2026.takagi import metodo_takagi as mt

FATORES_R1 = [0.8, 0.9, 1.0, 1.1, 1.2]
QUANTIDADE_AMOSTRA_R1 = 8
RF_PADRAO_OHM = 0.01


def sensibilidade_rf_analitica() -> pd.DataFrame:
    """
    Sensibilidade da distancia estimada a Rf, em forma fechada, a partir
    da propria derivacao analitica do offset (Secao 2.3.3 do TCC,
    Equacao im_zm_offset): d_est = d_real + Rf*Im(C)/Im(Z1L). Como C e
    escala-invariante ao comprimento do caminho (C depende so da razao
    entre Z1L e Z0L, nao de seus modulos absolutos), a sensibilidade em
    km por ohm de Rf e CONSTANTE, independente do comprimento do caminho
    rele-falta -- por isso calculada diretamente com a taxa de referencia
    por km (resultado identico ao usar os valores acumulados de um
    caminho qualquer).

    Entradas:
        nenhuma.
    Saida:
        DataFrame com "metodo" e "s_rf_km_ohm" (sensibilidade em km de
        erro por ohm de Rf): reatancia sem correcao do offset (K0 apenas),
        reatancia compensada e corrigida (exata, S=0) e Takagi compensado
        (S=0, cancelamento exato de Rf por construcao, Secao 2.4).
    """
    dados = ge.calcular_parametros_sequencia_losangular_cemig()
    z1 = complex(dados["r1_ohm_km"], dados["x1_ohm_km"])
    z0 = complex(dados["r0_ohm_km"], dados["x0_ohm_km"])
    c = mr.fator_c(z1, z0)
    s_rf_k0 = c.imag / z1.imag
    return pd.DataFrame([
        {"metodo": "Reatância K0 (sem correção do offset)", "s_rf_km_ohm": s_rf_k0, "origem": "analítica (fechada)"},
        {"metodo": "Reatância compensada e corrigida", "s_rf_km_ohm": 0.0, "origem": "exata (por construção)"},
        {"metodo": "Takagi compensado", "s_rf_km_ohm": 0.0, "origem": "exata (por construção)"},
    ])


def sensibilidade_carregamento_empirica(pasta_takagi: Path, pasta_reatancia: Path) -> pd.DataFrame:
    """
    Sensibilidade do erro (MAE) ao fator de carregamento (load_scale),
    estimada pela inclinacao da reta de regressao linear sobre os dados
    ja calculados da varredura de carregamento global (Secoes 6a/6b,
    load_scale em {0,1,2,4,6,8,10}) -- nao ha forma fechada tratavel para
    esse efeito (depende da topologia completa do alimentador e da
    distribuicao de cargas intermediarias, Secao 6b), por isso a
    sensibilidade e estimada empiricamente a partir dos dados ja
    simulados.

    Entradas:
        pasta_takagi: pasta de resultados da Secao 6a (contem
            carregamento_global_metricas.csv).
        pasta_reatancia: pasta de resultados da Secao 6b (idem).
    Saida:
        DataFrame com "metodo", "s_carga_km_por_unidade" (inclinacao, km
        de MAE por unidade de load_scale) e "r2_ajuste" (qualidade do
        ajuste linear).
    """
    linhas = []
    for metodo, pasta in [("Takagi compensado", pasta_takagi),
                           ("Reatância compensada e corrigida", pasta_reatancia)]:
        df = pd.read_csv(Path(pasta) / "carregamento_global_metricas.csv")
        slope, _ = np.polyfit(df["fator_carregamento"], df["mae_km"], 1)
        r2 = np.corrcoef(df["fator_carregamento"], df["mae_km"])[0, 1] ** 2
        linhas.append({"metodo": metodo, "s_carga_km_por_unidade": slope, "r2_ajuste": r2})
    return pd.DataFrame(linhas)


def preparar_amostra_sensibilidade_r1(pasta_saida: Path, quantidade: int = QUANTIDADE_AMOSTRA_R1,
                                       rf_ohm: float = RF_PADRAO_OHM) -> pd.DataFrame:
    """
    Mede os fasores (Va, Ia, I0, pre e pos-falta) em uma pequena amostra
    de barras MT espalhadas por distancia (mesma geometria Cemig das
    Secoes 6a/6b), para uso na analise de sensibilidade a R1
    (sensibilidade_r1_numerica). Uma amostra pequena e suficiente aqui,
    pois o objetivo e ilustrar a ordem de grandeza da sensibilidade (ver
    docstring do modulo), nao caracterizar sua distribuicao completa nas
    300 barras.

    Entradas:
        pasta_saida: pasta de resultados desta secao.
        quantidade: numero de barras da amostra, espacadas uniformemente
            por distancia desde a origem.
        rf_ohm: resistencia de falta usada na medicao (ohms).
    Saida:
        DataFrame no formato de varredura_falta_rele.executar_varredura
        (colunas "barra", "distancia_real_km", "va_pos", "ia_pre",
        "ia_pos", "i0_pre", "i0_pos").
    """
    dss0 = dss_core.compilar_alimentador()
    dss_core.definir_modo_instantaneo(dss0)
    dss_core.resolver_fluxo_potencia(dss0)
    grafo_completo = ga.componente_conexa_da_origem(ga.construir_grafo_eletrico(dss0), ga.obter_barra_origem(dss0))
    origem0 = ga.obter_barra_origem(dss0)
    caminho_master = et.extrair_subalimentador(
        dss0, origem0, set(grafo_completo.nodes), pasta_saida / "alimentador_geometria_cemig",
        "JMLT310_SENS_R1", usar_geometria_cemig_trifasica=True, usar_geometria_cemig_monofasica=True)

    dss = et.compilar_subalimentador(caminho_master)
    dss_core.definir_modo_instantaneo(dss)
    dss_core.resolver_fluxo_potencia(dss)
    grafo = ga.componente_conexa_da_origem(ga.construir_grafo_eletrico(dss), ga.obter_barra_origem(dss))
    origem = ga.obter_barra_origem(dss)
    distancias = ga.distancias_desde_origem(grafo, origem)
    barras_mt = sorted(ga.barras_de_media_tensao(grafo) - {origem})
    barras_ordenadas = sorted(barras_mt, key=distancias.get)
    n = len(barras_ordenadas)
    amostra = [barras_ordenadas[round(i * (n - 1) / (quantidade - 1))] for i in range(quantidade)]
    # remove a barra mais proxima da origem: distancia real quase nula torna
    # a sensibilidade RELATIVA (normalizada por d_real) mal definida ali.
    amostra = [b for b in amostra if distancias[b] > 0.5]

    return vf.executar_varredura(dss, grafo, origem, amostra, rf_ohm)


def sensibilidade_r1_numerica(medidas: pd.DataFrame, fatores: list = FATORES_R1) -> pd.DataFrame:
    """
    Sensibilidade da distancia estimada a uma variacao no R1 de
    referencia (mantendo X1, R0 e X0 fixos no valor da geometria Cemig),
    estimada por perturbacao numerica finita: recalcula a distancia para
    cada fator de R1 em `fatores`, usando os MESMOS fasores medidos (Va,
    Ia, I0 nao mudam -- a perturbacao e so na referencia assumida pela
    formula, nao no circuito real), e ajusta a sensibilidade normalizada
    S = (Delta_d/d_real) / (Delta_R1/R1_ref) entre o fator de referencia
    (1,0) e +10% (1,1).

    Entradas:
        medidas: DataFrame devolvido por preparar_amostra_sensibilidade_r1.
        fatores: lista de multiplicadores de R1 a testar (1,0 = referencia).
    Saida:
        DataFrame com "barra", "distancia_real_km", "s_r1_reatancia",
        "s_r1_takagi" (sensibilidade normalizada, adimensional).
    """
    dados_geo = ge.calcular_parametros_sequencia_losangular_cemig()
    r1_ref, x1_ref = dados_geo["r1_ohm_km"], dados_geo["x1_ohm_km"]
    z0_ref = complex(dados_geo["r0_ohm_km"], dados_geo["x0_ohm_km"])

    linhas = []
    for _, linha in medidas.iterrows():
        valores_reat, valores_tak = {}, {}
        for fator in fatores:
            z1_pert = complex(r1_ref * fator, x1_ref)
            k0 = mr.fator_compensacao_k0(z1_pert, z0_ref)
            ia_comp = mr.corrente_compensada(linha["ia_pos"], linha["i0_pos"], k0)
            valores_reat[fator] = mr.distancia_reatancia_corrigida_exata(
                linha["va_pos"], ia_comp, z1_pert, z0_ref)
            valores_tak[fator] = mt.distancia_takagi_compensado(
                linha["va_pos"], linha["ia_pos"], linha["ia_pre"],
                linha["i0_pos"], linha["i0_pre"], k0, z1_pert)
        d_real = linha["distancia_real_km"]
        s_reat = ((valores_reat[1.1] - valores_reat[1.0]) / d_real) / 0.10
        s_tak = ((valores_tak[1.1] - valores_tak[1.0]) / d_real) / 0.10
        linhas.append({"barra": linha["barra"], "distancia_real_km": d_real,
                        "s_r1_reatancia": s_reat, "s_r1_takagi": s_tak})
    return pd.DataFrame(linhas)


def executar_analise_sensibilidade(pasta_saida: Path, pasta_takagi: Path, pasta_reatancia: Path) -> dict:
    """
    Executa a Secao 10 completa: sensibilidade a Rf (analitica), ao
    carregamento (empirica, dados ja simulados) e a R1 de referencia do
    condutor (numerica, amostra pequena).

    Entradas:
        pasta_saida: pasta de resultados desta secao (sera criada se nao existir).
        pasta_takagi: pasta de resultados da Secao 6a.
        pasta_reatancia: pasta de resultados da Secao 6b.
    Saida:
        dicionario com "sensibilidade_rf", "sensibilidade_carga",
        "sensibilidade_r1" (DataFrames).
    """
    pasta_saida = Path(pasta_saida)
    pasta_saida.mkdir(parents=True, exist_ok=True)

    sens_rf = sensibilidade_rf_analitica()
    sens_rf.to_csv(pasta_saida / "sensibilidade_rf.csv", index=False)
    latex_utils.salvar_tabela_latex(
        sens_rf.rename(columns={"metodo": "Método", "s_rf_km_ohm": "S_Rf (km/Ω)", "origem": "Origem"}),
        pasta_saida / "sensibilidade_rf.txt",
        legenda="Sensibilidade da distância estimada à resistência de falta (Rf), forma fechada",
        rotulo="sensibilidade_rf", contexto="Secao 10 - sensibilidade analitica a Rf, por metodo.",
        decimais={"S_Rf (km/Ω)": 4}, alinhamento="lcl",
    )

    sens_carga = sensibilidade_carregamento_empirica(pasta_takagi, pasta_reatancia)
    sens_carga.to_csv(pasta_saida / "sensibilidade_carregamento.csv", index=False)
    latex_utils.salvar_tabela_latex(
        sens_carga.rename(columns={
            "metodo": "Método", "s_carga_km_por_unidade": "S_carga (km MAE / unidade load\\_scale)",
            "r2_ajuste": "R² do ajuste",
        }),
        pasta_saida / "sensibilidade_carregamento.txt",
        legenda="Sensibilidade do erro (MAE) ao fator de carregamento, estimada por regressão linear",
        rotulo="sensibilidade_carregamento",
        contexto="Secao 10 - sensibilidade empirica ao carregamento (load_scale), por metodo.",
        decimais={"S_carga (km MAE / unidade load\\_scale)": 5, "R² do ajuste": 4}, alinhamento="lcc",
    )

    medidas_r1 = preparar_amostra_sensibilidade_r1(pasta_saida)
    sens_r1_por_barra = sensibilidade_r1_numerica(medidas_r1)
    sens_r1_por_barra.to_csv(pasta_saida / "sensibilidade_r1_por_barra.csv", index=False)
    sens_r1_resumo = pd.DataFrame([{
        "metodo": "Reatância compensada e corrigida",
        "s_r1_media": sens_r1_por_barra["s_r1_reatancia"].mean(),
        "s_r1_desvio_padrao": sens_r1_por_barra["s_r1_reatancia"].std(),
    }, {
        "metodo": "Takagi compensado",
        "s_r1_media": sens_r1_por_barra["s_r1_takagi"].mean(),
        "s_r1_desvio_padrao": sens_r1_por_barra["s_r1_takagi"].std(),
    }])
    sens_r1_resumo.to_csv(pasta_saida / "sensibilidade_r1_resumo.csv", index=False)
    latex_utils.salvar_tabela_latex(
        sens_r1_resumo.rename(columns={
            "metodo": "Método", "s_r1_media": "S_R1 (média)", "s_r1_desvio_padrao": "S_R1 (desvio padrão)",
        }),
        pasta_saida / "sensibilidade_r1_resumo.txt",
        legenda="Sensibilidade normalizada da distância estimada a um erro no R1 de referência do condutor",
        rotulo="sensibilidade_r1",
        contexto=f"Secao 10 - sensibilidade numerica a R1 (perturbacao de +10%), "
                 f"amostra de {len(sens_r1_por_barra)} barras.",
        decimais={"S_R1 (média)": 4, "S_R1 (desvio padrão)": 4}, alinhamento="lcc",
    )

    return {"sensibilidade_rf": sens_rf, "sensibilidade_carga": sens_carga,
            "sensibilidade_r1_por_barra": sens_r1_por_barra, "sensibilidade_r1_resumo": sens_r1_resumo}
