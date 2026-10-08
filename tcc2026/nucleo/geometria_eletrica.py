"""
Geometria eletrica das linhas MT: verificacao de uso de LineGeometry no
alimentador e, quando ausente, definicao de uma geometria de referencia em
espacador losangular (padrao de rede compacta Cemig) para obter R1/X1/R0/X0/
C1/C0 fisicamente consistentes (o alimentador original so define Linecode
com r1/x1, sem matriz nem geometria -- R0/X0/C0/C1 lidos do Linecode sao o
valor default generico do OpenDSS, nao um calculo fisico real).
"""
from functools import lru_cache

import numpy as np
import py_dss_interface

from tcc2026.configuracao import CONDUTOR_REFERENCIA, GEOMETRIA_LOSANGULAR_CEMIG

_A = np.array([
    [1, 1, 1],
    [1, np.exp(-1j * 2 * np.pi / 3), np.exp(1j * 2 * np.pi / 3)],
    [1, np.exp(1j * 2 * np.pi / 3), np.exp(-1j * 2 * np.pi / 3)],
])
_A_INV = np.linalg.inv(_A)


def verificar_uso_linegeometry(dss: py_dss_interface.DSS) -> bool:
    """
    Verifica se algum elemento Line do alimentador compilado referencia um
    LineGeometry (em vez de Linecode simples ou matriz direta).

    Entradas:
        dss: instancia do motor OpenDSS com o alimentador ja compilado.
    Saida:
        True se pelo menos uma Line usa geometry=..., False caso contrario.
    """
    linhas = dss.lines
    for nome in linhas.names:
        linhas.name = nome
        if linhas.geometry.strip():
            return True
    return False


def matriz_fase_para_sequencia_1x(zabc_ohm_km: np.ndarray) -> tuple[complex, complex, complex]:
    """
    Converte uma matriz de impedancia de fase 3x3 (ohm/km) em componentes de
    sequencia, assumindo acoplamento aproximadamente equilibrado (media das
    auto-impedancias e media das impedancias mutuas).

    Entradas:
        zabc_ohm_km: matriz 3x3 complexa de impedancia de fase, em ohm/km.
    Saida:
        tupla (z0, z1, z2) em ohm/km (z1 = z2 para rede passiva equilibrada).
    """
    zs = np.trace(zabc_ohm_km) / 3.0
    fora_diag = zabc_ohm_km[~np.eye(3, dtype=bool)]
    zm = fora_diag.mean()
    z0 = zs + 2 * zm
    z1 = zs - zm
    z2 = zs - zm
    return complex(z0), complex(z1), complex(z2)


@lru_cache(maxsize=1)
def calcular_parametros_sequencia_losangular_cemig(nome_geometria: str = "GEOM_LOSANG_CEMIG",
                                                    nome_condutor: str = "COND_REF_CEMIG") -> dict:
    """
    Calcula R1/X1/R0/X0/C1/C0 por km de uma linha trifasica MT com espacador
    losangular padrao Cemig (3 fases + mensageiro neutro reduzido), usando
    um circuito OpenDSS auxiliar minimo e independente do alimentador real
    (o pacote de dados original nao traz WireData/LineGeometry; valores
    dimensionais e de condutor adotados como referencia tipica de catalogo,
    ver tcc2026.configuracao.CONDUTOR_REFERENCIA/GEOMETRIA_LOSANGULAR_CEMIG).

    ATENCAO: o motor OpenDSS (OpenDSSEngine.DSS, via COM) e um singleton por
    processo -- "clear"/"new circuit" aqui substitui QUALQUER circuito ja
    compilado (ex.: o alimentador real). Por isso o resultado e cacheado
    (lru_cache) e so roda uma vez por processo; se for chamar isto no meio
    de um pipeline que usa outra instancia de dss, recompile o alimentador
    real depois desta chamada antes de continuar.

    Entradas:
        nome_geometria: nome do objeto LineGeometry criado internamente.
        nome_condutor: nome do objeto WireData criado internamente.
    Saida:
        dicionario com r1_ohm_km, x1_ohm_km, r0_ohm_km, x0_ohm_km (ohm/km) e
        c1_nf_km, c0_nf_km (nF/km), validos para qualquer trecho MT trifasico
        que adote essa mesma geometria de referencia.
    """
    c = CONDUTOR_REFERENCIA
    g = GEOMETRIA_LOSANGULAR_CEMIG
    dss_aux = py_dss_interface.DSS()
    dss_aux.text("clear")
    dss_aux.text("new circuit.aux_geometria basekv=13.8 bus1=aux1 pu=1.0")
    dss_aux.text(
        f'new wiredata.{nome_condutor} Rdc={c["rdc_ohm_km"]} Rac={c["rac_ohm_km"]} '
        f'GMRac={c["gmr_m"]} GMRunits=m Radius={c["raio_m"]} Diam={c["diametro_m"]} '
        f'radunits=m normamps={c["normamps"]} runits=km'
    )
    h = g["altura_base_m"]
    dx = g["semi_diagonal_horizontal_m"]
    dy = g["semi_diagonal_vertical_m"]
    dss_aux.text(f'new linegeometry.{nome_geometria} nconds=4 nphases=3 reduce=yes')
    dss_aux.text(f'~ cond=1 wire={nome_condutor} x={dx}  h={h}')       # fase A (direita)
    dss_aux.text(f'~ cond=2 wire={nome_condutor} x={-dx} h={h}')       # fase B (esquerda)
    dss_aux.text(f'~ cond=3 wire={nome_condutor} x=0.0   h={h - dy}')  # fase C (base do losango)
    dss_aux.text(f'~ cond=4 wire={nome_condutor} x=0.0   h={h + dy}')  # neutro/mensageiro (topo)
    dss_aux.text('~ units=m')
    dss_aux.text(
        f'new line.linha_referencia bus1=aux1.1.2.3 bus2=aux2.1.2.3 '
        f'geometry={nome_geometria} length=1 units=km phases=3'
    )
    dss_aux.text("solve")
    linhas = dss_aux.lines
    linhas.name = "linha_referencia"
    rmatrix = np.array(linhas.rmatrix).reshape(3, 3)
    xmatrix = np.array(linhas.xmatrix).reshape(3, 3)
    cmatrix = np.array(linhas.cmatrix).reshape(3, 3)
    zabc = rmatrix + 1j * xmatrix
    z0, z1, _ = matriz_fase_para_sequencia_1x(zabc)
    c0_mat, c1_mat, _ = matriz_fase_para_sequencia_1x(cmatrix.astype(complex))
    return {
        "r1_ohm_km": z1.real,
        "x1_ohm_km": z1.imag,
        "r0_ohm_km": z0.real,
        "x0_ohm_km": z0.imag,
        "c1_nf_km": c1_mat.real,
        "c0_nf_km": c0_mat.real,
    }
