"""
Camada fina sobre o py_dss_interface: localizar o Master do alimentador,
compilar o circuito, resolver fluxo de potencia (snapshot ou curva horaria)
e extrair resumos de potencia/perdas/tensao.
"""
import re
from pathlib import Path

import pandas as pd
import py_dss_interface

from tcc2026.configuracao import NUMERO_DU_PADRAO, PASTA_ALIMENTADOR_REDUZIDO, SUBESTACAO


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


def compilar_alimentador(caminho_master: Path | None = None,
                          aplicar_impedancia_real: bool = True) -> py_dss_interface.DSS:
    """
    Compila o alimentador no motor OpenDSS a partir do arquivo Master.

    Por padrao, substitui a fonte equivalente (quase ideal nos arquivos
    originais da BDGD) pela impedancia real da subestacao a montante (ver
    aplicar_impedancia_fonte_real), de modo que todas as secoes do trabalho
    (tabela de barras, estudos de trecho, Takagi, reatancia) usem o mesmo
    modelo consistente de fonte.

    Entradas:
        caminho_master: caminho do Master*.dss; se None, usa o Master padrao
            configurado em tcc2026.configuracao.
        aplicar_impedancia_real: se True (padrao), aplica a impedancia real
            da subestacao logo apos compilar. Usar False apenas em calculos
            auxiliares que nao dependem da fonte (ex.: geometria de
            referencia em componente isolado).
    Saida:
        instancia py_dss_interface.DSS com o circuito compilado (fonte
        equivalente ja ajustada, se aplicar_impedancia_real=True).
    """
    if caminho_master is None:
        caminho_master = localizar_master()
    dss = py_dss_interface.DSS()
    dss.text(f'compile "{caminho_master}"')
    if aplicar_impedancia_real:
        aplicar_impedancia_fonte_real(dss)
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


def escalar_carregamento(dss: py_dss_interface.DSS, fator: float) -> None:
    """
    Escala uniformemente todas as cargas do circuito ativo por `fator`,
    via o multiplicador global de carga do OpenDSS (Set LoadMult=), sem
    alterar os valores nominais de kW/kvar de cada objeto Load. Usado para
    simular cenarios de carregamento 2x/4x/6x (ver
    tcc2026.reatancia.estudo_trifasico/estudo_monofasico).

    Entradas:
        dss: instancia do motor OpenDSS (ja compilada).
        fator: multiplicador de carga (1.0 = carregamento nominal).
    Saida:
        nenhuma (altera o estado interno do solver; chamar
        resolver_fluxo_potencia novamente apos esta funcao).
    """
    dss.text(f"Set LoadMult={fator}")


def calcular_impedancia_equivalente_subestacao(dados_subestacao: dict = SUBESTACAO) -> dict:
    """
    Calcula a impedancia de Thevenin equivalente, no lado de 13,8 kV, do
    sistema a montante da subestacao (refletida do barramento de 69 kV)
    em serie com o transformador 69/13,8 kV, a partir da potencia de
    curto-circuito do sistema e dos dados de placa do transformador.

    O percentual de impedancia do transformador e a relacao X/R nao
    constam nos dados de origem; valores tipicos de catalogo (8%, X/R=8)
    sao adotados como referencia (ver tcc2026.configuracao.SUBESTACAO).

    Entradas:
        dados_subestacao: dicionario com tensao_primario_kv,
            tensao_secundario_kv, potencia_curto_circuito_mva,
            potencia_trafo_mva, percentual_impedancia_trafo e
            relacao_xr_trafo (ver tcc2026.configuracao.SUBESTACAO).
    Saida:
        dicionario com r1_ohm, x1_ohm (sequencia positiva, lado 13,8 kV) e
        r0_ohm, x0_ohm (sequencia zero, aproximada pela impedancia do
        proprio transformador, assumindo conexao Delta-Estrela aterrada
        que bloqueia a contribuicao de sequencia zero do sistema a
        montante).
    """
    v_pri = dados_subestacao["tensao_primario_kv"]
    v_sec = dados_subestacao["tensao_secundario_kv"]
    scc_mva = dados_subestacao["potencia_curto_circuito_mva"]
    s_trafo_mva = dados_subestacao["potencia_trafo_mva"]
    pct_z = dados_subestacao["percentual_impedancia_trafo"]
    xr = dados_subestacao["relacao_xr_trafo"]

    z_sistema_69kv_ohm = v_pri ** 2 / scc_mva
    z_sistema_13kv_ohm = z_sistema_69kv_ohm * (v_sec / v_pri) ** 2

    z_base_trafo_ohm = v_sec ** 2 / s_trafo_mva
    z_trafo_ohm = pct_z * z_base_trafo_ohm
    r_trafo_ohm = z_trafo_ohm / (1 + xr ** 2) ** 0.5
    x_trafo_ohm = xr * r_trafo_ohm

    r1_ohm = r_trafo_ohm
    x1_ohm = z_sistema_13kv_ohm + x_trafo_ohm
    return {
        "r1_ohm": r1_ohm,
        "x1_ohm": x1_ohm,
        "r0_ohm": r_trafo_ohm,
        "x0_ohm": x_trafo_ohm,
    }


def aplicar_impedancia_fonte_real(dss: py_dss_interface.DSS,
                                   impedancia: dict | None = None) -> dict:
    """
    Substitui a impedancia da fonte equivalente do circuito compilado
    (elemento Vsource.source, originalmente quase ideal nos arquivos da
    BDGD) pela impedancia real da subestacao (ver
    calcular_impedancia_equivalente_subestacao). Deve ser chamada logo
    apos compilar_alimentador() e antes de resolver_fluxo_potencia().

    Entradas:
        dss: instancia do motor OpenDSS, recem compilada.
        impedancia: dicionario com r1_ohm, x1_ohm, r0_ohm, x0_ohm; se None,
            calculada a partir de tcc2026.configuracao.SUBESTACAO.
    Saida:
        o dicionario de impedancia efetivamente aplicado.
    """
    if impedancia is None:
        impedancia = calcular_impedancia_equivalente_subestacao()
    dss.text(
        f"Edit Vsource.source "
        f"r1={impedancia['r1_ohm']:.6f} x1={impedancia['x1_ohm']:.6f} "
        f"r0={impedancia['r0_ohm']:.6f} x0={impedancia['x0_ohm']:.6f}"
    )
    return impedancia


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
