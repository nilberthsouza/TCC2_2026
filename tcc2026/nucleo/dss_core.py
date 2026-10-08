"""
Camada fina sobre o py_dss_interface: localizar o Master do alimentador,
compilar o circuito, resolver fluxo de potencia (snapshot ou curva horaria)
e extrair resumos de potencia/perdas/tensao.
"""
import re
from pathlib import Path

import pandas as pd
import py_dss_interface

from tcc2026.configuracao import NUMERO_DU_PADRAO, PASTA_ALIMENTADOR_REDUZIDO


def localizar_master(pasta_rede: Path = PASTA_ALIMENTADOR_REDUZIDO,
                      numero_du: int = NUMERO_DU_PADRAO) -> Path:
    """
    Localiza o arquivo Master_DU<numero_du>*.dss dentro da pasta do alimentador.

    Entradas:
        pasta_rede: pasta com os arquivos .dss do alimentador (padrao BDGD).
        numero_du: numero do Master_DU desejado (ex.: 1 para Master_DU01...).
    Saida:
        Path absoluto do arquivo Master encontrado.
    """
    padrao = re.compile(rf"^Master_?DU0*{numero_du}[_.].*\.dss$", re.IGNORECASE)
    candidatos = [p for p in pasta_rede.glob("*.dss") if padrao.match(p.name)]
    if not candidatos:
        raise FileNotFoundError(
            f"Nenhum Master_DU{numero_du:02d} encontrado em {pasta_rede}"
        )
    return candidatos[0]


def compilar_alimentador(caminho_master: Path | None = None) -> py_dss_interface.DSS:
    """
    Compila o alimentador no motor OpenDSS a partir do arquivo Master.

    Entradas:
        caminho_master: caminho do Master*.dss; se None, usa o Master padrao
            configurado em tcc2026.configuracao.
    Saida:
        instancia py_dss_interface.DSS com o circuito compilado e resolvido
        uma vez no modo definido pelo proprio Master (daily, passo 1h).
    """
    if caminho_master is None:
        caminho_master = localizar_master()
    dss = py_dss_interface.DSS()
    dss.text(f'compile "{caminho_master}"')
    return dss


def definir_modo_instantaneo(dss: py_dss_interface.DSS) -> None:
    """
    Ajusta o solver para um unico ponto de operacao (primeiro ponto da curva
    diaria, hora 0). O modo "snap" puro do OpenDSS nao converge nesta rede
    (cargas concentradas no secundario do trafo exigem Newton partindo de
    uma tensao inicial razoavel), por isso usa-se o modo daily com 1 passo.

    Entradas:
        dss: instancia do motor OpenDSS (ja compilada).
    Saida:
        nenhuma (altera o estado interno do solver).
    """
    dss.text("set mode=daily")
    dss.text("set controlmode=static")
    dss.text("set algorithm=newton")
    dss.text("set tolerance=0.0001")
    dss.text("set maxiterations=100")
    dss.text("set number=1")
    dss.text("set hour=0")


def resolver_fluxo_potencia(dss: py_dss_interface.DSS) -> bool:
    """
    Resolve o fluxo de potencia no ponto de operacao atual do solver.

    Entradas:
        dss: instancia do motor OpenDSS.
    Saida:
        True se a solucao convergiu, False caso contrario.
    """
    dss.text("solve")
    return bool(dss.solution.converged)


def resumo_potencia_e_perdas(dss: py_dss_interface.DSS) -> dict:
    """
    Resume a potencia entregue pela fonte e as perdas totais do circuito.

    Entradas:
        dss: instancia do motor OpenDSS ja resolvida (fluxo convergido).
    Saida:
        dicionario com:
            p_ativa_kw: potencia ativa total entregue pela fonte (kW)
            p_reativa_kvar: potencia reativa total entregue pela fonte (kvar)
            perdas_ativa_kw: perdas ativas totais do circuito (kW)
            perdas_reativa_kvar: perdas reativas totais do circuito (kvar)
            perdas_percentual: perdas ativas / potencia ativa da fonte (%)
            tensao_min_pu, tensao_media_pu, tensao_max_pu: estatisticas de
                tensao nas barras, em pu
    """
    p_fonte_kw, q_fonte_kvar = dss.circuit.total_power
    perdas_w, perdas_var = dss.circuit.losses
    p_ativa_kw = abs(p_fonte_kw)
    perdas_ativa_kw = perdas_w / 1000.0
    # Ha barras desenergizadas (ilha isolada sem conexao a fonte, ver
    # LEIA-ME do alimentador) com tensao numericamente ~0; sao excluidas
    # das estatisticas de tensao por nao representarem o alimentador.
    tensoes_pu = [v for v in dss.circuit.buses_vmag_pu if v > 0.05]
    return {
        "p_ativa_kw": p_ativa_kw,
        "p_reativa_kvar": abs(q_fonte_kvar),
        "perdas_ativa_kw": perdas_ativa_kw,
        "perdas_reativa_kvar": perdas_var / 1000.0,
        "perdas_percentual": 100.0 * perdas_ativa_kw / p_ativa_kw if p_ativa_kw else 0.0,
        "tensao_min_pu": min(tensoes_pu) if tensoes_pu else float("nan"),
        "tensao_media_pu": sum(tensoes_pu) / len(tensoes_pu) if tensoes_pu else float("nan"),
        "tensao_max_pu": max(tensoes_pu) if tensoes_pu else float("nan"),
    }


def simular_dia_horario(dss: py_dss_interface.DSS, horas: int = 24) -> pd.DataFrame:
    """
    Simula o alimentador hora a hora (modo daily, passo de 1h) e coleta as
    curvas de potencia, perdas e tensao.

    Entradas:
        dss: instancia do motor OpenDSS ja compilada (Master define
            Set mode=daily, loadshapes de 24 pontos/1h).
        horas: numero de horas a simular (padrao 24, um dia completo).
    Saida:
        pandas.DataFrame com uma linha por hora e colunas:
            hora (0..horas-1), p_ativa_kw, p_reativa_kvar,
            perdas_ativa_kw, perdas_reativa_kvar,
            tensao_min_pu, tensao_media_pu, tensao_max_pu
    """
    dss.text("set mode=daily")
    dss.text("set algorithm=newton")
    dss.text("set tolerance=0.0001")
    dss.text("set maxiterations=100")
    dss.text("set number=1")
    dss.text("set hour=0")
    linhas = []
    for hora in range(horas):
        dss.text("solve")
        if not dss.solution.converged:
            # Rede reduzida com cargas BT concentradas no secundario do
            # trafo pode nao convergir em pontos de carga especificos (ver
            # LEIA-ME do alimentador). Tenta uma vez com algoritmo normal
            # antes de marcar a hora como nao convergente (NaN).
            dss.text("set algorithm=normal")
            dss.text("solve")
            dss.text("set algorithm=newton")
        if dss.solution.converged:
            resumo = resumo_potencia_e_perdas(dss)
        else:
            resumo = {k: float("nan") for k in (
                "p_ativa_kw", "p_reativa_kvar", "perdas_ativa_kw",
                "perdas_reativa_kvar", "perdas_percentual",
                "tensao_min_pu", "tensao_media_pu", "tensao_max_pu")}
        resumo["hora"] = hora
        linhas.append(resumo)
    colunas = ["hora", "p_ativa_kw", "p_reativa_kvar", "perdas_ativa_kw",
               "perdas_reativa_kvar", "tensao_min_pu", "tensao_media_pu", "tensao_max_pu"]
    return pd.DataFrame(linhas)[colunas]
