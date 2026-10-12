"""
Secao 9: analise dos linecodes (condutores) reais do alimentador JMLT310.

Duas tabelas complementares:
1. Ranking dos linecodes por quilometragem total no alimentador (distancia
   absoluta e percentual) -- "quais condutores sao mais representativos".
2. Para os metodos de Takagi e reatancia compensada e corrigida (Secoes 6a
   e 6b, resultados ja calculados sobre as 300 barras MT), o linecode do
   ultimo segmento antes de cada barra de falta e correlacionado com o erro
   observado naquela barra -- "quais condutores aparecem mais associados a
   erro", cruzando com o ranking por quilometragem (1) para saber se sao
   condutores raros ou comuns no alimentador.

Para os piores casos, fornece as coordenadas (longitude, latitude) das
barras do segmento, para inspecao visual (Google Street View) do tipo real
de condutor (cabo nu x isolado, bitola aparente etc.) -- fora do escopo
deste pipeline automatizado, mas como insumo para validacao manual.
"""
from pathlib import Path

import pandas as pd

from tcc2026.nucleo import dss_core, grafo_alimentador as ga, latex_utils, mapa_geografico as mg

QUANTIDADE_PIORES = 10
QUANTIDADE_COORDENADAS = 8


def montar_grafo_real() -> dict:
    """
    Compila o alimentador reduzido SEM a correcao de geometria Cemig (ou
    seja, com os linecodes originais da BDGD preservados em cada Line) e
    monta o grafo eletrico correspondente, para uso nesta analise.

    Entradas:
        nenhuma.
    Saida:
        dicionario com "dss", "grafo", "origem", "coordenadas"
        ({barra: (longitude, latitude)}, ver mapa_geografico.carregar_coordenadas).
    """
    dss = dss_core.compilar_alimentador(aplicar_impedancia_real=False)
    dss_core.definir_modo_instantaneo(dss)
    dss_core.resolver_fluxo_potencia(dss)
    grafo = ga.componente_conexa_da_origem(ga.construir_grafo_eletrico(dss), ga.obter_barra_origem(dss))
    origem = ga.obter_barra_origem(dss)
    coordenadas = mg.carregar_coordenadas()
    return {"dss": dss, "grafo": grafo, "origem": origem, "coordenadas": coordenadas}


def montar_tabela_linecodes_por_km(dss) -> pd.DataFrame:
    """
    Soma o comprimento total (km) de cada linecode presente nas linhas MT
    do alimentador compilado, e calcula o percentual sobre o comprimento
    total.

    Entradas:
        dss: instancia do motor OpenDSS com o alimentador real compilado
            (ver montar_grafo_real, SEM a geometria Cemig).
    Saida:
        DataFrame com colunas "rank", "linecode", "km", "pct", ordenado por
        km decrescente.
    """
    linhas = dss.lines
    codigos: dict[str, float] = {}
    for nome in linhas.names:
        linhas.name = nome
        codigo = linhas.linecode
        comprimento = float(linhas.length)
        if not codigo:
            continue
        codigos[codigo] = codigos.get(codigo, 0.0) + comprimento
    total_km = sum(codigos.values())
    tabela = pd.DataFrame([
        {"linecode": codigo, "km": km, "pct": 100.0 * km / total_km}
        for codigo, km in codigos.items()
    ]).sort_values("km", ascending=False).reset_index(drop=True)
    tabela.insert(0, "rank", tabela.index + 1)
    return tabela


def linecode_do_ultimo_segmento(grafo, origem: str, barra: str) -> dict:
    """
    Identifica o linecode, o comprimento e as barras extremas do ultimo
    segmento de linha (mais proximo da barra de falta) no caminho
    rele-barra -- o segmento cuja impedancia real tem maior influencia
    relativa na medicao, por estar mais perto do ponto de falta.

    Entradas:
        grafo: grafo eletrico do alimentador real (ver montar_grafo_real).
        origem: barra de origem (posicao do rele).
        barra: barra de falta de interesse.
    Saida:
        dicionario com "linecode", "comprimento_km", "fases", "barra_de"
        barra_para" (None em todos os campos se a barra for a propria
        origem ou nao houver segmento de linha no caminho).
    """
    caminho = ga.caminho_entre_barras(grafo, origem, barra)
    for a, b in zip(reversed(caminho[:-1]), reversed(caminho[1:])):
        dados = grafo.edges[a, b]
        if dados["tipo"] == "linha":
            return {"linecode": dados["linecode"], "comprimento_km": dados["comprimento_km"],
                    "fases": dados["fases"], "barra_de": a, "barra_para": b}
    return {"linecode": None, "comprimento_km": None, "fases": None, "barra_de": None, "barra_para": None}


def montar_tabela_erro_por_linecode(tabela_resultados: pd.DataFrame, grafo, origem: str) -> pd.DataFrame:
    """
    Para cada barra de falta de uma tabela de resultados (Takagi ou
    reatancia compensada e corrigida, Secoes 6a/6b), identifica o linecode
    do ultimo segmento do caminho rele-barra e agrega o erro por linecode.

    Entradas:
        tabela_resultados: DataFrame com colunas "barra", "distancia_real_km",
            "distancia_estimada_km" (ver takagi_resultados.csv /
            reatancia_compensada_resultados.csv).
        grafo: grafo eletrico do alimentador real (ver montar_grafo_real).
        origem: barra de origem (posicao do rele).
    Saida:
        DataFrame com colunas "linecode", "mae_km", "erro_medio_km",
        "erro_max_abs_km", "n_barras", ordenado por mae_km decrescente.
    """
    tabela = tabela_resultados.copy()
    tabela["erro_km"] = tabela["distancia_estimada_km"] - tabela["distancia_real_km"]
    tabela["linecode"] = tabela["barra"].apply(
        lambda b: linecode_do_ultimo_segmento(grafo, origem, b)["linecode"])
    agrupado = tabela.groupby("linecode")["erro_km"].agg(
        mae_km=lambda s: s.abs().mean(), erro_medio_km="mean",
        erro_max_abs_km=lambda s: s.abs().max(), n_barras="count")
    return agrupado.sort_values("mae_km", ascending=False).reset_index()


def montar_tabela_comparativa_piores_linecodes(tabela_km: pd.DataFrame, tabela_erro_takagi: pd.DataFrame,
                                                tabela_erro_reatancia: pd.DataFrame,
                                                quantidade: int = QUANTIDADE_PIORES) -> pd.DataFrame:
    """
    Combina os piores linecodes (maior MAE) de Takagi e reatancia em uma
    unica lista (uniao dos top `quantidade` de cada metodo), e cruza com o
    ranking por quilometragem (tabela_km) para mostrar a posicao e a
    representatividade de cada linecode no alimentador.

    Entradas:
        tabela_km: DataFrame devolvido por montar_tabela_linecodes_por_km.
        tabela_erro_takagi, tabela_erro_reatancia: DataFrames devolvidos
            por montar_tabela_erro_por_linecode para cada metodo.
        quantidade: quantos piores linecodes considerar de cada metodo
            antes de unir as duas listas.
    Saida:
        DataFrame com colunas "linecode", "rank_km", "km", "pct_km",
        "mae_takagi_km", "n_barras_takagi", "mae_reatancia_km",
        "n_barras_reatancia", ordenado pela media dos dois MAE.
    """
    piores_takagi = set(tabela_erro_takagi.head(quantidade)["linecode"])
    piores_reatancia = set(tabela_erro_reatancia.head(quantidade)["linecode"])
    linecodes_interesse = piores_takagi | piores_reatancia

    km_indexado = tabela_km.set_index("linecode")
    takagi_indexado = tabela_erro_takagi.set_index("linecode")
    reatancia_indexado = tabela_erro_reatancia.set_index("linecode")

    linhas = []
    for linecode in linecodes_interesse:
        linha_km = km_indexado.loc[linecode] if linecode in km_indexado.index else None
        linha_takagi = takagi_indexado.loc[linecode] if linecode in takagi_indexado.index else None
        linha_reatancia = reatancia_indexado.loc[linecode] if linecode in reatancia_indexado.index else None
        linhas.append({
            "linecode": linecode,
            "rank_km": int(linha_km["rank"]) if linha_km is not None else None,
            "km": linha_km["km"] if linha_km is not None else 0.0,
            "pct_km": linha_km["pct"] if linha_km is not None else 0.0,
            "mae_takagi_km": linha_takagi["mae_km"] if linha_takagi is not None else float("nan"),
            "n_barras_takagi": int(linha_takagi["n_barras"]) if linha_takagi is not None else 0,
            "mae_reatancia_km": linha_reatancia["mae_km"] if linha_reatancia is not None else float("nan"),
            "n_barras_reatancia": int(linha_reatancia["n_barras"]) if linha_reatancia is not None else 0,
        })
    tabela = pd.DataFrame(linhas)
    tabela["mae_media_km"] = tabela[["mae_takagi_km", "mae_reatancia_km"]].mean(axis=1)
    return tabela.sort_values("mae_media_km", ascending=False).reset_index(drop=True)


def montar_tabela_parametros_linecodes(dss, tabela_comparativa: pd.DataFrame) -> pd.DataFrame:
    """
    Le, diretamente do objeto Linecode do OpenDSS, os parametros eletricos
    (R1/X1/R0/X0/C1/C0/ampacidade/fases) de cada linecode da tabela
    comparativa dos piores casos (sem nenhuma correcao aplicada por este
    trabalho), para permitir uma conferencia visual rapida de valores
    fisicamente implausiveis (possivel erro de preenchimento na BDGD).

    Entradas:
        dss: instancia do motor OpenDSS com o alimentador real compilado
            (ver montar_grafo_real, SEM a geometria Cemig).
        tabela_comparativa: DataFrame devolvido por
            montar_tabela_comparativa_piores_linecodes.
    Saida:
        DataFrame com colunas "linecode", "fases", "r1_ohm_km", "x1_ohm_km",
        "r0_ohm_km", "x0_ohm_km", "c1_nf_km", "c0_nf_km", "normamps",
        "x1_r1", na mesma ordem de tabela_comparativa.
    """
    linecodes = dss.linecodes
    linhas = []
    for codigo in tabela_comparativa["linecode"]:
        linecodes.name = codigo
        r1, x1 = linecodes.r1, linecodes.x1
        linhas.append({
            "linecode": codigo, "fases": linecodes.phases,
            "r1_ohm_km": r1, "x1_ohm_km": x1,
            "r0_ohm_km": linecodes.r0, "x0_ohm_km": linecodes.x0,
            "c1_nf_km": linecodes.c1, "c0_nf_km": linecodes.c0,
            "normamps": linecodes.norm_amps, "x1_r1": x1 / r1 if r1 else float("nan"),
        })
    return pd.DataFrame(linhas)


def montar_tabela_coordenadas(tabela_comparativa: pd.DataFrame, grafo, origem: str, coordenadas: dict,
                               tabela_resultados_referencia: pd.DataFrame,
                               quantidade: int = QUANTIDADE_COORDENADAS) -> pd.DataFrame:
    """
    Para os piores linecodes (tabela_comparativa), localiza um segmento de
    exemplo (barras extremas e coordenadas geograficas) para inspecao
    visual (Google Street View) do condutor real.

    Entradas:
        tabela_comparativa: DataFrame devolvido por
            montar_tabela_comparativa_piores_linecodes.
        grafo, origem: ver montar_grafo_real.
        coordenadas: dicionario {barra: (longitude, latitude)}.
        tabela_resultados_referencia: DataFrame de resultados (Takagi ou
            reatancia) usado so para obter uma barra de falta de exemplo
            associada a cada linecode de interesse.
        quantidade: quantos linecodes (do topo de tabela_comparativa)
            buscar coordenadas.
    Saida:
        DataFrame com colunas "linecode", "barra_falta_exemplo", "barra_de",
        "barra_para", "long_de", "lat_de", "long_para", "lat_para".
    """
    linecodes_alvo = list(tabela_comparativa.head(quantidade)["linecode"])
    linhas = []
    vistos = set()
    for barra in tabela_resultados_referencia["barra"]:
        info = linecode_do_ultimo_segmento(grafo, origem, barra)
        linecode = info["linecode"]
        if linecode not in linecodes_alvo or linecode in vistos:
            continue
        vistos.add(linecode)
        coord_de = coordenadas.get(info["barra_de"])
        coord_para = coordenadas.get(info["barra_para"])
        linhas.append({
            "linecode": linecode, "barra_falta_exemplo": barra,
            "barra_de": info["barra_de"], "barra_para": info["barra_para"],
            "long_de": coord_de[0] if coord_de else None, "lat_de": coord_de[1] if coord_de else None,
            "long_para": coord_para[0] if coord_para else None, "lat_para": coord_para[1] if coord_para else None,
        })
        if len(vistos) >= quantidade:
            break
    return pd.DataFrame(linhas)


def executar_analise_linecodes(pasta_saida: Path, pasta_takagi: Path, pasta_reatancia: Path) -> dict:
    """
    Executa a Secao 9 completa: ranking de linecodes por km, correlacao de
    erro por linecode (Takagi e reatancia compensada e corrigida),
    comparativo dos piores linecodes e coordenadas para inspecao visual.

    Entradas:
        pasta_saida: pasta de resultados desta secao (sera criada se nao existir).
        pasta_takagi: pasta de resultados da Secao 6a (contem
            takagi_resultados.csv).
        pasta_reatancia: pasta de resultados da Secao 6b (contem
            reatancia_compensada_resultados.csv).
    Saida:
        dicionario com "tabela_km", "tabela_erro_takagi",
        "tabela_erro_reatancia", "tabela_comparativa", "tabela_parametros",
        "tabela_coordenadas".
    """
    pasta_saida = Path(pasta_saida)
    pasta_saida.mkdir(parents=True, exist_ok=True)

    contexto = montar_grafo_real()
    grafo, origem = contexto["grafo"], contexto["origem"]

    tabela_km = montar_tabela_linecodes_por_km(contexto["dss"])
    tabela_km.to_csv(pasta_saida / "linecodes_por_km.csv", index=False)
    latex_utils.salvar_tabela_latex(
        tabela_km.rename(columns={"rank": "Rank", "linecode": "Linecode", "km": "km", "pct": "\\% do total"}),
        pasta_saida / "linecodes_por_km.txt",
        legenda="Linecodes do alimentador JMLT310 reduzido, por quilometragem total",
        rotulo="linecodes_por_km",
        contexto="Secao 9 - ranking dos linecodes reais (BDGD) por comprimento total no alimentador.",
        decimais={"Rank": 0, "km": 3, "\\% do total": 2},
        alinhamento="clcc",
    )

    resultados_takagi = pd.read_csv(Path(pasta_takagi) / "takagi_resultados.csv")
    resultados_reatancia = pd.read_csv(Path(pasta_reatancia) / "reatancia_compensada_resultados.csv")

    tabela_erro_takagi = montar_tabela_erro_por_linecode(resultados_takagi, grafo, origem)
    tabela_erro_reatancia = montar_tabela_erro_por_linecode(resultados_reatancia, grafo, origem)
    tabela_erro_takagi.to_csv(pasta_saida / "erro_por_linecode_takagi.csv", index=False)
    tabela_erro_reatancia.to_csv(pasta_saida / "erro_por_linecode_reatancia.csv", index=False)

    tabela_comparativa = montar_tabela_comparativa_piores_linecodes(
        tabela_km, tabela_erro_takagi, tabela_erro_reatancia)
    tabela_comparativa.to_csv(pasta_saida / "piores_linecodes_comparativo.csv", index=False)
    latex_utils.salvar_tabela_latex(
        tabela_comparativa.rename(columns={
            "linecode": "Linecode", "rank_km": "Rank (km)", "km": "km", "pct_km": "\\% do total",
            "mae_takagi_km": "MAE Takagi (km)", "n_barras_takagi": "N (Takagi)",
            "mae_reatancia_km": "MAE Reatância (km)", "n_barras_reatancia": "N (Reatância)",
        }).drop(columns=["mae_media_km"]),
        pasta_saida / "piores_linecodes_comparativo.txt",
        legenda="Linecodes mais associados a erro nos métodos de Takagi e reatância compensada e corrigida, "
                "cruzados com o ranking por quilometragem",
        rotulo="piores_linecodes",
        contexto="Secao 9 - linecodes do ultimo segmento antes da barra de falta, para as barras de maior erro "
                 "em cada metodo (uniao dos 10 piores de cada um).",
        decimais={"Rank (km)": 0, "km": 3, "\\% do total": 2, "MAE Takagi (km)": 4, "N (Takagi)": 0,
                  "MAE Reatância (km)": 4, "N (Reatância)": 0},
        alinhamento="lcccccc",
    )

    tabela_parametros = montar_tabela_parametros_linecodes(contexto["dss"], tabela_comparativa)
    tabela_parametros.to_csv(pasta_saida / "parametros_piores_linecodes.csv", index=False)
    latex_utils.salvar_tabela_latex(
        tabela_parametros.rename(columns={
            "linecode": "Linecode", "fases": "Fases", "r1_ohm_km": "R1 (Ω/km)", "x1_ohm_km": "X1 (Ω/km)",
            "r0_ohm_km": "R0 (Ω/km)", "x0_ohm_km": "X0 (Ω/km)", "c1_nf_km": "C1 (nF/km)", "c0_nf_km": "C0 (nF/km)",
            "normamps": "Ampacidade (A)", "x1_r1": "X1/R1",
        }),
        pasta_saida / "parametros_piores_linecodes.txt",
        legenda="Parâmetros elétricos dos linecodes mais associados a erro, tal como cadastrados na BDGD",
        rotulo="parametros_piores_linecodes",
        contexto="Secao 9 - parametros eletricos (Linecode do OpenDSS, sem correcao) dos linecodes da tabela "
                 "piores_linecodes_comparativo, para conferencia de possiveis erros de preenchimento na BDGD.",
        decimais={"Fases": 0, "R1 (Ω/km)": 3, "X1 (Ω/km)": 3, "R0 (Ω/km)": 3, "X0 (Ω/km)": 3,
                  "C1 (nF/km)": 1, "C0 (nF/km)": 1, "Ampacidade (A)": 1, "X1/R1": 2},
        alinhamento="lccccccccc",
    )

    tabela_coordenadas = montar_tabela_coordenadas(
        tabela_comparativa, grafo, origem, contexto["coordenadas"], resultados_takagi)
    tabela_coordenadas.to_csv(pasta_saida / "coordenadas_para_street_view.csv", index=False)
    latex_utils.salvar_tabela_latex(
        tabela_coordenadas.rename(columns={
            "linecode": "Linecode", "barra_falta_exemplo": "Barra de falta (exemplo)",
            "barra_de": "De", "barra_para": "Até", "long_de": "Long. (De)", "lat_de": "Lat. (De)",
            "long_para": "Long. (Até)", "lat_para": "Lat. (Até)",
        }),
        pasta_saida / "coordenadas_para_street_view.txt",
        legenda="Coordenadas geográficas dos segmentos de pior desempenho, para inspeção visual (Google Street View)",
        rotulo="coordenadas_street_view",
        contexto="Secao 9 - coordenadas (long/lat, EPSG:4326) das barras extremas do segmento de exemplo de "
                 "cada linecode problematico, para conferencia visual do condutor real.",
        decimais={"Long. (De)": 6, "Lat. (De)": 6, "Long. (Até)": 6, "Lat. (Até)": 6},
        alinhamento="lllcccc",
    )

    return {"tabela_km": tabela_km, "tabela_erro_takagi": tabela_erro_takagi,
            "tabela_erro_reatancia": tabela_erro_reatancia, "tabela_comparativa": tabela_comparativa,
            "tabela_parametros": tabela_parametros, "tabela_coordenadas": tabela_coordenadas}
