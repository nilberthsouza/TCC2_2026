"""
Injecao de faltas (curto-circuito) via objeto Fault do OpenDSS e leitura da
tensao/corrente "no rele" (barra de origem do trecho/alimentador em
estudo), para os metodos de localizacao de falta (reatancia, Takagi).
"""
import py_dss_interface


def preparar_elemento_falta(dss: py_dss_interface.DSS, nome: str = "FALTA_ESTUDO") -> None:
    """
    Cria (desabilitado) o objeto Fault reutilizado por todas as simulacoes
    de curto-circuito deste estudo; evita recriar um objeto novo a cada
    falta simulada.

    Entradas:
        dss: instancia do motor OpenDSS com o circuito (alimentador
            completo ou trecho extraido) ja compilado.
        nome: nome do objeto Fault a criar.
    Saida:
        nenhuma.
    """
    dss.text(f"New Fault.{nome} bus1=aux_falta.1 phases=1 r=1e9 enabled=no")


def aplicar_falta_monofasica(dss: py_dss_interface.DSS, barra: str, fase: int,
                              rf_ohm: float = 0.01, nome: str = "FALTA_ESTUDO") -> None:
    """
    Aplica uma falta monofasica-terra (fase-neutro/terra) em uma barra.

    Entradas:
        dss: instancia do motor OpenDSS.
        barra: nome da barra onde aplicar a falta (sem sufixo de fase).
        fase: numero da fase (1/2/3) a aterrar.
        rf_ohm: resistencia de falta, em ohms (nao pode ser exatamente 0).
        nome: nome do objeto Fault (ver preparar_elemento_falta).
    Saida:
        nenhuma (o circuito fica com a falta habilitada ate remover_falta).
    """
    dss.text(f"Edit Fault.{nome} bus1={barra}.{fase} phases=1 r={rf_ohm} enabled=yes")


def aplicar_falta_trifasica(dss: py_dss_interface.DSS, barra: str,
                             rf_ohm: float = 0.01, nome: str = "FALTA_ESTUDO") -> None:
    """
    Aplica uma falta trifasica (as 3 fases entre si e terra, atraves de
    rf_ohm) em uma barra.

    Entradas:
        dss: instancia do motor OpenDSS.
        barra: nome da barra onde aplicar a falta (sem sufixo de fase).
        rf_ohm: resistencia de falta, em ohms.
        nome: nome do objeto Fault (ver preparar_elemento_falta).
    Saida:
        nenhuma.
    """
    dss.text(f"Edit Fault.{nome} bus1={barra}.1.2.3 phases=3 r={rf_ohm} enabled=yes")


def remover_falta(dss: py_dss_interface.DSS, nome: str = "FALTA_ESTUDO") -> None:
    """
    Desabilita o objeto Fault, retornando o circuito ao estado sem falta.

    Entradas:
        dss: instancia do motor OpenDSS.
        nome: nome do objeto Fault.
    Saida:
        nenhuma.
    """
    dss.text(f"Edit Fault.{nome} enabled=no")


def desligar_todas_as_cargas(dss: py_dss_interface.DSS) -> None:
    """
    Desabilita todas as cargas do circuito ativo (usado no cenario "sem
    cargas" do metodo da reatancia aparente).

    Entradas:
        dss: instancia do motor OpenDSS.
    Saida:
        nenhuma.
    """
    dss.text("BatchEdit Load..* enabled=no")


def religar_todas_as_cargas(dss: py_dss_interface.DSS) -> None:
    """
    Reabilita todas as cargas do circuito ativo.

    Entradas:
        dss: instancia do motor OpenDSS.
    Saida:
        nenhuma.
    """
    dss.text("BatchEdit Load..* enabled=yes")


def medir_tensao_corrente_rele(dss: py_dss_interface.DSS, barra_rele: str, fase: int) -> tuple[complex, complex]:
    """
    Le a tensao (na barra do rele, fase informada) e a corrente entregue
    pela fonte equivalente (Vsource.source), apos resolver o fluxo de
    potencia com a falta aplicada.

    Entradas:
        dss: instancia do motor OpenDSS, ja resolvida (fluxo de potencia ou
            falta aplicada).
        barra_rele: nome da barra onde o rele esta instalado (normalmente a
            barra de origem/raiz do circuito em estudo).
        fase: numero da fase (1/2/3) monitorada pelo rele.
    Saida:
        tupla (tensao_v, corrente_a), numeros complexos (volts fase-neutro,
        amperes), medidos no ponto do rele.
    """
    dss.circuit.set_active_bus(barra_rele)
    bus = dss.bus
    indice = list(bus.nodes).index(fase)
    tensao_v = complex(bus.voltages[2 * indice], bus.voltages[2 * indice + 1])

    dss.circuit.set_active_element("Vsource.source")
    ce = dss.cktelement
    indice_corrente = list(ce.node_order[:ce.num_conductors]).index(fase)
    # Convencao do OpenDSS: CktElement.Currents e a corrente que "entra" no
    # terminal do elemento; para a fonte, a corrente que ela efetivamente
    # injeta na rede tem sinal oposto.
    corrente_a = -complex(ce.currents[2 * indice_corrente], ce.currents[2 * indice_corrente + 1])
    return tensao_v, corrente_a
