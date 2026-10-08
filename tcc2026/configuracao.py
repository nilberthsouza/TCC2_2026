"""
Caminhos e parametros globais do projeto.

O caminho do alimentador pode ser sobrescrito pela variavel de ambiente
TCC2026_PASTA_ALIMENTADOR, sem precisar alterar este arquivo.
"""
import os
from pathlib import Path

RAIZ_PROJETO = Path(__file__).resolve().parent.parent

PASTA_ALIMENTADOR_REDUZIDO = Path(os.environ.get(
    "TCC2026_PASTA_ALIMENTADOR",
    r"C:\Users\nilbe\Documents\DISCIPLINAS\TCC2026\TCC2\JMLT310_reduzido\rede_reduzida",
))

NUMERO_DU_PADRAO = 1

PASTA_RESULTADOS = RAIZ_PROJETO / "resultados"

TENSAO_BASE_KV = 13.8
FREQUENCIA_HZ = 60
SEMENTE_ALEATORIA_PADRAO = 42

# Parametros de referencia para a geometria em losango (espacador losangular),
# adotados por nao haver LineGeometry nem WireData no pacote de dados original
# (ver tcc2026/nucleo/geometria_eletrica.py).
CONDUTOR_REFERENCIA = {
    "nome": "CAA_1_0",
    "rdc_ohm_km": 0.535,
    "rac_ohm_km": 0.587,
    "gmr_m": 0.00136,
    "raio_m": 0.00525,
    "diametro_m": 0.0105,
    "normamps": 230,
}

# Afastamentos tipicos (m) do espacador losangular (cabo fase, cabo fase,
# cabo fase, mensageiro neutro) em torno do centro geometrico do poste.
GEOMETRIA_LOSANGULAR_CEMIG = {
    "altura_base_m": 8.00,
    "semi_diagonal_horizontal_m": 0.125,
    "semi_diagonal_vertical_m": 0.20,
}
