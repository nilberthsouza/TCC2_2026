"""
Secao 4: trecho trifasico do JMLT310 — extracao do mini-alimentador, fluxo
de potencia, curva horaria e metodo da reatancia aparente em 5 variantes
(com/sem carga, com/sem compensacao de sequencia zero K0, e compensacao
com correcao do offset de resistencia de falta).
"""
from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx
import pandas as pd
import seaborn as sns

from tcc2026.extracao import extrator_trecho as et
from tcc2026.nucleo import (dss_core, falta_injecao as fi, geometria_eletrica as ge,
                             graficos, grafo_alimentador as ga, latex_utils, metricas)
from tcc2026.reatancia import metodo_reatancia as mr

RF_PADRAO_OHM = 0.01

RUBRICA_METODOS = {
    "original_sem_carga": "Sem compensação, sem cargas",
    "original_com_carga": "Sem compensação, com cargas",
    "compensado_sem_carga": "Compensação K0, sem cargas",
    "compensado_com_carga": "Compensação K0, com cargas",
    "compensado_corrigido_sem_carga": "Compensação K0 + correção exata do offset, sem cargas",
}


def extrair_trecho(pasta_saida: Path) -> dict:
    """
    Seleciona automaticamente um trecho trifasico pequeno e diverso e
    extrai o mini-alimentador correspondente.

    Entradas:
        pasta_saida: pasta onde o mini-alimentador extraido sera escrito.
    Saida:
        dicionario com barra_raiz, caminho_master, grafo_completo, barras_sub.
    """
    dss = dss_core.compilar_alimentador()
    dss_core.definir_modo_instantaneo(dss)
    dss_core.resolver_fluxo_potencia(dss)
    grafo_completo = ga.componente_conexa_da_origem(ga.construir_grafo_eletrico(dss), ga.obter_barra_origem(dss))
    origem_completo = ga.obter_barra_origem(dss)
    barra_raiz = ga.selecionar_trecho_trifasico_pequeno(grafo_completo, origem_completo)
    barras_sub = ga.subarvore_a_partir_de(grafo_completo, origem_completo, barra_raiz)
    caminho_master = et.extrair_subalimentador(
        dss, barra_raiz, barras_sub, pasta_saida / "subalimentador", "MINI_3F",
        usar_geometria_cemig_trifasica=True)
    return {
        "barra_raiz": barra_raiz, "caminho_master": caminho_master,
        "grafo_completo": grafo_completo, "origem_completo": origem_completo, "barras_sub": barras_sub,
    }


def fluxo_e_curvas(caminho_master: Path, pasta_saida: Path) -> dict:
    """
    Resolve o fluxo de potencia do mini-alimentador trifasico e simula a
    curva horaria (24h), salvando resumo/curva em CSV e um grafico seaborn
    separado por grandeza.

    Entradas:
        caminho_master: Path do Master do mini-alimentador extraido.
        pasta_saida: pasta de resultados desta secao.
    Saida:
        dicionario com "resumo" (dict) e "curva" (DataFrame).
    """
    dss = et.compilar_subalimentador(caminho_master)
    dss_core.definir_modo_instantaneo(dss)
    if not dss_core.resolver_fluxo_potencia(dss):
        raise RuntimeError("Fluxo de potencia do trecho trifasico nao convergiu.")
    resumo = dss_core.resumo_potencia_e_perdas(dss)
    pd.DataFrame([resumo]).to_csv(pasta_saida / "fluxo_potencia_resumo.csv", index=False)

    dss2 = et.compilar_subalimentador(caminho_master)
    curva = dss_core.simular_dia_horario(dss2, horas=24)
    curva.to_csv(pasta_saida / "curva_horaria.csv", index=False)

    graficos.aplicar_estilo_padrao()
    especificacoes = [
        ("p_ativa_kw", "Potência ativa (kW)", "curva_potencia_ativa.png",
         "Curva horária de potência ativa do trecho trifásico extraído (kW), 24 h."),
        ("p_reativa_kvar", "Potência reativa (kvar)", "curva_potencia_reativa.png",
         "Curva horária de potência reativa do trecho trifásico extraído (kvar), 24 h."),
        ("perdas_ativa_kw", "Perdas ativas (kW)", "curva_perdas.png",
         "Curva horária de perdas ativas do trecho trifásico extraído (kW), 24 h."),
        ("tensao_media_pu", "Tensão média (pu)", "curva_tensao_media.png",
         "Curva horária da tensão média nas barras do trecho trifásico extraído (pu), 24 h."),
    ]
    for coluna, rotulo_y, nome_arquivo, descricao in especificacoes:
        fig, eixo = plt.subplots(figsize=(7, 3.5))
        sns.lineplot(data=curva, x="hora", y=coluna, marker="o", ax=eixo, color="#2b6cb0")
        eixo.set_xlabel("Hora")
        eixo.set_ylabel(rotulo_y)
        sns.despine(ax=eixo)
        graficos.salvar_figura(fig, pasta_saida / nome_arquivo, descricao)
    return {"resumo": resumo, "curva": curva}


def executar_varredura_reatancia_5_variantes(caminho_master: Path, rf_ohm: float = RF_PADRAO_OHM) -> dict:
    """
    Para cada barra MT do trecho trifasico, aplica uma falta monofasica-
    terra (fase A) com e sem cargas, e estima a distancia pelas 5
    variantes do metodo da reatancia (ver RUBRICA_METODOS).

    Entradas:
        caminho_master: Path do Master do mini-alimentador extraido.
        rf_ohm: resistencia de falta usada em todas as simulacoes (ohms).
    Saida:
        dicionario com "tabela" (DataFrame longo: barra, metodo,
        distancia_real_km, distancia_estimada_km), "x1_ref_ohm_km",
        "z1_geo_ohm_km", "z0_geo_ohm_km", "distancia_tronco_km".
    """
    dados_geo = ge.calcular_parametros_sequencia_losangular_cemig()
    z1_geo = complex(dados_geo["r1_ohm_km"], dados_geo["x1_ohm_km"])
    z0_geo = complex(dados_geo["r0_ohm_km"], dados_geo["x0_ohm_km"])
    k0 = mr.fator_compensacao_k0(z1_geo, z0_geo)

    dss = et.compilar_subalimentador(caminho_master)
    dss_core.definir_modo_instantaneo(dss)
    dss_core.resolver_fluxo_potencia(dss)

    grafo = ga.componente_conexa_da_origem(ga.construir_grafo_eletrico(dss), ga.obter_barra_origem(dss))
    origem = ga.obter_barra_origem(dss)
    distancias = ga.distancias_desde_origem(grafo, origem)
    barras_mt = sorted(ga.barras_de_media_tensao(grafo) - {origem})
    x1_ref = mr.x1_medio_ponderado_trecho(dss, grafo)

    fi.preparar_elemento_falta(dss)

    linhas = []
    for barra in barras_mt:
        dss.circuit.set_active_bus(barra)
        fase_barra = int(dss.bus.nodes[0])
        for cenario, aplicar_cenario in (("sem_carga", fi.desligar_todas_as_cargas),
                                          ("com_carga", fi.religar_todas_as_cargas)):
            aplicar_cenario(dss)
            fi.aplicar_falta_monofasica(dss, barra, fase_barra, rf_ohm)
            dss.text("solve")
            if dss.solution.converged:
                medidas = fi.medir_tensoes_correntes_trifasicas_rele(dss, origem)
                va = medidas["tensoes"][fase_barra]
                ia = medidas["correntes"][fase_barra]
                i0 = mr.corrente_sequencia_zero(medidas["correntes"])

                d_original = mr.distancia_reatancia_simples(va, ia, x1_ref)
                linhas.append({"barra": barra, "metodo": f"original_{cenario}",
                                "distancia_real_km": distancias[barra], "distancia_estimada_km": d_original})

                ia_comp = mr.corrente_compensada(ia, i0, k0)
                d_compensado = mr.distancia_reatancia_compensada(va, ia_comp, x1_ref)
                linhas.append({"barra": barra, "metodo": f"compensado_{cenario}",
                                "distancia_real_km": distancias[barra], "distancia_estimada_km": d_compensado})

                if cenario == "sem_carga":
                    d_corrigido = mr.distancia_reatancia_corrigida_exata(va, ia_comp, z1_geo, z0_geo)
                    linhas.append({"barra": barra, "metodo": "compensado_corrigido_sem_carga",
                                    "distancia_real_km": distancias[barra], "distancia_estimada_km": d_corrigido})
            fi.remover_falta(dss)
    fi.religar_todas_as_cargas(dss)

    return {
        "tabela": pd.DataFrame(linhas),
        "x1_ref_ohm_km": x1_ref,
        "z1_geo_ohm_km": z1_geo,
        "z0_geo_ohm_km": z0_geo,
        "distancia_tronco_km": max(distancias.values()),
    }


def gerar_metricas_e_graficos(resultado_varredura: dict, pasta_saida: Path) -> pd.DataFrame:
    """
    Calcula as metricas de erro por variante do metodo e gera o grafico de
    dispersao (real x estimado, todas as variantes) e o boxplot comparativo
    dos erros.

    Entradas:
        resultado_varredura: dicionario devolvido por
            executar_varredura_reatancia_5_variantes.
        pasta_saida: pasta de resultados desta secao.
    Saida:
        DataFrame com as metricas por variante.
    """
    tabela = resultado_varredura["tabela"].copy()
    tabela["rotulo_metodo"] = tabela["metodo"].map(RUBRICA_METODOS)
    tabela["erro_km"] = tabela["distancia_estimada_km"] - tabela["distancia_real_km"]
    tabela.to_csv(pasta_saida / "reatancia_resultados.csv", index=False)
    comprimento_base = resultado_varredura["distancia_tronco_km"]

    linhas_metricas = []
    for chave_metodo, rotulo in RUBRICA_METODOS.items():
        sub = tabela[tabela["metodo"] == chave_metodo]
        m = metricas.resumo_metricas(sub["distancia_real_km"].to_numpy(), sub["distancia_estimada_km"].to_numpy(),
                                      comprimento_base)
        m["metodo"] = rotulo
        linhas_metricas.append(m)
    tabela_metricas = pd.DataFrame(linhas_metricas)[
        ["metodo", "mae_km", "rmse_km", "r2", "erro_max_km", "erro_max_pct",
         "erro_medio_km", "erro_medio_pct", "desvio_padrao_km"]]
    tabela_metricas.to_csv(pasta_saida / "reatancia_metricas.csv", index=False)
    latex_utils.salvar_tabela_latex(
        tabela_metricas.rename(columns={
            "metodo": "Método", "mae_km": "MAE (km)", "rmse_km": "RMSE (km)", "r2": "R²",
            "erro_max_km": "Erro Máx. (km)", "erro_max_pct": "Erro Máx. (\\%)",
            "erro_medio_km": "Erro Médio (km)", "erro_medio_pct": "Erro Médio (\\%)",
            "desvio_padrao_km": "Desvio Padrão (km)",
        }),
        pasta_saida / "reatancia_metricas.txt",
        legenda="Erros das 5 variantes do método da reatância no trecho trifásico",
        rotulo="reatancia_3f_metricas",
        contexto="Secao 4 - metricas de erro das 5 variantes do metodo da reatancia no trecho trifasico.",
        decimais=4, alinhamento="lcccccccc",
    )

    graficos.aplicar_estilo_padrao()
    limite = max(tabela["distancia_real_km"].max(), tabela["distancia_estimada_km"].max()) * 1.08
    fig, eixo = plt.subplots(figsize=(7, 6))
    sns.scatterplot(data=tabela, x="distancia_real_km", y="distancia_estimada_km",
                     hue="rotulo_metodo", style="rotulo_metodo", ax=eixo, s=55)
    eixo.plot([0, limite], [0, limite], linestyle="--", color="gray", linewidth=1)
    eixo.set_xlabel("Distância real (km)")
    eixo.set_ylabel("Distância estimada (km)")
    eixo.legend(title="", fontsize=8, loc="upper left")
    sns.despine(ax=eixo)
    graficos.salvar_figura(
        fig, pasta_saida / "reatancia_real_vs_estimado.png",
        "Distância real x estimada no trecho trifásico, para as 5 variantes do método da reatância."
    )

    fig, eixo = plt.subplots(figsize=(9, 4.5))
    sns.boxplot(data=tabela, x="rotulo_metodo", y="erro_km", ax=eixo, color="#90cdf4")
    eixo.axhline(0, color="gray", linewidth=1, linestyle="--")
    eixo.set_xlabel("")
    eixo.set_ylabel("Erro (km)")
    eixo.tick_params(axis="x", labelrotation=20)
    sns.despine(ax=eixo)
    graficos.salvar_figura(
        fig, pasta_saida / "reatancia_boxplot.png",
        "Distribuição do erro (estimado − real) das 5 variantes do método da reatância, lado a lado."
    )
    return tabela_metricas


def plotar_mapas_trecho(grafo_completo, barras_sub: set, pasta_saida: Path) -> None:
    """
    Gera um grafico esquematico so do trecho trifasico extraido e outro
    com o trecho destacado dentro da topologia completa do alimentador.

    Entradas:
        grafo_completo: grafo eletrico completo (componente conexo da origem).
        barras_sub: conjunto de barras do trecho trifasico extraido.
        pasta_saida: pasta de resultados desta secao.
    Saida:
        nenhuma (salva os dois .png em pasta_saida).
    """
    graficos.aplicar_estilo_padrao()

    subgrafo = grafo_completo.subgraph(barras_sub)
    pos_sub = nx.spring_layout(subgrafo, seed=42)
    fig, eixo = plt.subplots(figsize=(6, 6))
    nx.draw_networkx_edges(subgrafo, pos_sub, ax=eixo, edge_color="#a0aec0")
    nx.draw_networkx_nodes(subgrafo, pos_sub, ax=eixo, node_size=70, node_color="#2b6cb0")
    eixo.axis("off")
    graficos.salvar_figura(
        fig, pasta_saida / "trecho_isolado.png",
        "Topologia esquemática (layout de grafo, não geográfico) do trecho trifásico extraído."
    )

    pos_total = nx.spring_layout(grafo_completo, seed=42, k=0.15, iterations=50)
    cores = ["#c53030" if n in barras_sub else "#cbd5e0" for n in grafo_completo.nodes]
    tamanhos = [40 if n in barras_sub else 8 for n in grafo_completo.nodes]
    fig, eixo = plt.subplots(figsize=(8, 8))
    nx.draw_networkx_edges(grafo_completo, pos_total, ax=eixo, edge_color="#e2e8f0", width=0.5)
    nx.draw_networkx_nodes(grafo_completo, pos_total, ax=eixo, node_size=tamanhos, node_color=cores)
    eixo.axis("off")
    graficos.salvar_figura(
        fig, pasta_saida / "trecho_destacado_no_alimentador.png",
        "Trecho trifásico (vermelho) destacado na topologia completa do alimentador (layout esquemático)."
    )


def executar_estudo_trifasico(pasta_saida: Path) -> dict:
    """
    Executa a secao 4 completa: extracao do trecho trifasico, fluxo de
    potencia, curva horaria, varredura das 5 variantes do metodo da
    reatancia, metricas e graficos.

    Entradas:
        pasta_saida: pasta de resultados desta secao (sera criada se nao existir).
    Saida:
        dicionario com "extracao", "fluxo_curvas", "varredura", "tabela_metricas".
    """
    pasta_saida = Path(pasta_saida)
    pasta_saida.mkdir(parents=True, exist_ok=True)

    extracao = extrair_trecho(pasta_saida)
    fluxo_curvas = fluxo_e_curvas(extracao["caminho_master"], pasta_saida)
    varredura = executar_varredura_reatancia_5_variantes(extracao["caminho_master"])
    tabela_metricas = gerar_metricas_e_graficos(varredura, pasta_saida)
    plotar_mapas_trecho(extracao["grafo_completo"], extracao["barras_sub"], pasta_saida)

    return {
        "extracao": extracao, "fluxo_curvas": fluxo_curvas,
        "varredura": varredura, "tabela_metricas": tabela_metricas,
    }
