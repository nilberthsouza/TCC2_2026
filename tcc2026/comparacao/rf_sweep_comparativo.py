"""
Secao 11: varredura de Rf comparando diretamente o metodo de Takagi
compensado e o metodo da reatancia compensada e corrigida, nas MESMAS 300
barras MT do alimentador completo e nas MESMAS faltas simuladas (os dois
metodos sao calculados a partir dos mesmos fasores medidos em cada barra e
valor de Rf, garantindo comparacao direta ponto a ponto).

Fecha a ressalva deixada na Secao 6 (comparacao final): la, os dois metodos
so haviam sido comparados com Rf=0,01 ohm (falta franca); aqui, varre-se
Rf de 0,01 a 100 ohm (mesma faixa e justificativa de literatura da Secao 5
-- GABR et al. 2017, DAVI, OLESKOVICZ e LOPES 2023).
"""
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from tcc2026.extracao import extrator_trecho as et
from tcc2026.nucleo import (dss_core, falta_injecao as fi, geometria_eletrica as ge, graficos,
                             grafo_alimentador as ga, latex_utils, metricas, varredura_falta_rele as vf)
from tcc2026.reatancia import metodo_reatancia as mr
from tcc2026.takagi import metodo_takagi as mt

RF_VALORES_OHM = [0.01, 10.0, 25.0, 50.0, 100.0]


def preparar_alimentador(pasta_saida: Path) -> dict:
    """
    Compila o alimentador completo com a geometria de referencia Cemig
    aplicada as linhas trifasicas e monofasicas (mesmo procedimento das
    Secoes 6a/6b), e devolve o circuito, o grafo, a origem, a lista de
    barras MT e as impedancias de sequencia de referencia.

    Entradas:
        pasta_saida: pasta de resultados desta secao.
    Saida:
        dicionario com "dss", "grafo", "origem", "barras_mt", "z1_ohm_km",
        "z0_ohm_km", "k0".
    """
    ge.calcular_parametros_sequencia_losangular_cemig()

    dss0 = dss_core.compilar_alimentador()
    dss_core.definir_modo_instantaneo(dss0)
    dss_core.resolver_fluxo_potencia(dss0)
    grafo_completo = ga.componente_conexa_da_origem(ga.construir_grafo_eletrico(dss0), ga.obter_barra_origem(dss0))
    origem0 = ga.obter_barra_origem(dss0)
    caminho_master = et.extrair_subalimentador(
        dss0, origem0, set(grafo_completo.nodes), pasta_saida / "alimentador_geometria_cemig",
        "JMLT310_GEOM_RF_SWEEP", usar_geometria_cemig_trifasica=True, usar_geometria_cemig_monofasica=True)

    dss = et.compilar_subalimentador(caminho_master)
    dss_core.definir_modo_instantaneo(dss)
    dss_core.resolver_fluxo_potencia(dss)

    grafo = ga.componente_conexa_da_origem(ga.construir_grafo_eletrico(dss), ga.obter_barra_origem(dss))
    origem = ga.obter_barra_origem(dss)
    barras_mt = sorted(ga.barras_de_media_tensao(grafo) - {origem})

    dados_geo = ge.calcular_parametros_sequencia_losangular_cemig()
    z1 = complex(dados_geo["r1_ohm_km"], dados_geo["x1_ohm_km"])
    z0 = complex(dados_geo["r0_ohm_km"], dados_geo["x0_ohm_km"])
    k0 = mr.fator_compensacao_k0(z1, z0)

    return {"dss": dss, "grafo": grafo, "origem": origem, "barras_mt": barras_mt,
            "z1_ohm_km": z1, "z0_ohm_km": z0, "k0": k0}


def executar_varredura(preparo: dict, rf_valores: list = RF_VALORES_OHM) -> pd.DataFrame:
    """
    Para cada valor de Rf em rf_valores, simula a falta monofasica-terra
    nas 300 barras MT (vf.executar_varredura) e calcula, a partir dos
    MESMOS fasores medidos, a distancia estimada pelos dois metodos
    (Takagi compensado e reatancia compensada e corrigida).

    Entradas:
        preparo: dicionario devolvido por preparar_alimentador.
        rf_valores: lista de resistencias de falta a varrer (ohms).
    Saida:
        DataFrame longo: rf_ohm, barra, distancia_real_km, metodo,
        distancia_estimada_km.
    """
    dss, grafo, origem = preparo["dss"], preparo["grafo"], preparo["origem"]
    barras_mt = preparo["barras_mt"]
    z1, z0, k0 = preparo["z1_ohm_km"], preparo["z0_ohm_km"], preparo["k0"]

    linhas = []
    for rf_ohm in rf_valores:
        # vf.executar_varredura mede o estado "pre-falta" no inicio da
        # chamada a partir da ultima solucao em memoria do OpenDSS; sem
        # desabilitar explicitamente a falta e resolver o fluxo de potencia
        # de novo aqui, essa medicao ficaria contaminada pela ultima falta
        # ainda habilitada da iteracao anterior (ela nao e desfeita
        # automaticamente so por fi.remover_falta, que apenas desabilita o
        # elemento sem forcar um novo "solve").
        fi.remover_falta(dss)
        if not dss_core.resolver_fluxo_potencia(dss):
            raise RuntimeError(f"Fluxo de potencia nao convergiu ao restaurar o estado normal (Rf={rf_ohm}).")
        medidas = vf.executar_varredura(dss, grafo, origem, barras_mt, rf_ohm)
        for _, linha in medidas.iterrows():
            ia_comp_pos = mr.corrente_compensada(linha["ia_pos"], linha["i0_pos"], k0)
            d_reatancia = mr.distancia_reatancia_corrigida_exata(linha["va_pos"], ia_comp_pos, z1, z0)
            d_takagi = mt.distancia_takagi_compensado(
                linha["va_pos"], linha["ia_pos"], linha["ia_pre"],
                linha["i0_pos"], linha["i0_pre"], k0, z1)
            for metodo, distancia_estimada in [
                ("Takagi compensado", d_takagi),
                ("Reatância compensada e corrigida", d_reatancia),
            ]:
                linhas.append({
                    "rf_ohm": rf_ohm, "barra": linha["barra"],
                    "distancia_real_km": linha["distancia_real_km"],
                    "metodo": metodo, "distancia_estimada_km": distancia_estimada,
                })
    return pd.DataFrame(linhas)


def montar_tabela_metricas(tabela: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula MAE, RMSE, R2, erro medio e erro maximo absoluto, por valor de
    Rf e por metodo, sobre a populacao global das 300 barras MT.

    Entradas:
        tabela: DataFrame devolvido por executar_varredura.
    Saida:
        DataFrame com rf_ohm, metodo, mae_km, rmse_km, r2, erro_medio_km,
        erro_max_km.
    """
    linhas = []
    for (rf_ohm, metodo), sub in tabela.groupby(["rf_ohm", "metodo"]):
        m = metricas.resumo_metricas(
            sub["distancia_real_km"].to_numpy(), sub["distancia_estimada_km"].to_numpy(),
            sub["distancia_real_km"].max())
        linhas.append({"rf_ohm": rf_ohm, "metodo": metodo, "mae_km": m["mae_km"], "rmse_km": m["rmse_km"],
                        "r2": m["r2"], "erro_medio_km": m["erro_medio_km"], "erro_max_km": m["erro_max_km"]})
    tabela_metricas = pd.DataFrame(linhas).sort_values(["metodo", "rf_ohm"]).reset_index(drop=True)
    return tabela_metricas


def plotar_metricas_vs_rf(tabela_metricas: pd.DataFrame, pasta_saida: Path) -> None:
    """
    Gera dois graficos de linha (MAE e erro medio/vies) em funcao de Rf,
    uma curva por metodo, para visualizar diretamente se a vantagem da
    reatancia corrigida sobre o Takagi se mantem, cresce ou se inverte
    conforme Rf aumenta.

    Entradas:
        tabela_metricas: DataFrame devolvido por montar_tabela_metricas.
        pasta_saida: pasta de resultados desta secao.
    Saida:
        nenhuma (dois arquivos .png salvos em pasta_saida).
    """
    graficos.aplicar_estilo_padrao()

    fig, eixo = plt.subplots(figsize=(7, 5))
    sns.lineplot(data=tabela_metricas, x="rf_ohm", y="mae_km", hue="metodo", marker="o", ax=eixo,
                 palette=["#c05621", "#2f855a"])
    eixo.set_xlabel("Rf (Ω)")
    eixo.set_ylabel("MAE (km)")
    eixo.legend(title="Método")
    sns.despine(ax=eixo)
    graficos.salvar_figura(
        fig, pasta_saida / "rf_sweep_mae_comparativo.png",
        "MAE do Takagi compensado e da reatância compensada e corrigida, em função de Rf, "
        "nas mesmas 300 barras MT do alimentador completo."
    )

    fig, eixo = plt.subplots(figsize=(7, 5))
    sns.lineplot(data=tabela_metricas, x="rf_ohm", y="erro_medio_km", hue="metodo", marker="o", ax=eixo,
                 palette=["#c05621", "#2f855a"])
    eixo.axhline(0, color="gray", linewidth=1, linestyle="--")
    eixo.set_xlabel("Rf (Ω)")
    eixo.set_ylabel("Erro médio / viés (km)")
    eixo.legend(title="Método")
    sns.despine(ax=eixo)
    graficos.salvar_figura(
        fig, pasta_saida / "rf_sweep_erro_medio_comparativo.png",
        "Erro médio (viés) do Takagi compensado e da reatância compensada e corrigida, em função de Rf, "
        "nas mesmas 300 barras MT do alimentador completo."
    )


def executar_rf_sweep_comparativo(pasta_saida: Path) -> dict:
    """
    Executa a Secao 11 completa: varre Rf de 0,01 a 100 ohm nas mesmas 300
    barras MT para os dois metodos, calcula as metricas por Rf/metodo,
    gera os graficos comparativos e salva a tabela LaTeX.

    Entradas:
        pasta_saida: pasta de resultados desta secao (sera criada se nao existir).
    Saida:
        dicionario com "tabela" (resultados ponto a ponto) e "tabela_metricas".
    """
    pasta_saida = Path(pasta_saida)
    pasta_saida.mkdir(parents=True, exist_ok=True)

    preparo = preparar_alimentador(pasta_saida)
    tabela = executar_varredura(preparo)
    tabela.to_csv(pasta_saida / "rf_sweep_resultados.csv", index=False)

    tabela_metricas = montar_tabela_metricas(tabela)
    tabela_metricas.to_csv(pasta_saida / "rf_sweep_metricas.csv", index=False)
    latex_utils.salvar_tabela_latex(
        tabela_metricas.rename(columns={
            "rf_ohm": "Rf (Ω)", "metodo": "Método", "mae_km": "MAE (km)", "rmse_km": "RMSE (km)",
            "r2": "R²", "erro_medio_km": "Erro Médio (km)", "erro_max_km": "Erro Máx. (km)",
        }),
        pasta_saida / "rf_sweep_metricas.txt",
        legenda="Comparação direta entre Takagi compensado e reatância compensada e corrigida, "
                "em função de Rf, nas mesmas 300 barras MT do alimentador completo",
        rotulo="rf_sweep_comparativo",
        contexto="Secao 11 - varredura de Rf comparando os dois metodos nas mesmas faltas simuladas.",
        decimais={"Rf (Ω)": 2, "MAE (km)": 4, "RMSE (km)": 4, "R²": 4,
                  "Erro Médio (km)": 4, "Erro Máx. (km)": 4},
        alinhamento="lcccccc",
    )

    plotar_metricas_vs_rf(tabela_metricas, pasta_saida)

    return {"tabela": tabela, "tabela_metricas": tabela_metricas}
