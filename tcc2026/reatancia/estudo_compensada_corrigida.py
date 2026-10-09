"""
Secao 6b: metodo da reatancia aparente com compensacao de sequencia zero
(K0) e correcao do offset de resistencia de falta, aplicado a barras de
ramificacao, barras folha e barras aleatorias do alimentador completo
(JMLT310 reduzido) — mesma amostragem e estrutura da Secao 6a (Takagi).
"""
import random
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from tcc2026.extracao import extrator_trecho as et
from tcc2026.nucleo import (amostragem_barras as ab, dss_core, geometria_eletrica as ge,
                             graficos, grafo_alimentador as ga, latex_utils, metricas,
                             varredura_falta_rele as vf)
from tcc2026.reatancia import metodo_reatancia as mr

RF_PADRAO_OHM = 0.01
QUANTIDADE_GRAFICO = 20
QUANTIDADE_TABELA_ALEATORIA = 100
SEMENTE_ALEATORIA = 42


def preparar_amostras_e_medidas(pasta_saida: Path, rf_ohm: float = RF_PADRAO_OHM) -> dict:
    """
    Prepara uma copia do alimentador completo com a geometria Cemig
    aplicada as linhas trifasicas, classifica as barras MT e mede
    tensao/corrente no rele (antes/depois da falta) para todas elas.

    Entradas:
        pasta_saida: pasta de resultados desta secao.
        rf_ohm: resistencia de falta usada em todas as simulacoes (ohms).
    Saida:
        dicionario com "medidas", "categorias", "x1_ref_ohm_km", "k0_corrigido".
    """
    # Aquece o cache ANTES de compilar qualquer alimentador real: o calculo
    # usa um circuito OpenDSS auxiliar que substituiria (singleton COM) o
    # alimentador que estiver compilado no momento da chamada.
    ge.calcular_parametros_sequencia_losangular_cemig()

    dss0 = dss_core.compilar_alimentador()
    dss_core.definir_modo_instantaneo(dss0)
    dss_core.resolver_fluxo_potencia(dss0)
    grafo_completo = ga.componente_conexa_da_origem(ga.construir_grafo_eletrico(dss0), ga.obter_barra_origem(dss0))
    origem0 = ga.obter_barra_origem(dss0)
    caminho_master = et.extrair_subalimentador(
        dss0, origem0, set(grafo_completo.nodes), pasta_saida / "alimentador_geometria_cemig",
        "JMLT310_GEOM_REAT", usar_geometria_cemig_trifasica=True)

    dss = et.compilar_subalimentador(caminho_master)
    dss_core.definir_modo_instantaneo(dss)
    dss_core.resolver_fluxo_potencia(dss)

    grafo = ga.componente_conexa_da_origem(ga.construir_grafo_eletrico(dss), ga.obter_barra_origem(dss))
    origem = ga.obter_barra_origem(dss)
    barras_mt = sorted(ga.barras_de_media_tensao(grafo) - {origem})
    categorias = {b: c for b, c in ga.classificar_barras(grafo, origem).items() if b in set(barras_mt)}

    medidas = vf.executar_varredura(dss, grafo, origem, barras_mt, rf_ohm)

    x1_ref = mr.x1_medio_ponderado_trecho(dss, grafo)
    dados_geo = ge.calcular_parametros_sequencia_losangular_cemig()
    z1 = complex(dados_geo["r1_ohm_km"], dados_geo["x1_ohm_km"])
    z0 = complex(dados_geo["r0_ohm_km"], dados_geo["x0_ohm_km"])
    z0_corrigido = mr.z0_corrigido_para_anular_offset(z1, z0)
    k0_corrigido = mr.fator_compensacao_k0(z1, z0_corrigido)

    return {"medidas": medidas, "categorias": categorias, "x1_ref_ohm_km": x1_ref, "k0_corrigido": k0_corrigido}


def montar_resultados(preparo: dict) -> pd.DataFrame:
    """
    Calcula a distancia estimada pelo metodo da reatancia compensada e
    corrigida para cada barra medida.

    Entradas:
        preparo: dicionario devolvido por preparar_amostras_e_medidas.
    Saida:
        DataFrame com barra, distancia_real_km, distancia_estimada_km.
    """
    medidas = preparo["medidas"].copy()
    k0_corrigido = preparo["k0_corrigido"]
    x1_ref = preparo["x1_ref_ohm_km"]

    medidas["distancia_estimada_km"] = medidas.apply(
        lambda linha: mr.distancia_reatancia_compensada(
            linha["va_pos"],
            mr.corrente_compensada(linha["ia_pos"], linha["i0_pos"], k0_corrigido),
            x1_ref,
        ), axis=1
    )
    return medidas


def executar_amostragem_e_estudo(pasta_saida: Path) -> dict:
    """
    Executa a Secao 6b completa: prepara o alimentador, mede todas as
    barras MT, estima a distancia pelo metodo da reatancia compensada e
    corrigida, separa por categoria (ramificacao/folha/aleatoria/global),
    gera graficos (20 barras por categoria) e a tabela de metricas
    (populacao completa).

    Entradas:
        pasta_saida: pasta de resultados desta secao (sera criada se nao existir).
    Saida:
        dicionario com "tabela" (resultados completos) e "tabela_metricas".
    """
    pasta_saida = Path(pasta_saida)
    pasta_saida.mkdir(parents=True, exist_ok=True)

    preparo = preparar_amostras_e_medidas(pasta_saida)
    tabela = montar_resultados(preparo)
    tabela.drop(columns=["va_pos", "ia_pre", "ia_pos", "i0_pre", "i0_pos"]).to_csv(
        pasta_saida / "reatancia_compensada_resultados.csv", index=False)

    categorias = preparo["categorias"]
    distancias = dict(zip(tabela["barra"], tabela["distancia_real_km"]))
    barras_ramificacao = set(ab.selecionar_barras_ramificacao(categorias, distancias, quantidade=10 ** 9))
    barras_folha = set(ab.selecionar_barras_folha(categorias, distancias, quantidade=10 ** 9))
    gerador = random.Random(SEMENTE_ALEATORIA)
    barras_aleatorias_tabela = set(gerador.sample(
        list(tabela["barra"]), min(QUANTIDADE_TABELA_ALEATORIA, len(tabela))))

    grupos = {
        "Ramificação": tabela[tabela["barra"].isin(barras_ramificacao)],
        "Folha": tabela[tabela["barra"].isin(barras_folha)],
        "Aleatória": tabela[tabela["barra"].isin(barras_aleatorias_tabela)],
        "Global (todas as barras)": tabela,
    }

    linhas_metricas = []
    for rotulo, sub in grupos.items():
        m = metricas.resumo_metricas(sub["distancia_real_km"].to_numpy(), sub["distancia_estimada_km"].to_numpy(),
                                      sub["distancia_real_km"].max())
        m["grupo"] = rotulo
        m["n_barras"] = len(sub)
        linhas_metricas.append(m)
    tabela_metricas = pd.DataFrame(linhas_metricas)[
        ["grupo", "n_barras", "mae_km", "rmse_km", "r2", "erro_max_km",
         "erro_medio_km", "desvio_padrao_km"]]
    tabela_metricas.to_csv(pasta_saida / "reatancia_compensada_metricas.csv", index=False)
    latex_utils.salvar_tabela_latex(
        tabela_metricas.rename(columns={
            "grupo": "Grupo", "n_barras": "N", "mae_km": "MAE (km)", "rmse_km": "RMSE (km)", "r2": "R²",
            "erro_max_km": "Erro Máx. (km)", "erro_medio_km": "Erro Médio (km)",
            "desvio_padrao_km": "Desvio Padrão (km)",
        }),
        pasta_saida / "reatancia_compensada_metricas.txt",
        legenda="Erros do método da reatância compensada e corrigida, por grupo de barras (JMLT310 reduzido)",
        rotulo="reatancia_compensada_metricas",
        contexto="Secao 6b - metricas do metodo da reatancia com compensacao K0 e correcao do offset, populacao completa de cada grupo.",
        decimais={"N": 0, "MAE (km)": 4, "RMSE (km)": 4, "R²": 4, "Erro Máx. (km)": 4,
                  "Erro Médio (km)": 4, "Desvio Padrão (km)": 4},
        alinhamento="lccccccc",
    )

    graficos.aplicar_estilo_padrao()
    especificacoes_dispersao = [
        ("Ramificação", barras_ramificacao, "reatancia_compensada_ramificacao.png",
         "Distância real x estimada (reatância compensada e corrigida) em 20 barras de ramificação."),
        ("Folha", barras_folha, "reatancia_compensada_folha.png",
         "Distância real x estimada (reatância compensada e corrigida) em 20 barras folha."),
        ("Aleatória", set(gerador.sample(list(tabela["barra"]), min(20, len(tabela)))),
         "reatancia_compensada_aleatoria.png",
         "Distância real x estimada (reatância compensada e corrigida) em 20 barras aleatórias (semente fixa)."),
    ]
    for rotulo, conjunto, nome_arquivo, descricao in especificacoes_dispersao:
        sub_completo = tabela[tabela["barra"].isin(conjunto)]
        sub_grafico = sub_completo.sort_values("distancia_real_km")
        if len(sub_grafico) > QUANTIDADE_GRAFICO:
            sub_grafico = sub_grafico.iloc[
                sorted({round(i * (len(sub_grafico) - 1) / (QUANTIDADE_GRAFICO - 1)) for i in range(QUANTIDADE_GRAFICO)})]
        limite = max(sub_grafico["distancia_real_km"].max(), sub_grafico["distancia_estimada_km"].max()) * 1.1
        fig, eixo = plt.subplots(figsize=(5.5, 5.5))
        sns.scatterplot(data=sub_grafico, x="distancia_real_km", y="distancia_estimada_km", ax=eixo,
                         s=60, color="#2f855a")
        eixo.plot([0, limite], [0, limite], linestyle="--", color="gray", linewidth=1)
        eixo.set_xlabel("Distância real (km)")
        eixo.set_ylabel("Distância estimada (km)")
        sns.despine(ax=eixo)
        graficos.salvar_figura(fig, pasta_saida / nome_arquivo, descricao)

    tabela_boxplot = pd.concat([sub.assign(grupo=rotulo) for rotulo, sub in grupos.items()], ignore_index=True)
    tabela_boxplot["erro_km"] = tabela_boxplot["distancia_estimada_km"] - tabela_boxplot["distancia_real_km"]
    fig, eixo = plt.subplots(figsize=(8, 4.5))
    sns.boxplot(data=tabela_boxplot, x="grupo", y="erro_km", ax=eixo, color="#9ae6b4")
    eixo.axhline(0, color="gray", linewidth=1, linestyle="--")
    eixo.set_xlabel("")
    eixo.set_ylabel("Erro (km)")
    sns.despine(ax=eixo)
    graficos.salvar_figura(
        fig, pasta_saida / "reatancia_compensada_boxplot.png",
        "Distribuição do erro (estimado − real) do método da reatância compensada e corrigida, pelos 4 grupos de barras."
    )

    return {"tabela": tabela, "tabela_metricas": tabela_metricas}
