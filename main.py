"""
Orquestrador principal do projeto TCC2_2026: localizacao de faltas no
alimentador JMLT310 (rede reduzida). Cada secao do trabalho roda de forma
independente e grava seus resultados em resultados/<NN>_<secao>/.

Uso:
    python main.py --secoes visao_geral
    python main.py --secoes todas
"""
import argparse
from pathlib import Path

from tcc2026.configuracao import PASTA_RESULTADOS
from tcc2026.topologia import visao_geral
from tcc2026.faltas import tabela_barras
from tcc2026.reatancia import estudo_compensada_corrigida, estudo_monofasico, estudo_trifasico
from tcc2026.resistencia_falta import efeito_rf
from tcc2026.takagi import estudo_takagi

SECOES_DISPONIVEIS = {
    "visao_geral": ("01_visao_geral", lambda pasta: visao_geral.executar_visao_geral(pasta)),
    "tabela_tres_barras": ("02_tabela_falta_tres_barras", lambda pasta: tabela_barras.executar_tabela_barras(pasta)),
    "trecho_monofasico": ("03_trecho_monofasico", lambda pasta: estudo_monofasico.executar_estudo_monofasico(pasta)),
    "trecho_trifasico": ("04_trecho_trifasico", lambda pasta: estudo_trifasico.executar_estudo_trifasico(pasta)),
    "resistencia_falta": ("05_resistencia_falta", lambda pasta: efeito_rf.executar_efeito_resistencia_falta(pasta)),
    "takagi": ("06_takagi", lambda pasta: estudo_takagi.executar_amostragem_e_estudo(pasta)),
    "reatancia_compensada_corrigida": (
        "07_reatancia_compensada_corrigida",
        lambda pasta: estudo_compensada_corrigida.executar_amostragem_e_estudo(pasta)),
}


def executar_secoes(nomes_secoes: list[str], pasta_resultados: Path = PASTA_RESULTADOS) -> None:
    """
    Executa, em sequencia, as secoes do trabalho solicitadas.

    Entradas:
        nomes_secoes: lista com os nomes das secoes a rodar (chaves de
            SECOES_DISPONIVEIS), ou ["todas"] para rodar todas em ordem.
        pasta_resultados: pasta raiz onde cada secao grava sua subpasta.
    Saida:
        nenhuma (efeitos colaterais: arquivos gravados em disco e
        mensagens de progresso impressas no terminal).
    """
    if nomes_secoes == ["todas"]:
        nomes_secoes = list(SECOES_DISPONIVEIS.keys())
    for nome in nomes_secoes:
        if nome not in SECOES_DISPONIVEIS:
            disponiveis = ", ".join(SECOES_DISPONIVEIS.keys())
            raise ValueError(f"Secao '{nome}' desconhecida. Disponiveis: {disponiveis}")
        subpasta, funcao = SECOES_DISPONIVEIS[nome]
        pasta_saida = pasta_resultados / subpasta
        print(f"==> Executando secao '{nome}' -> {pasta_saida}")
        funcao(pasta_saida)
        print(f"==> Secao '{nome}' concluida.")


def main() -> None:
    """
    Ponto de entrada de linha de comando do orquestrador.

    Entradas:
        nenhuma (le argumentos de --secoes na linha de comando).
    Saida:
        nenhuma.
    """
    analisador = argparse.ArgumentParser(description=__doc__)
    analisador.add_argument(
        "--secoes", nargs="+", default=["todas"],
        help=f"Secoes a executar: {', '.join(SECOES_DISPONIVEIS.keys())} ou 'todas'.",
    )
    argumentos = analisador.parse_args()
    executar_secoes(argumentos.secoes)


if __name__ == "__main__":
    main()
