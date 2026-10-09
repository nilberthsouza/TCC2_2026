"""
Secao 5: efeito da resistencia de falta (Rf) na distancia estimada.

- Trecho monofasico: 10 barras distribuidas ao longo do trecho, curto-
  circuito com 4 valores de Rf (0,01, 5, 15 e 25 ohm), metodo da reatancia
  simples (sem compensacao, ja que o trecho e monofasico).
- Trecho trifasico: superficie 3D (analitica) mostrando como Rf e a
  diferenca angular entre Z1 e Z0 afetam o offset introduzido na distancia
  estimada pelo metodo da reatancia com compensacao K0.
"""
import cmath
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401 (necessario para projection="3d")

from tcc2026.extracao import extrator_trecho as et
from tcc2026.nucleo import dss_core, falta_injecao as fi, geometria_eletrica as ge
from tcc2026.nucleo import grafo_alimentador as ga, graficos
from tcc2026.reatancia import estudo_monofasico, metodo_reatancia as mr

RF_VALORES_OHM = [0.01, 5.0, 15.0, 25.0]


def selecionar_dez_barras_distribuidas(distancias: dict, origem: str) -> list:
    """
    Seleciona ate 10 barras distribuidas ao longo do trecho (por distancia
    ate a origem, igualmente espacadas na lista ordenada), para o estudo do
    efeito da resistencia de falta.

    Entradas:
        distancias: dicionario {barra: distancia_km} desde a origem.
        origem: nome da barra de origem (excluida da selecao).
    Saida:
        lista de ate 10 nomes de barra, em ordem crescente de distancia.
    """
    barras_ordenadas = sorted((b for b in distancias if b != origem), key=distancias.get)
    n = len(barras_ordenadas)
    if n <= 10:
        return barras_ordenadas
    indices = sorted({round(i * (n - 1) / 9) for i in range(10)})
    return [barras_ordenadas[i] for i in indices]


def executar_efeito_rf_monofasico(pasta_saida: Path) -> dict:
    """
    Aplica curtos-circuitos monofasicos-terra em 10 barras do trecho
    monofasico (Secao 3), variando Rf em RF_VALORES_OHM, e estima a
    distancia pelo metodo da reatancia simples, salvando tabela e grafico
    do erro em funcao da distancia real, uma curva por Rf.

    Entradas:
        pasta_saida: pasta de resultados desta secao (sera criada se nao existir).
    Saida:
        dicionario com "tabela" (DataFrame) e "x1_ref_ohm_km".
    """
    pasta_saida = Path(pasta_saida)
    pasta_saida.mkdir(parents=True, exist_ok=True)

    extracao = estudo_monofasico.extrair_trecho(pasta_saida)
    dss = et.compilar_subalimentador(extracao["caminho_master"])
    dss_core.definir_modo_instantaneo(dss)
    dss_core.resolver_fluxo_potencia(dss)

    grafo = ga.componente_conexa_da_origem(ga.construir_grafo_eletrico(dss), ga.obter_barra_origem(dss))
    origem = ga.obter_barra_origem(dss)
    distancias_todas = ga.distancias_desde_origem(grafo, origem)
    barras_mt = ga.barras_de_media_tensao(grafo)
    distancias = {b: d for b, d in distancias_todas.items() if b in barras_mt}
    x1_ref = mr.x1_medio_ponderado_trecho(dss, grafo)
    barras = selecionar_dez_barras_distribuidas(distancias, origem)

    fi.preparar_elemento_falta(dss)
    fi.desligar_todas_as_cargas(dss)

    linhas = []
    for barra in barras:
        dss.circuit.set_active_bus(barra)
        fase = int(dss.bus.nodes[0])
        for rf_ohm in RF_VALORES_OHM:
            fi.aplicar_falta_monofasica(dss, barra, fase, rf_ohm)
            dss.text("solve")
            if dss.solution.converged:
                tensao, corrente = fi.medir_tensao_corrente_rele(dss, origem, fase)
                distancia_estimada = mr.distancia_reatancia_simples(tensao, corrente, x1_ref)
                linhas.append({
                    "barra": barra, "rf_ohm": rf_ohm, "distancia_real_km": distancias[barra],
                    "distancia_estimada_km": distancia_estimada,
                    "erro_km": distancia_estimada - distancias[barra],
                })
            fi.remover_falta(dss)
    fi.religar_todas_as_cargas(dss)

    tabela = pd.DataFrame(linhas)
    tabela.to_csv(pasta_saida / "efeito_rf_monofasico.csv", index=False)

    graficos.aplicar_estilo_padrao()
    fig, eixo = plt.subplots(figsize=(7, 5))
    sns.lineplot(data=tabela, x="distancia_real_km", y="erro_km", hue="rf_ohm",
                 marker="o", ax=eixo, palette="flare")
    eixo.axhline(0, color="gray", linewidth=1, linestyle="--")
    eixo.set_xlabel("Distância real (km)")
    eixo.set_ylabel("Erro (km)")
    eixo.legend(title="Rf (Ω)")
    sns.despine(ax=eixo)
    graficos.salvar_figura(
        fig, pasta_saida / "efeito_rf_monofasico.png",
        "Erro do método da reatância simples em função da distância real, para 4 valores de resistência de falta."
    )
    return {"tabela": tabela, "x1_ref_ohm_km": x1_ref}


def executar_efeito_rf_trifasico_3d(pasta_saida: Path,
                                     rf_max_ohm: float = 25.0,
                                     delta_theta_max_graus: float = 60.0,
                                     resolucao: int = 40) -> dict:
    """
    Calcula analiticamente o offset introduzido na parte imaginaria da
    impedancia aparente compensada (Zm = s*Z1 + Rf*C) em funcao de Rf e da
    diferenca angular entre Z0 e Z1 (mantendo o modulo de Z0 fixo no valor
    de referencia e variando so o angulo), e plota a superficie 3D
    resultante (offset convertido em km, dividindo por X1).

    Entradas:
        pasta_saida: pasta de resultados desta secao (sera criada se nao existir).
        rf_max_ohm: maior valor de Rf varrido (ohms); a varredura comeca em 0,01 ohm.
        delta_theta_max_graus: maior |diferenca angular| entre Z0 e Z1 varrida (graus).
        resolucao: numero de pontos em cada eixo da grade.
    Saida:
        dicionario com "tabela" (DataFrame longo: rf_ohm, delta_theta_graus,
        offset_km) e "x1_ref_ohm_km".
    """
    pasta_saida = Path(pasta_saida)
    pasta_saida.mkdir(parents=True, exist_ok=True)

    dados_geo = ge.calcular_parametros_sequencia_losangular_cemig()
    z1 = complex(dados_geo["r1_ohm_km"], dados_geo["x1_ohm_km"])
    x1_ref = dados_geo["x1_ohm_km"]
    modulo_z0 = abs(complex(dados_geo["r0_ohm_km"], dados_geo["x0_ohm_km"]))
    angulo_z1 = cmath.phase(z1)

    rf_valores = np.linspace(0.01, rf_max_ohm, resolucao)
    delta_theta_valores = np.linspace(-delta_theta_max_graus, delta_theta_max_graus, resolucao)
    grade_rf, grade_dtheta = np.meshgrid(rf_valores, delta_theta_valores)
    grade_offset = np.zeros_like(grade_rf)

    linhas = []
    for i in range(grade_rf.shape[0]):
        for j in range(grade_rf.shape[1]):
            rf_ohm = grade_rf[i, j]
            delta_theta_graus = grade_dtheta[i, j]
            z0_variado = modulo_z0 * cmath.exp(1j * (angulo_z1 + math.radians(delta_theta_graus)))
            c = mr.fator_c(z1, z0_variado)
            offset_km = rf_ohm * c.imag / x1_ref
            grade_offset[i, j] = offset_km
            linhas.append({"rf_ohm": rf_ohm, "delta_theta_graus": delta_theta_graus, "offset_km": offset_km})
    tabela = pd.DataFrame(linhas)
    tabela.to_csv(pasta_saida / "efeito_rf_trifasico_3d.csv", index=False)

    graficos.aplicar_estilo_padrao()
    fig = plt.figure(figsize=(8, 6.5))
    eixo = fig.add_subplot(projection="3d")
    superficie = eixo.plot_surface(grade_rf, grade_dtheta, grade_offset, cmap="viridis",
                                    linewidth=0, antialiased=True, alpha=0.95)
    eixo.set_xlabel("Rf (Ω)")
    eixo.set_ylabel("Ângulo(Z0) − Ângulo(Z1) (graus)")
    eixo.set_zlabel("Offset na distância (km)")
    fig.colorbar(superficie, ax=eixo, shrink=0.6, pad=0.1, label="Offset (km)")
    graficos.salvar_figura(
        fig, pasta_saida / "efeito_rf_trifasico_3d.png",
        "Offset na distância estimada (compensação K0) em função de Rf e da diferença angular entre Z0 e Z1."
    )
    return {"tabela": tabela, "x1_ref_ohm_km": x1_ref}


def executar_efeito_resistencia_falta(pasta_saida: Path) -> dict:
    """
    Executa a secao 5 completa: efeito de Rf no trecho monofasico (10
    barras, 4 valores de Rf) e a superficie 3D do trecho trifasico (Rf x
    diferenca angular Z0/Z1 x offset na distancia).

    Entradas:
        pasta_saida: pasta de resultados desta secao (sera criada se nao existir).
    Saida:
        dicionario com "monofasico" e "trifasico_3d" (resultados de cada parte).
    """
    pasta_saida = Path(pasta_saida)
    pasta_saida.mkdir(parents=True, exist_ok=True)
    monofasico = executar_efeito_rf_monofasico(pasta_saida / "monofasico")
    trifasico_3d = executar_efeito_rf_trifasico_3d(pasta_saida / "trifasico")
    return {"monofasico": monofasico, "trifasico_3d": trifasico_3d}
