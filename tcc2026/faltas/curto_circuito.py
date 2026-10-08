"""
Calculo do equivalente de Thevenin, tensao/corrente de operacao e correntes
de curto-circuito (trifasico e monofasico-terra) em qualquer barra do
alimentador, via modo FaultStudy do OpenDSS.
"""
import numpy as np
import py_dss_interface

from tcc2026.nucleo import grafo_alimentador as ga


def executar_estudo_curto_circuito(dss: py_dss_interface.DSS) -> None:
    """
    Resolve o alimentador no modo FaultStudy do OpenDSS, que calcula para
    cada barra a impedancia de Thevenin de sequencia positiva/zero
    (Zsc1/Zsc0) e a corrente de curto trifasico (Isc), mantendo o ponto de
    carga do ultimo fluxo de potencia resolvido.

    Entradas:
        dss: instancia do motor OpenDSS, com o alimentador ja resolvido no
            ponto de operacao desejado (ver dss_core.resolver_fluxo_potencia).
    Saida:
        nenhuma (os resultados ficam disponiveis via dss.bus apos
        dss.circuit.set_active_bus(...)).
    """
    dss.text("solve mode=faultstudy")


def _pares_para_complexos(valores: list[float]) -> list[complex]:
    """
    Converte uma lista plana [re1, im1, re2, im2, ...] (formato devolvido
    pelo py_dss_interface para grandezas trifasicas) em uma lista de
    numeros complexos.

    Entradas:
        valores: lista com 2*N numeros reais (N fases).
    Saida:
        lista com N numeros complexos.
    """
    return [complex(valores[i], valores[i + 1]) for i in range(0, len(valores), 2)]


def thevenin_na_barra(dss: py_dss_interface.DSS, barra: str) -> dict:
    """
    Le a impedancia de Thevenin (sequencia positiva e zero) e as tensoes/
    correntes de curto trifasico calculadas pelo modo FaultStudy para uma
    barra.

    Entradas:
        dss: instancia do motor OpenDSS, ja resolvida em modo FaultStudy
            (ver executar_estudo_curto_circuito).
        barra: nome da barra (sem sufixo de fase).
    Saida:
        dicionario com:
            z1_ohm, z0_ohm: impedancia de Thevenin de sequencia positiva e
                zero, em ohms (numeros complexos).
            tensao_pre_falta_fases_v: tensao de Thevenin (= pre-falta) por
                fase, em volts fase-neutro (numeros complexos).
            corrente_curto_trifasico_fases_a: corrente de curto trifasico
                por fase, em amperes (numeros complexos).
    """
    dss.circuit.set_active_bus(barra)
    bus = dss.bus
    z1 = complex(bus.zsc1[0], bus.zsc1[1])
    z0 = complex(bus.zsc0[0], bus.zsc0[1])
    tensoes = _pares_para_complexos(bus.voc)
    correntes = _pares_para_complexos(bus.isc)
    return {
        "z1_ohm": z1,
        "z0_ohm": z0,
        "tensao_pre_falta_fases_v": tensoes,
        "corrente_curto_trifasico_fases_a": correntes,
    }


def curto_circuito_trifasico_a(dss: py_dss_interface.DSS, barra: str) -> float:
    """
    Corrente de curto-circuito trifasico (francamente aterrado) em uma
    barra, pela media das magnitudes de fase calculadas pelo FaultStudy.

    Entradas:
        dss: instancia do motor OpenDSS em modo FaultStudy.
        barra: nome da barra.
    Saida:
        corrente de curto trifasico, em amperes (magnitude).
    """
    dados = thevenin_na_barra(dss, barra)
    magnitudes = [abs(i) for i in dados["corrente_curto_trifasico_fases_a"]]
    return float(np.mean(magnitudes))


def curto_circuito_monofasico_a(dss: py_dss_interface.DSS, barra: str, rf_ohm: float = 0.0) -> float:
    """
    Corrente de curto-circuito monofasico-terra (fase A) em uma barra, por
    componentes simetricas: If = 3*Va_pre-falta / (Z1 + Z2 + Z0 + 3*Rf),
    assumindo Z2 = Z1 (rede passiva).

    Entradas:
        dss: instancia do motor OpenDSS em modo FaultStudy.
        barra: nome da barra.
        rf_ohm: resistencia de falta (ohms), padrao 0 (curto franco).
    Saida:
        corrente de curto monofasico-terra, em amperes (magnitude).
    """
    dados = thevenin_na_barra(dss, barra)
    z1 = dados["z1_ohm"]
    z2 = z1
    z0 = dados["z0_ohm"]
    va = dados["tensao_pre_falta_fases_v"][0]
    corrente = 3 * va / (z1 + z2 + z0 + 3 * rf_ohm)
    return float(abs(corrente))


def tensao_na_barra_pu(dss: py_dss_interface.DSS, barra: str) -> float:
    """
    Tensao de operacao (pre-falta) em uma barra, media das 3 fases, em pu.

    Entradas:
        dss: instancia do motor OpenDSS ja resolvida em fluxo de potencia
            normal (nao em FaultStudy).
        barra: nome da barra.
    Saida:
        tensao media em pu.
    """
    dss.circuit.set_active_bus(barra)
    magnitudes_pu = dss.bus.vmag_angle_pu[0::2]
    return float(np.mean(magnitudes_pu))


def elemento_a_montante(grafo, origem: str, barra: str) -> tuple[str, str]:
    """
    Identifica o elemento (linha ou transformador) imediatamente a montante
    de uma barra, no caminho desde a origem.

    Entradas:
        grafo: grafo eletrico do alimentador.
        origem: nome da barra de origem.
        barra: nome da barra de interesse.
    Saida:
        tupla (nome_classe_dss, nome_elemento), onde nome_classe_dss e
        "Line" ou "Transformer".
    """
    caminho = ga.caminho_entre_barras(grafo, origem, barra)
    pai = caminho[-2]
    dados = grafo.edges[pai, barra]
    nome_classe = "Line" if dados["tipo"] == "linha" else "Transformer"
    return nome_classe, dados["nome_elemento"]


def potencia_e_corrente_a_jusante(dss: py_dss_interface.DSS, grafo, origem: str, barra: str) -> dict:
    """
    Potencia ativa/reativa e corrente media que fluem, no fluxo de potencia
    normal, do elemento imediatamente a montante para dentro da barra —
    ou seja, tudo o que esta conectado a jusante desse ponto (carga
    concentrada equivalente, util para o circuito simplificado fonte-linha-
    disjuntor-medicao-carga).

    Entradas:
        dss: instancia do motor OpenDSS ja resolvida em fluxo de potencia
            normal (nao em FaultStudy).
        grafo: grafo eletrico do alimentador.
        origem: nome da barra de origem.
        barra: nome da barra de interesse.
    Saida:
        dicionario com p_kw (potencia ativa a jusante), q_kvar (potencia
        reativa a jusante; positivo = indutivo/QL, negativo = capacitivo/Qc)
        e corrente_media_a (corrente media das 3 fases, em amperes).
    """
    nome_classe, nome_elemento = elemento_a_montante(grafo, origem, barra)
    dss.circuit.set_active_element(f"{nome_classe}.{nome_elemento}")
    ce = dss.cktelement
    # A potencia reportada em cada terminal e a que "entra" no elemento por
    # ali; no terminal do lado da fonte ela e positiva e numericamente
    # igual ao que sai para a rede a jusante (a menos das perdas do proprio
    # trecho, que ficam incluidas como parte da carga concentrada).
    terminal_fonte = 0 if ga.nome_barra_base(ce.bus_names[0]) != barra else 1
    n_fases = ce.num_conductors
    bloco = ce.powers[terminal_fonte * 2 * n_fases: (terminal_fonte + 1) * 2 * n_fases]
    p_kw = sum(bloco[0::2])
    q_kvar = sum(bloco[1::2])
    correntes = ce.currents_mag_ang[terminal_fonte * 2 * n_fases: (terminal_fonte + 1) * 2 * n_fases]
    corrente_media_a = float(np.mean(correntes[0::2]))
    return {"p_kw": p_kw, "q_kvar": q_kvar, "corrente_media_a": corrente_media_a}
