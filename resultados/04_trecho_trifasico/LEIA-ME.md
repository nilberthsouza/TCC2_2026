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
5. **Compensação K0 + correção EXATA do offset, sem cargas** — resolve
   `Zm = s·Z1 + Rf·C` (com `C = 3·Z1/(2·Z1+Z0)`) como sistema de duas
   equações reais e duas incógnitas (`s` e `Rf`), multiplicando por
   `conj(C)` e tomando a parte imaginária:
   `s_hat = Im(Zm·conj(C)) / Im(Z1·conj(C))`
   (ver `tcc2026.reatancia.metodo_reatancia.distancia_reatancia_corrigida_exata`
   e a dedução completa no Apêndice C do texto do TCC). Essa correção
   **substituiu** uma versão anterior, aproximada, que ajustava
   artificialmente o ângulo de Z0 para anular `Im(C)` — a correção exata é
   dramaticamente melhor (ver resultado abaixo).

Todas as variantes usam o mesmo X1 de referência (`reatancia_metricas.csv`
traz o valor, média ponderada pelos Linecodes reais do trecho), para que a
diferença entre elas venha só da corrente/fórmula usada, não de uma
calibração diferente.

## Resultado (ver `reatancia_metricas.csv`/`.txt`)

| Variante | MAE (km) | R² | Erro médio (%) |
|---|---|---|---|
| Sem compensação | 0,774 | -7,64 | 73,7 |
| Compensação K0 | 0,164 | 0,598 | -15,6 |
| Compensação K0 + correção **exata** | **0,021** | **0,981** | **-2,0** |

O método **sem compensação** erra sistematicamente e muito (ignora o
caminho de retorno pela terra). A **compensação K0** reduz bastante o erro,
mas ainda carrega o offset proporcional a Rf. A **correção exata** do
offset praticamente elimina o erro restante — uma melhora de quase uma
ordem de grandeza em relação à compensação K0 sozinha, e muito superior à
correção aproximada testada anteriormente (que só chegava a MAE ≈ 0,14 km,
R² ≈ 0,71).

## Gráficos

- `reatancia_real_vs_estimado.png`: distância real x estimada, 5 variantes.
- `reatancia_boxplot.png`: boxplot do erro (estimado − real), 5 variantes lado a lado.
- `trecho_isolado.png` / `trecho_destacado_no_alimentador.png`: topologia
  esquemática (layout de grafo, não geográfico) do trecho.
