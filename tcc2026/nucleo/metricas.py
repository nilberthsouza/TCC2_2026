"""
Metricas de erro para avaliar metodos de localizacao de falta: comparam a
distancia real (desde a barra de origem/rele) com a distancia estimada pelo
metodo, ambas em km.
"""
import numpy as np


def erro_absoluto(distancia_real_km: np.ndarray, distancia_estimada_km: np.ndarray) -> np.ndarray:
    """
    Erro ponto a ponto entre a distancia estimada e a real.

    Entradas:
        distancia_real_km: distancias reais (km), vetor de N pontos.
        distancia_estimada_km: distancias estimadas pelo metodo (km), N pontos.
    Saida:
        vetor (km) com estimado - real, N pontos.
    """
    return np.asarray(distancia_estimada_km) - np.asarray(distancia_real_km)


def erro_absoluto_medio(distancia_real_km: np.ndarray, distancia_estimada_km: np.ndarray) -> float:
    """
    MAE (Mean Absolute Error) entre as distancias estimada e real.

    Entradas:
        distancia_real_km, distancia_estimada_km: vetores (km), N pontos.
    Saida:
        MAE em km.
    """
    return float(np.mean(np.abs(erro_absoluto(distancia_real_km, distancia_estimada_km))))


def raiz_erro_quadratico_medio(distancia_real_km: np.ndarray, distancia_estimada_km: np.ndarray) -> float:
    """
    RMSE (Root Mean Squared Error) entre as distancias estimada e real.

    Entradas:
        distancia_real_km, distancia_estimada_km: vetores (km), N pontos.
    Saida:
        RMSE em km.
    """
    erro = erro_absoluto(distancia_real_km, distancia_estimada_km)
    return float(np.sqrt(np.mean(erro ** 2)))


def coeficiente_determinacao(distancia_real_km: np.ndarray, distancia_estimada_km: np.ndarray) -> float:
    """
    R^2 (coeficiente de determinacao) entre a distancia estimada e a real.

    Entradas:
        distancia_real_km, distancia_estimada_km: vetores (km), N pontos.
    Saida:
        R^2 (adimensional; 1.0 = ajuste perfeito).
    """
    real = np.asarray(distancia_real_km, dtype=float)
    estimado = np.asarray(distancia_estimada_km, dtype=float)
    ss_res = np.sum((real - estimado) ** 2)
    ss_tot = np.sum((real - real.mean()) ** 2)
    return float(1.0 - ss_res / ss_tot) if ss_tot > 0 else float("nan")


def erro_maximo(distancia_real_km: np.ndarray, distancia_estimada_km: np.ndarray) -> float:
    """
    Maior erro absoluto (km) entre todos os pontos avaliados.

    Entradas:
        distancia_real_km, distancia_estimada_km: vetores (km), N pontos.
    Saida:
        erro maximo em km.
    """
    return float(np.max(np.abs(erro_absoluto(distancia_real_km, distancia_estimada_km))))


def erro_medio(distancia_real_km: np.ndarray, distancia_estimada_km: np.ndarray) -> float:
    """
    Erro medio (com sinal) entre a distancia estimada e a real, indica tendencia
    de sub ou sobre-estimacao do metodo.

    Entradas:
        distancia_real_km, distancia_estimada_km: vetores (km), N pontos.
    Saida:
        erro medio em km (positivo = metodo sobrestima a distancia).
    """
    return float(np.mean(erro_absoluto(distancia_real_km, distancia_estimada_km)))


def desvio_padrao_erro(distancia_real_km: np.ndarray, distancia_estimada_km: np.ndarray) -> float:
    """
    Desvio padrao do erro (km) entre a distancia estimada e a real.

    Entradas:
        distancia_real_km, distancia_estimada_km: vetores (km), N pontos.
    Saida:
        desvio padrao do erro em km.
    """
    return float(np.std(erro_absoluto(distancia_real_km, distancia_estimada_km), ddof=0))


def erro_maximo_percentual(distancia_real_km: np.ndarray, distancia_estimada_km: np.ndarray,
                            comprimento_base_km: float) -> float:
    """
    Maior erro absoluto, em % do comprimento total do trecho/tronco avaliado
    (convencao usual em artigos de localizacao de falta).

    Entradas:
        distancia_real_km, distancia_estimada_km: vetores (km), N pontos.
        comprimento_base_km: comprimento de referencia (km) usado como base
            do percentual (ex.: comprimento total do trecho/tronco).
    Saida:
        erro maximo em % do comprimento de referencia.
    """
    return 100.0 * erro_maximo(distancia_real_km, distancia_estimada_km) / comprimento_base_km


def erro_medio_percentual(distancia_real_km: np.ndarray, distancia_estimada_km: np.ndarray,
                           comprimento_base_km: float) -> float:
    """
    Erro medio (com sinal), em % do comprimento total do trecho/tronco avaliado.

    Entradas:
        distancia_real_km, distancia_estimada_km: vetores (km), N pontos.
        comprimento_base_km: comprimento de referencia (km) usado como base
            do percentual.
    Saida:
        erro medio em % do comprimento de referencia.
    """
    return 100.0 * erro_medio(distancia_real_km, distancia_estimada_km) / comprimento_base_km


def resumo_metricas(distancia_real_km: np.ndarray, distancia_estimada_km: np.ndarray,
                     comprimento_base_km: float) -> dict:
    """
    Calcula todas as metricas de erro de uma vez, para compor tabelas
    comparativas entre metodos de localizacao de falta.

    Entradas:
        distancia_real_km, distancia_estimada_km: vetores (km), N pontos.
        comprimento_base_km: comprimento de referencia (km) para os
            percentuais (ex.: comprimento do trecho/tronco avaliado).
    Saida:
        dicionario com mae_km, rmse_km, r2, erro_max_km, erro_max_pct,
        erro_medio_km, erro_medio_pct, desvio_padrao_km.
    """
    return {
        "mae_km": erro_absoluto_medio(distancia_real_km, distancia_estimada_km),
        "rmse_km": raiz_erro_quadratico_medio(distancia_real_km, distancia_estimada_km),
        "r2": coeficiente_determinacao(distancia_real_km, distancia_estimada_km),
        "erro_max_km": erro_maximo(distancia_real_km, distancia_estimada_km),
        "erro_max_pct": erro_maximo_percentual(distancia_real_km, distancia_estimada_km, comprimento_base_km),
        "erro_medio_km": erro_medio(distancia_real_km, distancia_estimada_km),
        "erro_medio_pct": erro_medio_percentual(distancia_real_km, distancia_estimada_km, comprimento_base_km),
        "desvio_padrao_km": desvio_padrao_erro(distancia_real_km, distancia_estimada_km),
    }
