"""
Metodo da reatancia aparente para localizacao de falta: a partir da tensao
e corrente no rele durante a falta, estima a distancia usando so a parte
imaginaria da impedancia aparente (menos sensivel a resistencia de falta
que a parte real), calibrada pela reatancia de sequencia positiva (X1) por
km do trecho avaliado. Inclui tambem a compensacao de sequencia zero (K0)
e a correcao exata do offset que o fator de compensacao introduz quando a
falta tem resistencia, resolvendo Zm = s*Z1 + Rf*C como sistema de duas
equacoes reais (ver tcc2026.nucleo.geometria_eletrica para Z1/Z0 de
referencia e o Apendice C do texto do TCC para a deducao completa).
"""
import py_dss_interface

from tcc2026.nucleo import geometria_eletrica as ge


def x1_medio_ponderado_trecho(dss: py_dss_interface.DSS, grafo) -> float:
    """
    Calcula a reatancia de sequencia positiva (X1) media do trecho,
    ponderada pelo comprimento de cada segmento, a partir dos Linecodes
    reais usados (dado de catalogo do proprio alimentador, nao a geometria
    de referencia). E a constante de calibracao do metodo da reatancia
    simples (sem compensacao). Trechos trifasicos convertidos para a
    geometria de referencia Cemig (sem Linecode, ver
    tcc2026.extracao.extrator_trecho.converter_linhas_trifasicas_para_geometria_cemig)
    usam o X1 da propria geometria de referencia.

    Entradas:
        dss: instancia do motor OpenDSS do trecho em estudo, ja compilado.
        grafo: grafo eletrico do trecho (arestas tipo "linha" com
            "comprimento_km" e "linecode").
    Saida:
        X1 medio ponderado, em ohm/km.
    """
    linecodes = dss.linecodes
    x1_geometria_cemig = None
    soma_x1_km = 0.0
    soma_km = 0.0
    for _, _, dados in grafo.edges(data=True):
        if dados["tipo"] != "linha":
            continue
        if dados["linecode"]:
            linecodes.name = dados["linecode"]
            x1 = linecodes.x1
        else:
            if x1_geometria_cemig is None:
                x1_geometria_cemig = ge.calcular_parametros_sequencia_losangular_cemig()["x1_ohm_km"]
            x1 = x1_geometria_cemig
        soma_x1_km += x1 * dados["comprimento_km"]
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


def corrente_sequencia_zero(correntes_fase: dict) -> complex:
    """
    Corrente de sequencia zero a partir das 3 correntes de fase: I0 = (Ia + Ib + Ic) / 3.

    Entradas:
        correntes_fase: dicionario {1: Ia, 2: Ib, 3: Ic} (A, complexo).
    Saida:
        I0 (A, complexo).
    """
    return (correntes_fase[1] + correntes_fase[2] + correntes_fase[3]) / 3.0


def fator_compensacao_k0(z1_ohm_km: complex, z0_ohm_km: complex) -> complex:
    """
    Fator de compensacao de sequencia zero: K0 = (Z0 - Z1) / Z1.

    Entradas:
        z1_ohm_km: impedancia de sequencia positiva de referencia (ohm/km, complexo).
        z0_ohm_km: impedancia de sequencia zero de referencia (ohm/km, complexo).
    Saida:
        K0 (adimensional, complexo).
    """
    return (z0_ohm_km - z1_ohm_km) / z1_ohm_km


def corrente_compensada(corrente_fase_a: complex, corrente_sequencia_zero_a: complex, k0: complex) -> complex:
    """
    Corrente de fase A compensada pela sequencia zero: Ia_comp = Ia + K0 * I0.

    Entradas:
        corrente_fase_a: corrente de fase A no rele (A, complexo).
        corrente_sequencia_zero_a: corrente de sequencia zero no rele (A, complexo).
        k0: fator de compensacao (ver fator_compensacao_k0).
    Saida:
        corrente compensada (A, complexo).
    """
    return corrente_fase_a + k0 * corrente_sequencia_zero_a


def fator_c(z1_ohm_km: complex, z0_ohm_km: complex) -> complex:
    """
    Fator C que multiplica a resistencia de falta na impedancia aparente
    compensada: Zm = s*Z1 + Rf*C, com C = 3*Z1 / (2*Z1 + Z0). Quando
    Im(C) != 0, a resistencia de falta introduz um "offset" na parte
    imaginaria de Zm (e portanto um erro sistematico na distancia
    estimada) mesmo usando a corrente compensada.

    Entradas:
        z1_ohm_km, z0_ohm_km: impedancias de sequencia positiva e zero de
            referencia (ohm/km ou ohm totais, desde que consistentes).
    Saida:
        C (adimensional, complexo).
    """
    return 3 * z1_ohm_km / (2 * z1_ohm_km + z0_ohm_km)


def distancia_reatancia_compensada(tensao_rele_v: complex, corrente_compensada_a: complex,
                                    x1_ref_ohm_km: float) -> float:
    """
    Estima a distancia da falta pelo metodo da reatancia com compensacao
    de sequencia zero: Zm = V / Ia_comp, d = Im(Zm) / X1.

    Entradas:
        tensao_rele_v: tensao fase-neutro no rele durante a falta (V).
        corrente_compensada_a: corrente de fase compensada (ver corrente_compensada).
        x1_ref_ohm_km: reatancia de sequencia positiva de referencia (ohm/km).
    Saida:
        distancia estimada ate a falta, em km.
    """
    zm = tensao_rele_v / corrente_compensada_a
    return zm.imag / x1_ref_ohm_km


def distancia_reatancia_corrigida_exata(tensao_rele_v: complex, corrente_compensada_a: complex,
                                         z1_ohm_km: complex, z0_ohm_km: complex) -> float:
    """
    Estima a distancia da falta pelo metodo da reatancia compensada com
    correcao EXATA do offset de resistencia de falta: em vez de supor Rf
    desprezivel ou ajustar artificialmente o angulo de Z0 para anular
    Im(C), resolve o sistema Zm = s*Z1 + Rf*C (uma equacao complexa, duas
    equacoes reais) para as duas incognitas reais s e Rf, multiplicando
    por conj(C) e tomando a parte imaginaria (ver deducao completa no
    Apendice C do texto do TCC):

        C = 3*Z1 / (2*Z1 + Z0)
        s_hat = Im(Zm * conj(C)) / Im(Z1 * conj(C))

    Entradas:
        tensao_rele_v: tensao fase-neutro no rele durante a falta (V).
        corrente_compensada_a: corrente de fase compensada (Ia + K0*I0, ver
            corrente_compensada), com K0 = (Z0-Z1)/Z1 calculado diretamente
            a partir de z1_ohm_km e z0_ohm_km (sem nenhum ajuste artificial
            de angulo).
        z1_ohm_km, z0_ohm_km: impedancias de sequencia positiva e zero de
            referencia (ohm/km, complexo).
    Saida:
        distancia estimada ate a falta, em km.
    """
    zm = tensao_rele_v / corrente_compensada_a
    c_conj = fator_c(z1_ohm_km, z0_ohm_km).conjugate()
    return (zm * c_conj).imag / (z1_ohm_km * c_conj).imag


def resistencia_falta_estimada_exata(tensao_rele_v: complex, corrente_compensada_a: complex,
                                      z1_ohm_km: complex, z0_ohm_km: complex) -> float:
    """
    Estima a resistencia de falta Rf como subproduto da correcao exata do
    offset (ver distancia_reatancia_corrigida_exata), multiplicando
    Zm = s*Z1 + Rf*C por conj(Z1) e tomando a parte imaginaria:

        Rf_hat = Im(Zm * conj(Z1)) / Im(C * conj(Z1))

    Entradas: mesmas de distancia_reatancia_corrigida_exata.
    Saida:
        resistencia de falta estimada, em ohms.
    """
    zm = tensao_rele_v / corrente_compensada_a
    c = fator_c(z1_ohm_km, z0_ohm_km)
    z1_conj = z1_ohm_km.conjugate()
    return (zm * z1_conj).imag / (c * z1_conj).imag
