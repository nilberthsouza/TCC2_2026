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
from tcc2026.nucleo import geometria_eletrica as ge
from tcc2026.nucleo import grafo_alimentador as ga

_PADRAO_BUS1 = re.compile(r'bus1="([^".]+)')
_PADRAO_BUS2 = re.compile(r'bus2="([^".]+)')
_PADRAO_PRIMEIRA_BUS_TRAFO = re.compile(r'buses=\[\s*"([^".]+)')
_PADRAO_LOADSHAPE = re.compile(r'(?:daily|yearly)="([^"]+)"')
_PADRAO_NOME_LOADSHAPE = re.compile(r'New "Loadshape\.([^"]+)"')
_PADRAO_LINECODE_3F = re.compile(r'linecode="[^"]+"')


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


def determinar_fases_barra_raiz(linhas_relevantes: list[str], barra_raiz: str) -> list[int]:
    """
    Determina o(s) numero(s) de fase (1/2/3) da barra_raiz dentro do trecho
    extraido, a partir dos sufixos de no das linhas mantidas que a
    referenciam. Necessario porque, no alimentador completo, a barra_raiz
    pode ser um ponto de transicao com mais fases ativas do que as
    realmente usadas pelo trecho extraido.

    Entradas:
        linhas_relevantes: linhas de texto "New Line..." ja filtradas para
            o trecho (ver filtrar_linhas_dois_barramentos).
        barra_raiz: nome da barra raiz do trecho (sem sufixo de fase).
    Saida:
        lista ordenada de numeros de fase (ex.: [2] ou [1, 2, 3]).
    """
    padrao = re.compile(re.escape(barra_raiz) + r'\.([123](?:\.[123]){0,2})', re.IGNORECASE)
    fases = set()
    for linha in linhas_relevantes:
        m = padrao.search(linha)
        if m:
            fases.update(int(f) for f in m.group(1).split("."))
    if not fases:
        raise ValueError(f"Nao foi possivel determinar as fases de {barra_raiz} nas linhas do trecho.")
    return sorted(fases)


def converter_linhas_trifasicas_para_geometria_cemig(linhas: list[str],
                                                       nome_geometria: str = "GEOM_LOSANG_CEMIG") -> list[str]:
    """
    Troca, nas linhas trifasicas (phases=3), o Linecode original por
    geometry=<nome_geometria> (espacador losangular padrao Cemig). Usado
    para que a simulacao da falta trifasica tenha R0/X0 fisicamente
    consistentes (os Linecodes originais so trazem r1/x1; r0/x0/c0/c1 sem
    geometria caem no valor generico padrao do OpenDSS, nao em um calculo
    fisico real — ver tcc2026.nucleo.geometria_eletrica). Trechos de 1 ou 2
    fases (ramais dentro do trecho trifasico) ficam com o Linecode original.

    Entradas:
        linhas: linhas de texto "New Line..."/chaves ja filtradas para o trecho.
        nome_geometria: nome do LineGeometry a referenciar (deve ser
            definido no arquivo redirecionado antes destas linhas, ver
            tcc2026.nucleo.geometria_eletrica.texto_definicao_geometria_losangular_cemig).
    Saida:
        lista de linhas de texto com phases=3 convertidas para geometry=.
    """
    convertidas = []
    for linha in linhas:
        if "phases=3" in linha and _PADRAO_LINECODE_3F.search(linha):
            linha = _PADRAO_LINECODE_3F.sub(f"geometry={nome_geometria}", linha)
        convertidas.append(linha)
    return convertidas


def tensao_fonte_equivalente(dss: py_dss_interface.DSS, barra_raiz: str, fases: list[int]) -> dict:
    """
    Le a tensao real (magnitude e angulo) observada na barra_raiz, nas
    fases informadas, no alimentador completo ja resolvido, para usar como
    fonte de tensao equivalente (Thevenin) do mini-alimentador extraido.
    Para uma raiz trifasica, a fonte equivalente e balanceada (modulo =
    media das 3 fases em pu, angulo = o da fase 1), uma simplificacao
    razoavel para o Thevenin de um trecho pequeno.

    Entradas:
        dss: instancia do motor OpenDSS do alimentador completo, ja
            resolvida em fluxo de potencia normal.
        barra_raiz: barra onde o trecho extraido comeca.
        fases: lista de fases ativas na raiz (ver determinar_fases_barra_raiz).
    Saida:
        dicionario com fases (list[int]), kv_ln (tensao fase-neutro de
        referencia, kV), pu (modulo em pu da base fase-neutro) e
        angulo_graus (angulo da fase de referencia, graus).
    """
    dss.circuit.set_active_bus(barra_raiz)
    bus = dss.bus
    kv_base_ln = bus.kv_base
    magnitudes_pu, angulos = [], []
    for fase in fases:
        indice = list(bus.nodes).index(fase)
        v_complexo = complex(bus.voltages[2 * indice], bus.voltages[2 * indice + 1])
        magnitudes_pu.append(abs(v_complexo) / 1000.0 / kv_base_ln)
        angulos.append(float(np.angle(v_complexo, deg=True)))
    return {
        "fases": fases,
        "kv_ln": kv_base_ln,
        "pu": float(np.mean(magnitudes_pu)),
        "angulo_graus": angulos[0],
    }


def extrair_subalimentador(dss: py_dss_interface.DSS, barra_raiz: str, barras_subarvore: set,
                            pasta_saida: Path, nome_circuito: str,
                            pasta_alimentador: Path = PASTA_ALIMENTADOR_REDUZIDO,
                            numero_du: int = NUMERO_DU_PADRAO,
                            usar_geometria_cemig_trifasica: bool = False) -> Path:
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
        usar_geometria_cemig_trifasica: se True, troca o Linecode das linhas
            trifasicas (phases=3) pela geometria de referencia em espacador
            losangular Cemig, para que R0/X0 (e portanto a corrente de
            sequencia zero em faltas monofasicas-terra) sejam fisicamente
            consistentes com o metodo de compensacao K0 (ver
            tcc2026.reatancia.estudo_trifasico). Sem isso, o R0/X0 usado na
            simulacao seria o valor generico padrao do OpenDSS (nao um
            calculo fisico real), inconsistente com a compensacao.
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

    if usar_geometria_cemig_trifasica:
        linhas_mt = converter_linhas_trifasicas_para_geometria_cemig(linhas_mt)
        chaves_mt = converter_linhas_trifasicas_para_geometria_cemig(chaves_mt)
        (pasta_saida / "geometria_cemig.dss").write_text(
            "\n".join(ge.texto_definicao_geometria_losangular_cemig()) + "\n", encoding="utf-8")

    (pasta_saida / "linecodes_extraido.dss").write_text("\n".join(linecodes) + "\n", encoding="utf-8")
    (pasta_saida / "linhas_extraido.dss").write_text("\n".join(linhas_mt + chaves_mt) + "\n", encoding="utf-8")
    (pasta_saida / "transformadores_extraido.dss").write_text("\n".join(transformadores) + "\n", encoding="utf-8")
    (pasta_saida / "cargas_extraido.dss").write_text("\n".join(cargas_bt + cargas_mt) + "\n", encoding="utf-8")
    (pasta_saida / "curvacarga_extraido.dss").write_text("\n".join(curvas) + "\n", encoding="utf-8")

    fases_raiz = determinar_fases_barra_raiz(linhas_mt + chaves_mt, barra_raiz)
    fonte = tensao_fonte_equivalente(dss, barra_raiz, fases_raiz)
    num_fases = len(fases_raiz)
    sufixo_bus = ".".join(str(f) for f in fases_raiz)
    basekv = fonte["kv_ln"] if num_fases == 1 else fonte["kv_ln"] * 3 ** 0.5
    linhas_master = [
        "Clear",
        f'New Circuit.{nome_circuito} basekv={basekv:.6f} bus1="{barra_raiz}.{sufixo_bus}" '
        f'phases={num_fases} pu={fonte["pu"]:.6f} angle={fonte["angulo_graus"]:.4f} '
        f'frequency=60 r1=0.0 x1=0.0001',
        'Redirect "linecodes_extraido.dss"',
        *(['Redirect "geometria_cemig.dss"'] if usar_geometria_cemig_trifasica else []),
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
