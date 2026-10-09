"""
Metodo de Takagi para localizacao de falta, baseado em
"Distribution Fault-Locating Algorithms Using Current Only" (metodo 1),
adaptado para ler a tensao diretamente na barra do rele (em vez de
estima-la so por corrente, como no artigo original) e usar o fator de
compensacao de corrente de sequencia zero (K0).
"""


def delta_corrente(corrente_pos_falta_a: complex, corrente_pre_falta_a: complex) -> complex:
    """
    Variacao de corrente entre o estado em falta e o estado pre-falta:
    DeltaIa = Ia_falta - Ia_pre_falta.

    Entradas:
        corrente_pos_falta_a: corrente de fase durante a falta (A, complexo).
        corrente_pre_falta_a: corrente de fase antes da falta (A, complexo).
    Saida:
        DeltaIa (A, complexo).
    """
    return corrente_pos_falta_a - corrente_pre_falta_a


def distancia_takagi(tensao_pos_falta_v: complex, corrente_pos_falta_a: complex,
                      corrente_pre_falta_a: complex, z1_ohm_km: complex) -> float:
    """
    Estima a distancia da falta pelo metodo de Takagi (metodo 1, por
    corrente, com a tensao lida diretamente na barra do rele):
        m = Im(Va . DeltaIa*) / Im(Z1 . Ia . DeltaIa*)
    Como Z1 aqui e dado em ohm/km, "m" ja sai diretamente em km
    (equivalente a d = m*L da formulacao classica, com Z1 por unidade de
    comprimento e L = 1 km).

    Entradas:
        tensao_pos_falta_v: tensao fase-neutro no rele durante a falta (V, complexo).
        corrente_pos_falta_a: corrente de fase no rele durante a falta (A, complexo).
        corrente_pre_falta_a: corrente de fase no rele antes da falta (A, complexo).
        z1_ohm_km: impedancia de sequencia positiva de referencia (ohm/km, complexo).
    Saida:
        distancia estimada ate a falta, em km.
    """
    delta_ia = delta_corrente(corrente_pos_falta_a, corrente_pre_falta_a)
    numerador = (tensao_pos_falta_v * delta_ia.conjugate()).imag
    denominador = (z1_ohm_km * corrente_pos_falta_a * delta_ia.conjugate()).imag
    return numerador / denominador


def distancia_takagi_compensado(tensao_pos_falta_v: complex,
                                 corrente_pos_falta_a: complex, corrente_pre_falta_a: complex,
                                 i0_pos_falta_a: complex, i0_pre_falta_a: complex,
                                 k0: complex, z1_ohm_km: complex) -> float:
    """
    Metodo de Takagi com compensacao de sequencia zero: a corrente de fase
    (antes e depois da falta) e compensada por Icomp = Ia + K0*I0 antes de
    aplicar a formula de Takagi (ver distancia_takagi).

    Entradas:
        tensao_pos_falta_v: tensao fase-neutro no rele durante a falta (V, complexo).
        corrente_pos_falta_a, corrente_pre_falta_a: corrente de fase no
            rele, durante e antes da falta (A, complexo).
        i0_pos_falta_a, i0_pre_falta_a: corrente de sequencia zero no rele,
            durante e antes da falta (A, complexo).
        k0: fator de compensacao de sequencia zero (ver
            tcc2026.reatancia.metodo_reatancia.fator_compensacao_k0).
        z1_ohm_km: impedancia de sequencia positiva de referencia (ohm/km, complexo).
    Saida:
        distancia estimada ate a falta, em km.
    """
    ia_pos_comp = corrente_pos_falta_a + k0 * i0_pos_falta_a
    ia_pre_comp = corrente_pre_falta_a + k0 * i0_pre_falta_a
    return distancia_takagi(tensao_pos_falta_v, ia_pos_comp, ia_pre_comp, z1_ohm_km)
