"""
Metodo da reatancia aparente para localizacao de falta: a partir da tensao
e corrente no rele durante a falta, estima a distancia usando so a parte
imaginaria da impedancia aparente (menos sensivel a resistencia de falta
que a parte real), calibrada pela reatancia de sequencia positiva (X1) por
km do trecho avaliado.
"""
import py_dss_interface

from tcc2026.nucleo import grafo_alimentador as ga


def x1_medio_ponderado_trecho(dss: py_dss_interface.DSS, grafo) -> float:
    """
    Calcula a reatancia de sequencia positiva (X1) media do trecho,
    ponderada pelo comprimento de cada segmento, a partir dos Linecodes
    reais usados (dado de catalogo do proprio alimentador, nao a geometria
    de referencia). E a constante de calibracao do metodo da reatancia
    simples (sem compensacao).

    Entradas:
        dss: instancia do motor OpenDSS do trecho em estudo, ja compilado.
        grafo: grafo eletrico do trecho (arestas tipo "linha" com
            "comprimento_km" e "linecode").
    Saida:
        X1 medio ponderado, em ohm/km.
    """
    linecodes = dss.linecodes
    soma_x1_km = 0.0
    soma_km = 0.0
    for _, _, dados in grafo.edges(data=True):
        if dados["tipo"] != "linha":
            continue
        linecodes.name = dados["linecode"]
        soma_x1_km += linecodes.x1 * dados["comprimento_km"]
        soma_km += dados["comprimento_km"]
    return soma_x1_km / soma_km if soma_km else float("nan")


def impedancia_aparente(tensao_rele_v: complex, corrente_rele_a: complex) -> complex:
    """
    Impedancia aparente vista pelo rele: Zap = V / I.

    Entradas:
        tensao_rele_v: tensao fase-neutro no rele durante a falta (V).
        corrente_rele_a: corrente no rele durante a falta (A).
    Saida:
        impedancia aparente (ohms, numero complexo).
    """
    return tensao_rele_v / corrente_rele_a


def distancia_reatancia_simples(tensao_rele_v: complex, corrente_rele_a: complex, x1_ref_ohm_km: float) -> float:
    """
    Estima a distancia da falta pelo metodo da reatancia simples (sem
    compensacao): d = Im(Zap) / X1.

    Entradas:
        tensao_rele_v: tensao fase-neutro no rele durante a falta (V).
        corrente_rele_a: corrente no rele durante a falta (A).
        x1_ref_ohm_km: reatancia de sequencia positiva de referencia do
            trecho (ohm/km, ver x1_medio_ponderado_trecho).
    Saida:
        distancia estimada ate a falta, em km.
    """
    zap = impedancia_aparente(tensao_rele_v, corrente_rele_a)
    return zap.imag / x1_ref_ohm_km
