"""
Extracao de um sub-alimentador ("mini alimentador") standalone a partir de
um ramal do JMLT310 reduzido: copia, por filtragem de texto dos arquivos
.dss originais (preservando a sintaxe exata dos objetos), apenas os
elementos cujas barras pertencem a sub-arvore de interesse, e monta um novo
Master com uma fonte de tensao equivalente na raiz do ramal (tensao real
observada ali no alimentador completo).
"""
import re
from pathlib import Path

import numpy as np
import py_dss_interface

from tcc2026.configuracao import NUMERO_DU_PADRAO, PASTA_ALIMENTADOR_REDUZIDO
from tcc2026.nucleo import grafo_alimentador as ga

_PADRAO_BUS1 = re.compile(r'bus1="([^".]+)')
_PADRAO_BUS2 = re.compile(r'bus2="([^".]+)')
_PADRAO_PRIMEIRA_BUS_TRAFO = re.compile(r'buses=\[\s*"([^".]+)')
_PADRAO_LOADSHAPE = re.compile(r'(?:daily|yearly)="([^"]+)"')
_PADRAO_NOME_LOADSHAPE = re.compile(r'New "Loadshape\.([^"]+)"')


def localizar_arquivo_por_prefixo(pasta: Path, prefixo: str) -> Path:
    """
    Localiza um arquivo .dss do alimentador original pelo prefixo do nome
    (mesmo esquema do Master_DU, ver dss_core.localizar_master).

    Entradas:
        pasta: pasta com os arquivos .dss do alimentador original.
        prefixo: prefixo do nome do arquivo (ex.: "SegmentosMT").
    Saida:
        Path do primeiro arquivo .dss encontrado com esse prefixo.
    """
    candidatos = sorted(pasta.glob(f"{prefixo}*.dss"))
    if not candidatos:
        raise FileNotFoundError(f"Nenhum arquivo com prefixo '{prefixo}' em {pasta}")
    return candidatos[0]


def _ler_linhas(caminho: Path) -> list[str]:
    """Le um arquivo .dss como lista de linhas (texto bruto)."""
    return caminho.read_text(encoding="utf-8", errors="replace").splitlines()


def filtrar_linhas_dois_barramentos(caminho: Path, barras_validas: set) -> list[str]:
    """
    Filtra as linhas "New ... bus1=... bus2=..." de um arquivo (Segmentos/
    Chaves MT) mantendo so os trechos cujas DUAS barras estao no conjunto
    informado.

    Entradas:
        caminho: arquivo .dss de origem (SegmentosMT ou ChavesMT).
        barras_validas: conjunto de nomes de barra (sem sufixo de fase) a manter.
    Saida:
        lista das linhas de texto mantidas (sintaxe original preservada).
    """
    mantidas = []
    for linha in _ler_linhas(caminho):
        m1, m2 = _PADRAO_BUS1.search(linha), _PADRAO_BUS2.search(linha)
        if not m1 or not m2:
            continue
        if ga.nome_barra_base(m1.group(1)) in barras_validas and ga.nome_barra_base(m2.group(1)) in barras_validas:
            mantidas.append(linha)
    return mantidas


def filtrar_linhas_um_barramento(caminho: Path, barras_validas: set) -> list[str]:
    """
    Filtra as linhas "New ... bus1=..." de um arquivo (Cargas) mantendo so
    os objetos cuja barra esta no conjunto informado.

    Entradas:
        caminho: arquivo .dss de origem (CargasBT ou CargasMT).
        barras_validas: conjunto de nomes de barra a manter.
    Saida:
        lista das linhas de texto mantidas.
    """
    mantidas = []
    for linha in _ler_linhas(caminho):
        m1 = _PADRAO_BUS1.search(linha)
        if m1 and ga.nome_barra_base(m1.group(1)) in barras_validas:
            mantidas.append(linha)
    return mantidas


def filtrar_transformadores(caminho: Path, barras_validas: set) -> list[str]:
    """
    Filtra os blocos "New Transformer..." (+ "New Reactor..." de
    aterramento do neutro, quando presente logo em seguida) cuja barra
    primaria esta no conjunto informado.

    Entradas:
        caminho: arquivo TransformadorMTMTMTBT original.
        barras_validas: conjunto de nomes de barra a manter.
    Saida:
        lista das linhas de texto mantidas (transformador + reactor).
    """
    linhas_originais = _ler_linhas(caminho)
    mantidas = []
    for indice, linha in enumerate(linhas_originais):
        if not linha.strip().startswith('New "Transformer.'):
            continue
        m = _PADRAO_PRIMEIRA_BUS_TRAFO.search(linha)
        if not m or ga.nome_barra_base(m.group(1)) not in barras_validas:
            continue
        mantidas.append(linha)
        proxima = linhas_originais[indice + 1] if indice + 1 < len(linhas_originais) else ""
        if proxima.strip().startswith('New "Reactor.'):
            mantidas.append(proxima)
    return mantidas


def extrair_loadshapes_usadas(linhas_cargas: list[str]) -> set:
    """
    Identifica os nomes de Loadshape referenciados por uma lista de linhas
    de Load (propriedade daily=/yearly=).

    Entradas:
        linhas_cargas: linhas de texto "New Load..." ja filtradas.
    Saida:
        conjunto com os nomes das loadshapes usadas.
    """
    nomes = set()
    for linha in linhas_cargas:
        m = _PADRAO_LOADSHAPE.search(linha)
        if m:
            nomes.add(m.group(1))
    return nomes


def filtrar_curva_carga(caminho: Path, nomes_usados: set) -> list[str]:
    """
    Filtra as definicoes de Loadshape de um arquivo CurvaCarga, mantendo so
    as que estao em nomes_usados.

    Entradas:
        caminho: arquivo CurvaCarga original.
        nomes_usados: conjunto de nomes de loadshape a manter (ver
            extrair_loadshapes_usadas).
    Saida:
        lista das linhas de texto mantidas.
    """
    mantidas = []
    for linha in _ler_linhas(caminho):
        m = _PADRAO_NOME_LOADSHAPE.search(linha)
        if m and m.group(1) in nomes_usados:
            mantidas.append(linha)
    return mantidas


def determinar_fase_barra_raiz(linhas_relevantes: list[str], barra_raiz: str) -> int:
    """
    Determina o numero da fase (1/2/3) da barra_raiz dentro do trecho
    extraido, a partir do sufixo de no de uma das linhas mantidas que a
    referenciam. Necessario porque, no alimentador completo, a barra_raiz
    pode ser um ponto de transicao com mais de uma fase ativa (ex.: um no
    de onde tambem parte um ramal trifasico que foi excluido do trecho);
    o que importa aqui e a fase realmente usada pelas linhas do trecho
    extraido, nao qualquer fase ativa da barra no alimentador completo.

    Entradas:
        linhas_relevantes: linhas de texto "New Line..." ja filtradas para
            o trecho (ver filtrar_linhas_dois_barramentos).
        barra_raiz: nome da barra raiz do trecho (sem sufixo de fase).
    Saida:
        numero da fase (1, 2 ou 3).
    """
    padrao = re.compile(re.escape(barra_raiz) + r'\.(\d)', re.IGNORECASE)
    for linha in linhas_relevantes:
        m = padrao.search(linha)
        if m:
            return int(m.group(1))
    raise ValueError(f"Nao foi possivel determinar a fase de {barra_raiz} nas linhas do trecho.")


def tensao_fonte_equivalente(dss: py_dss_interface.DSS, barra_raiz: str, fase: int) -> dict:
    """
    Le a tensao real (magnitude e angulo) observada na barra_raiz, na fase
    informada, no alimentador completo ja resolvido, para usar como fonte
    de tensao equivalente (Thevenin) do mini-alimentador extraido.

    Entradas:
        dss: instancia do motor OpenDSS do alimentador completo, ja
            resolvida em fluxo de potencia normal.
        barra_raiz: barra onde o trecho extraido comeca.
        fase: numero da fase (1/2/3) a usar (ver determinar_fase_barra_raiz).
    Saida:
        dicionario com fase (int), kv_ln (tensao fase-neutro, kV) e
        angulo_graus (angulo de fase, graus).
    """
    dss.circuit.set_active_bus(barra_raiz)
    bus = dss.bus
    indice = list(bus.nodes).index(fase)
    v_re, v_im = bus.voltages[2 * indice], bus.voltages[2 * indice + 1]
    v_complexo = complex(v_re, v_im)
    return {
        "fase": fase,
        "kv_ln": abs(v_complexo) / 1000.0,
        "angulo_graus": float(np.angle(v_complexo, deg=True)),
    }


def extrair_subalimentador(dss: py_dss_interface.DSS, barra_raiz: str, barras_subarvore: set,
                            pasta_saida: Path, nome_circuito: str,
                            pasta_alimentador: Path = PASTA_ALIMENTADOR_REDUZIDO,
                            numero_du: int = NUMERO_DU_PADRAO) -> Path:
    """
    Gera, em pasta_saida, um Master .dss standalone com so os elementos cujas
    barras estao em barras_subarvore, alimentado por uma fonte de tensao
    equivalente na tensao real observada em barra_raiz no alimentador
    completo. O conjunto de barras e calculado pelo chamador (ver
    grafo_alimentador.subarvore_a_partir_de, para um ramal completo, ou
    grafo_alimentador.barras_trecho_monofasico, para restringir a um trecho
    estritamente monofasico).

    Entradas:
        dss: instancia do motor OpenDSS do alimentador completo, ja
            resolvida em fluxo de potencia normal (para a fonte equivalente).
        barra_raiz: barra onde o trecho extraido comeca (usada como barra da
            fonte de tensao equivalente).
        barras_subarvore: conjunto de barras a manter no mini-alimentador.
        pasta_saida: pasta onde os .dss do mini-alimentador serao escritos.
        nome_circuito: nome do novo Circuit (tambem usado no nome dos arquivos).
        pasta_alimentador: pasta do alimentador reduzido original.
        numero_du: numero do Master_DU original (para localizar CargasBT/MT).
    Saida:
        Path do arquivo Master gerado (pronto para ser compilado).
    """
    pasta_saida = Path(pasta_saida)
    pasta_saida.mkdir(parents=True, exist_ok=True)

    linhas_mt = filtrar_linhas_dois_barramentos(
        localizar_arquivo_por_prefixo(pasta_alimentador, "SegmentosMT"), barras_subarvore)
    chaves_mt = filtrar_linhas_dois_barramentos(
        localizar_arquivo_por_prefixo(pasta_alimentador, "ChavesMT"), barras_subarvore)
    transformadores = filtrar_transformadores(
        localizar_arquivo_por_prefixo(pasta_alimentador, "TransformadorMTMTMTBT"), barras_subarvore)
    cargas_bt = filtrar_linhas_um_barramento(
        localizar_arquivo_por_prefixo(pasta_alimentador, f"CargasBT_DU{numero_du:02d}"), barras_subarvore)
    cargas_mt = filtrar_linhas_um_barramento(
        localizar_arquivo_por_prefixo(pasta_alimentador, f"CargasMT_DU{numero_du:02d}"), barras_subarvore)
    nomes_loadshapes = extrair_loadshapes_usadas(cargas_bt + cargas_mt)
    curvas = filtrar_curva_carga(localizar_arquivo_por_prefixo(pasta_alimentador, "CurvaCarga"), nomes_loadshapes)
    linecodes = _ler_linhas(localizar_arquivo_por_prefixo(pasta_alimentador, "CodCondutor"))

    (pasta_saida / "linecodes_extraido.dss").write_text("\n".join(linecodes) + "\n", encoding="utf-8")
    (pasta_saida / "linhas_extraido.dss").write_text("\n".join(linhas_mt + chaves_mt) + "\n", encoding="utf-8")
    (pasta_saida / "transformadores_extraido.dss").write_text("\n".join(transformadores) + "\n", encoding="utf-8")
    (pasta_saida / "cargas_extraido.dss").write_text("\n".join(cargas_bt + cargas_mt) + "\n", encoding="utf-8")
    (pasta_saida / "curvacarga_extraido.dss").write_text("\n".join(curvas) + "\n", encoding="utf-8")

    fase_raiz = determinar_fase_barra_raiz(linhas_mt + chaves_mt, barra_raiz)
    fonte = tensao_fonte_equivalente(dss, barra_raiz, fase_raiz)
    linhas_master = [
        "Clear",
        f'New Circuit.{nome_circuito} basekv={fonte["kv_ln"]:.6f} bus1="{barra_raiz}.{fonte["fase"]}" '
        f'phases=1 pu=1.0 angle={fonte["angulo_graus"]:.4f} frequency=60 r1=0.0 x1=0.0001',
        'Redirect "linecodes_extraido.dss"',
        'Redirect "transformadores_extraido.dss"',
        'Redirect "linhas_extraido.dss"',
        'Redirect "curvacarga_extraido.dss"',
        'Redirect "cargas_extraido.dss"',
        "Set mode=daily",
        "Set Voltagebases=[0.22 0.24 13.8]",
        "Calc Voltagebases",
        "Set tolerance=0.0001",
        "Set algorithm=newton",
        "Set maxiterations=100",
        "Set number=1",
        "Set hour=0",
        "Solve",
    ]
    caminho_master = pasta_saida / f"Master_{nome_circuito}.dss"
    caminho_master.write_text("\n".join(linhas_master) + "\n", encoding="utf-8")
    return caminho_master


def compilar_subalimentador(caminho_master: Path) -> py_dss_interface.DSS:
    """
    Compila o mini-alimentador extraido em uma nova instancia do motor
    OpenDSS.

    Entradas:
        caminho_master: Path do Master gerado por extrair_subalimentador.
    Saida:
        instancia py_dss_interface.DSS com o mini-alimentador compilado.
    """
    dss = py_dss_interface.DSS()
    dss.text(f'compile "{caminho_master}"')
    return dss
