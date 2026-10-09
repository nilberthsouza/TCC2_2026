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


def texto_definicao_geometria_losangular_cemig(nome_geometria: str = "GEOM_LOSANG_CEMIG",
                                                nome_condutor: str = "COND_REF_CEMIG") -> list[str]:
    """
    Gera as linhas de texto DSS (WireData + LineGeometry) da geometria em
    espacador losangular padrao Cemig, prontas para serem escritas em um
    arquivo .dss ou enviadas via dss.text(). Usada tanto para calcular os
    parametros de sequencia de referencia (ver
    calcular_parametros_sequencia_losangular_cemig) quanto para aplicar a
    geometria as linhas reais de um trecho extraido (ver
    tcc2026.extracao.extrator_trecho.aplicar_geometria_cemig_as_linhas).

    Entradas:
        nome_geometria: nome do objeto LineGeometry a criar.
        nome_condutor: nome do objeto WireData a criar.
    Saida:
        lista de linhas de texto DSS (sem quebras de linha).
    """
    c = CONDUTOR_REFERENCIA
    g = GEOMETRIA_LOSANGULAR_CEMIG
    h = g["altura_base_m"]
    dx = g["semi_diagonal_horizontal_m"]
    dy = g["semi_diagonal_vertical_m"]
    return [
        f'New wiredata.{nome_condutor} Rdc={c["rdc_ohm_km"]} Rac={c["rac_ohm_km"]} '
        f'GMRac={c["gmr_m"]} GMRunits=m Radius={c["raio_m"]} Diam={c["diametro_m"]} '
        f'radunits=m normamps={c["normamps"]} runits=km',
        f'New linegeometry.{nome_geometria} nconds=4 nphases=3 reduce=yes',
        f'~ cond=1 wire={nome_condutor} x={dx}  h={h}',        # fase A (direita)
        f'~ cond=2 wire={nome_condutor} x={-dx} h={h}',        # fase B (esquerda)
        f'~ cond=3 wire={nome_condutor} x=0.0   h={h - dy}',   # fase C (base do losango)
        f'~ cond=4 wire={nome_condutor} x=0.0   h={h + dy}',   # neutro/mensageiro (topo)
        '~ units=m',
    ]


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
    dss_aux = py_dss_interface.DSS()
    dss_aux.text("clear")
    dss_aux.text("new circuit.aux_geometria basekv=13.8 bus1=aux1 pu=1.0")
    for linha in texto_definicao_geometria_losangular_cemig(nome_geometria, nome_condutor):
        dss_aux.text(linha)
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


@lru_cache(maxsize=1)
def calcular_parametros_sequencia_monofasico_cemig(nome_geometria: str = "GEOM_MONO_CEMIG",
                                                     nome_condutor: str = "COND_REF_CEMIG") -> dict:
    """
    Calcula a impedancia de laco (fase + neutro reduzido) por km de um ramal
    monofasico MT, usado como referencia para os trechos monofasicos do
    alimentador (mesma logica/condutor da geometria losangular trifasica,
    ver calcular_parametros_sequencia_losangular_cemig). Como ha so um
    condutor de fase, a transformacao de componentes simetricas e trivial:
    Z1 = Z0 = impedancia propria do laco fase-neutro.

    ATENCAO: mesmo aviso de singleton do motor OpenDSS que
    calcular_parametros_sequencia_losangular_cemig (resultado cacheado).

    Entradas:
        nome_geometria: nome do objeto LineGeometry criado internamente.
        nome_condutor: nome do objeto WireData criado internamente.
    Saida:
        dicionario com r1_ohm_km, x1_ohm_km, r0_ohm_km, x0_ohm_km (ohm/km,
        com r0=r1 e x0=x1 pela natureza monofasica do trecho) e c1_nf_km,
        c0_nf_km (nF/km).
    """
    c = CONDUTOR_REFERENCIA
    g = GEOMETRIA_LOSANGULAR_CEMIG
    dss_aux = py_dss_interface.DSS()
    dss_aux.text("clear")
    dss_aux.text("new circuit.aux_geometria_1f basekv=13.8 bus1=aux1 pu=1.0")
    dss_aux.text(
        f'new wiredata.{nome_condutor} Rdc={c["rdc_ohm_km"]} Rac={c["rac_ohm_km"]} '
        f'GMRac={c["gmr_m"]} GMRunits=m Radius={c["raio_m"]} Diam={c["diametro_m"]} '
        f'radunits=m normamps={c["normamps"]} runits=km'
    )
    h = g["altura_base_m"]
    dss_aux.text(f'new linegeometry.{nome_geometria} nconds=2 nphases=1 reduce=yes')
    dss_aux.text(f'~ cond=1 wire={nome_condutor} x=0.0 h={h}')          # fase
    dss_aux.text(f'~ cond=2 wire={nome_condutor} x=0.0 h={h - 0.3}')    # neutro reduzido
    dss_aux.text('~ units=m')
    dss_aux.text(
        f'new line.linha_referencia_1f bus1=aux1.1 bus2=aux2.1 '
        f'geometry={nome_geometria} length=1 units=km phases=1'
    )
    dss_aux.text("solve")
    linhas = dss_aux.lines
    linhas.name = "linha_referencia_1f"
    z_self = complex(linhas.rmatrix[0], linhas.xmatrix[0])
    c_self = complex(linhas.cmatrix[0], 0.0)
    return {
        "r1_ohm_km": z_self.real,
        "x1_ohm_km": z_self.imag,
        "r0_ohm_km": z_self.real,
        "x0_ohm_km": z_self.imag,
        "c1_nf_km": c_self.real,
        "c0_nf_km": c_self.real,
    }


def acumular_parametros_linha_caminho(grafo, caminho: list) -> dict:
    """
    Soma R1/X1/R0/X0/C1/C0 e a distancia ao longo de uma sequencia de
    barras (caminho), usando os parametros de referencia por km da
    geometria losangular Cemig (trechos trifasicos) ou do laco monofasico
    (trechos de 1 fase); trechos de transformador (comprimento 0) nao
    entram na soma de impedancia de linha.

    Entradas:
        grafo: grafo eletrico do alimentador (arestas com "comprimento_km",
            "fases" e "tipo", ver grafo_alimentador.construir_grafo_eletrico).
        caminho: lista ordenada de barras (ex.: grafo_alimentador.caminho_entre_barras).
    Saida:
        dicionario com r1_ohm, x1_ohm, r0_ohm, x0_ohm (ohms totais),
        c1_nf, c0_nf (nF totais) e distancia_km (km totais do caminho).
    """
    params_3f = calcular_parametros_sequencia_losangular_cemig()
    params_1f = calcular_parametros_sequencia_monofasico_cemig()
    acumulado = {"r1_ohm": 0.0, "x1_ohm": 0.0, "r0_ohm": 0.0, "x0_ohm": 0.0,
                 "c1_nf": 0.0, "c0_nf": 0.0, "distancia_km": 0.0}
    for a, b in zip(caminho[:-1], caminho[1:]):
        dados = grafo.edges[a, b]
        if dados["tipo"] != "linha":
            continue
        comprimento_km = dados["comprimento_km"]
        params = params_3f if dados.get("fases") == 3 else params_1f
        acumulado["r1_ohm"] += params["r1_ohm_km"] * comprimento_km
        acumulado["x1_ohm"] += params["x1_ohm_km"] * comprimento_km
        acumulado["r0_ohm"] += params["r0_ohm_km"] * comprimento_km
        acumulado["x0_ohm"] += params["x0_ohm_km"] * comprimento_km
        acumulado["c1_nf"] += params["c1_nf_km"] * comprimento_km
        acumulado["c0_nf"] += params["c0_nf_km"] * comprimento_km
        acumulado["distancia_km"] += comprimento_km
    return acumulado
