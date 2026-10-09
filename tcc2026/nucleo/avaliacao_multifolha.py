"""
Avaliacao do Algoritmo 1 (avaliacao de um caminho rele-folha) em modo
multi-folha real: para cada falta simulada em uma barra folha MT, avalia a
formula de localizacao contra TODAS as folhas candidatas do alimentador
(nao so a folha onde a falta realmente ocorreu), contando quantas delas
produzem uma distancia valida (0<=d_mi<=L, Algoritmo 1 da Secao 3.2 do
TCC). Mede, assim, quao bem o criterio de validade por si so discrimina o
ramo correto da falta, sem usar a distancia real para escolher o
vencedor -- diferente das demais secoes deste projeto, que avaliam a
formula apenas no caminho correto (ja conhecido por construcao).
"""
import pandas as pd

from tcc2026.nucleo import geometria_eletrica as ge, grafo_alimentador as ga

EPS_DEN = 1e-9


def impedancias_por_folha(grafo, origem: str, folhas: list) -> dict:
    """
    Pre-calcula Z1L, Z0L (ohms) e L (km) do caminho rele-folha para cada
    barra folha, pelo Algoritmo 2 (ver
    geometria_eletrica.acumular_parametros_linha_caminho).

    Entradas:
        grafo: grafo eletrico do alimentador.
        origem: barra de origem (posicao do rele).
        folhas: lista de barras folha candidatas.
    Saida:
        dicionario {folha: {"z1l": complex, "z0l": complex, "l_km": float}}.
    """
    resultado = {}
    for folha in folhas:
        caminho = ga.caminho_entre_barras(grafo, origem, folha)
        acumulado = ge.acumular_parametros_linha_caminho(grafo, caminho)
        resultado[folha] = {
            "z1l": complex(acumulado["r1_ohm"], acumulado["x1_ohm"]),
            "z0l": complex(acumulado["r0_ohm"], acumulado["x0_ohm"]),
            "l_km": acumulado["distancia_km"],
        }
    return resultado


def avaliar_algoritmo1_caminho_takagi(va_pos: complex, ia_pos: complex, ia_pre: complex,
                                       i0_pos: complex, i0_pre: complex,
                                       z1l: complex, z0l: complex, l_km: float) -> dict:
    """
    Aplica o Algoritmo 1 (avaliacao de um caminho rele-folha) a um unico
    caminho candidato, pela formula do Takagi compensado (Equacoes
    3.12-3.16 do TCC).

    Entradas:
        va_pos, ia_pos, ia_pre, i0_pos, i0_pre: fasores medidos no rele
            durante e antes da falta (V/A).
        z1l, z0l: impedancia de sequencia positiva/zero acumulada do
            caminho rele-folha candidato (ohms, ver impedancias_por_folha).
        l_km: comprimento total do caminho candidato (km).
    Saida:
        dicionario com "valido" (bool), "d_mi_km" (float, possivelmente
        fora de [0, l_km] ou NaN) e "motivo_descarte" (str ou None).
    """
    k0 = (z0l - z1l) / z1l
    icomp_pos = ia_pos + k0 * i0_pos
    icomp_pre = ia_pre + k0 * i0_pre
    delta_icomp = icomp_pos - icomp_pre
    num = (va_pos * delta_icomp.conjugate()).imag
    den = (z1l * icomp_pos * delta_icomp.conjugate()).imag
    return _classificar_caminho(num, den, l_km)


def avaliar_algoritmo1_caminho_reatancia(va_pos: complex, ia_pos: complex, i0_pos: complex,
                                          z1l: complex, z0l: complex, l_km: float) -> dict:
    """
    Aplica o Algoritmo 1 (avaliacao de um caminho rele-folha) a um unico
    caminho candidato, pela formula da reatancia compensada com correcao
    exata do offset (ver metodo_reatancia.distancia_reatancia_corrigida_exata),
    usando Z1L/Z0L absolutos do caminho candidato em vez da taxa por km.

    Entradas:
        va_pos, ia_pos, i0_pos: fasores medidos no rele durante a falta (V/A).
        z1l, z0l: impedancia de sequencia positiva/zero acumulada do
            caminho rele-folha candidato (ohms, ver impedancias_por_folha).
        l_km: comprimento total do caminho candidato (km).
    Saida:
        dicionario com "valido" (bool), "d_mi_km" (float, possivelmente
        fora de [0, l_km] ou NaN) e "motivo_descarte" (str ou None).
    """
    k0 = (z0l - z1l) / z1l
    icomp = ia_pos + k0 * i0_pos
    c = 3 * z1l / (2 * z1l + z0l)
    zm = va_pos / icomp
    num = (zm * c.conjugate()).imag
    den = (z1l * c.conjugate()).imag
    return _classificar_caminho(num, den, l_km)


def _classificar_caminho(num: float, den: float, l_km: float) -> dict:
    """Converte (num, den) da equacao do Algoritmo 1 em d_mi_km e validade."""
    if abs(den) < EPS_DEN:
        return {"valido": False, "d_mi_km": float("nan"), "motivo_descarte": "denominador_nulo"}
    d_mi_km = (num / den) * l_km
    if 0.0 <= d_mi_km <= l_km:
        return {"valido": True, "d_mi_km": d_mi_km, "motivo_descarte": None}
    return {"valido": False, "d_mi_km": d_mi_km, "motivo_descarte": "fora_do_intervalo"}


def avaliar_multifolha(medidas_folhas: pd.DataFrame, impedancias: dict, avaliar_caminho_fn) -> pd.DataFrame:
    """
    Simula o procedimento multi-folha completo (Algoritmo 3): para cada
    falta em uma barra folha (medidas_folhas), avalia o Algoritmo 1 contra
    TODAS as folhas candidatas (impedancias), sem usar a distancia real
    para escolher o vencedor -- apenas o criterio de validade de cada
    caminho.

    Entradas:
        medidas_folhas: DataFrame com uma linha por barra de falta (cada
            uma deve ser uma barra folha presente em `impedancias`),
            colunas "barra", "distancia_real_km" e as colunas de fasores
            exigidas por `avaliar_caminho_fn`.
        impedancias: dicionario devolvido por impedancias_por_folha, com
            TODAS as folhas candidatas do alimentador.
        avaliar_caminho_fn: funcao(falta: Series, z1l, z0l, l_km) -> dict
            (ver avaliar_algoritmo1_caminho_takagi/_reatancia), que aplica
            o Algoritmo 1 a um unico caminho candidato.
    Saida:
        DataFrame com uma linha por barra de falta: "barra_falta",
        "n_folhas", "n_validas" (quantas folhas candidatas produziram uma
        distancia valida), "folha_correta_valida" (bool: a folha onde a
        falta realmente ocorreu foi uma das validas), "erro_km_correto"
        (erro da estimativa no caminho correto, entre as validas).
    """
    linhas = []
    for _, falta in medidas_folhas.iterrows():
        barra_falta = falta["barra"]
        n_validas = 0
        d_correto = float("nan")
        correto_valido = False
        for folha, imp in impedancias.items():
            avaliacao = avaliar_caminho_fn(falta, imp["z1l"], imp["z0l"], imp["l_km"])
            if avaliacao["valido"]:
                n_validas += 1
            if folha == barra_falta:
                d_correto = avaliacao["d_mi_km"]
                correto_valido = avaliacao["valido"]
        linhas.append({
            "barra_falta": barra_falta,
            "n_folhas": len(impedancias),
            "n_validas": n_validas,
            "folha_correta_valida": correto_valido,
            "erro_km_correto": d_correto - falta["distancia_real_km"],
        })
    return pd.DataFrame(linhas)
