"""
Varredura generica de faltas monofasicas-terra, medindo tensao/corrente no
rele antes e depois da falta em cada barra de uma lista — base comum para
os metodos de Takagi e da reatancia compensada/corrigida (Secao 6).
"""
import pandas as pd
import py_dss_interface

from tcc2026.nucleo import falta_injecao as fi
from tcc2026.nucleo import grafo_alimentador as ga
from tcc2026.reatancia import metodo_reatancia as mr


def executar_varredura(dss: py_dss_interface.DSS, grafo, origem: str, barras: list,
                        rf_ohm: float = 0.01) -> pd.DataFrame:
    """
    Para cada barra da lista, aplica uma falta monofasica-terra (na fase
    realmente presente ali) e registra a tensao/corrente no rele antes e
    depois da falta, nas 3 fases (para o calculo de I0). A tensao/corrente
    pre-falta e a mesma para todas as barras (estado de carga normal do
    alimentador) e e medida uma unica vez.

    Entradas:
        dss: instancia do motor OpenDSS, ja resolvida em fluxo de potencia
            normal (estado de carga a usar como pre-falta).
        grafo: grafo eletrico do alimentador (ou trecho) em estudo.
        origem: nome da barra de origem (onde fica o rele).
        barras: lista de barras MT onde aplicar a falta.
        rf_ohm: resistencia de falta (ohms).
    Saida:
        DataFrame com colunas: barra, fase, distancia_real_km,
        va_pos (V, complexo), ia_pre, ia_pos (A, complexo, fase faltada),
        i0_pre, i0_pos (A, complexo, sequencia zero).
    """
    distancias = ga.distancias_desde_origem(grafo, origem)
    medidas_pre = fi.medir_tensoes_correntes_trifasicas_rele(dss, origem)
    i0_pre = mr.corrente_sequencia_zero(medidas_pre["correntes"])

    fi.preparar_elemento_falta(dss)
    linhas = []
    for barra in barras:
        dss.circuit.set_active_bus(barra)
        fase = int(dss.bus.nodes[0])
        fi.aplicar_falta_monofasica(dss, barra, fase, rf_ohm)
        dss.text("solve")
        if dss.solution.converged:
            medidas_pos = fi.medir_tensoes_correntes_trifasicas_rele(dss, origem)
            linhas.append({
                "barra": barra,
                "fase": fase,
                "distancia_real_km": distancias[barra],
                "va_pos": medidas_pos["tensoes"][fase],
                "ia_pre": medidas_pre["correntes"][fase],
                "ia_pos": medidas_pos["correntes"][fase],
                "i0_pre": i0_pre,
                "i0_pos": mr.corrente_sequencia_zero(medidas_pos["correntes"]),
            })
        fi.remover_falta(dss)
    return pd.DataFrame(linhas)
