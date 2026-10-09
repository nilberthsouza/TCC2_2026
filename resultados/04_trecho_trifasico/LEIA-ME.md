# Seção 4 — Trecho trifásico (JMLT310)

Gerado por `tcc2026.reatancia.estudo_trifasico.executar_estudo_trifasico`.

## Trecho escolhido

Selecionado automaticamente (`grafo_alimentador.selecionar_trecho_trifasico_pequeno`):
entre as barras de ramificação da rede trifásica, a que gera uma sub-árvore
pequena (6 a 30 barras) com mais transformadores — 29 barras, 10
transformadores. Ver `subalimentador/Master_MINI_3F.dss`.

**Importante**: as linhas trifásicas deste trecho foram reconstruídas com a
geometria de referência em espaçador losangular Cemig (`geometria_cemig.dss`,
`geometry=GEOM_LOSANG_CEMIG` no lugar do `Linecode` original) em vez de
mantidas com o Linecode original. Isso é necessário porque os Linecodes do
alimentador só trazem r1/x1 — sem LineGeometry, o R0/X0 usado pelo OpenDSS
seria o valor genérico padrão do programa (não um cálculo físico real, ver
`01_visao_geral`), o que tornaria a corrente de sequência zero (e portanto
a compensação K0) sem sentido físico. Ramais de 1 ou 2 fases dentro do
trecho mantêm o Linecode original.

## Método da reatância aparente — 5 variantes

Para cada barra MT do trecho, uma falta monofásica-terra (Rf = 0,01 Ω, na
fase realmente presente naquela barra) é simulada e a distância é estimada
por 5 variantes (`reatancia_resultados.csv`, formato longo):

1. **Sem compensação, sem cargas** — `d = Im(Va/Ia) / X1`.
2. **Sem compensação, com cargas** — idem, com as cargas nominais ligadas.
3. **Compensação K0, sem cargas** — `Ia_comp = Ia + K0·I0`,
   `d = Im(Va/Ia_comp) / X1`, com `K0 = (Z0-Z1)/Z1` calculado pela geometria
   de referência Cemig.
4. **Compensação K0, com cargas** — idem, com cargas.
5. **Compensação K0 + correção do offset, sem cargas** — usa um Z0
   "corrigido" (mesmo módulo, ângulo igualado ao de Z1) para anular
   `Im(C)` (`C = 3·Z1/(2·Z1+Z0)`), eliminando o offset que `Rf·Im(C)`
   introduziria na parte imaginária de Zm quando `∠Z0 ≠ ∠Z1`.

Todas as variantes usam o mesmo X1 de referência (`reatancia_metricas.csv`
traz o valor, média ponderada pelos Linecodes reais do trecho), para que a
diferença entre elas venha só da corrente usada na fórmula, não de uma
calibração diferente.

## Resultado (ver `reatancia_metricas.csv`/`.txt`)

O método **sem compensação** erra sistematicamente e muito (≈74% de erro
médio, R² negativo) — esperado: ele ignora completamente o caminho de
retorno pela terra (sequência zero) de uma falta monofásica-terra. A
**compensação K0** reduz o erro médio para ≈16%, e a **correção do offset**
reduz ainda mais, para ≈13%, com o menor desvio padrão entre as 5
variantes — exatamente o comportamento esperado pela teoria (ver
`reatancia_real_vs_estimado.png`: os pontos "sem compensação" ficam bem
acima da diagonal; os compensados, grudados nela).

## Gráficos

- `reatancia_real_vs_estimado.png`: distância real x estimada, 5 variantes.
- `reatancia_boxplot.png`: boxplot do erro (estimado − real), 5 variantes lado a lado.
- `trecho_isolado.png` / `trecho_destacado_no_alimentador.png`: topologia
  esquemática (layout de grafo, não geográfico) do trecho.
