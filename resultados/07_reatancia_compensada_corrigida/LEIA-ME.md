# Seção 6b — Método da reatância compensada e corrigida

Gerado por
`tcc2026.reatancia.estudo_compensada_corrigida.executar_amostragem_e_estudo`,
rodando sobre o **alimentador completo** (JMLT310 reduzido, 437 barras),
com as linhas trifásicas convertidas para a geometria de referência Cemig
(mesma lógica da Seção 4/6a).

## Método

Mesma formulação da variante 5 da Seção 4 (compensação K0 + correção do
offset), agora varrida em todas as barras MT do alimentador:

```
K0_corrigido = (Z0_corrigido − Z1) / Z1
Z0_corrigido = |Z0| · exp(j·ângulo(Z1))      (anula Im(C), ver Seção 4/5)
Ia_comp = Ia + K0_corrigido · I0
Zm = Va / Ia_comp
d = Im(Zm) / X1
```

Falta monofásica-terra franca (Rf = 0,01 Ω) aplicada em todas as 300
barras MT do alimentador (exceto a origem), em uma única varredura.

## Amostragem e tabela de métricas

Mesmos 4 grupos da Seção 6a: **Ramificação** (161 barras, todas),
**Folha** (34 barras MT verdadeiras, todas), **Aleatória** (100 barras,
semente fixa 42) e **Global** (300 barras). `reatancia_compensada_metricas.csv`/
`.txt` trazem MAE/RMSE/R²/erro máx/erro médio/desvio padrão por grupo,
usando a população completa de cada um. Os gráficos de dispersão mostram
20 barras por grupo.

## Gráficos

- `reatancia_compensada_ramificacao.png` / `_folha.png` / `_aleatoria.png`:
  distância real x estimada, 20 barras por grupo.
- `reatancia_compensada_boxplot.png`: boxplot do erro, 4 grupos lado a lado.

## Resultado e limitação importante

Diferente da Seção 4 (trecho pequeno, erro médio ≈13%) e da Seção 6a
(Takagi, R² > 0,99 no alimentador inteiro), aqui o método **superestima
sistematicamente** a distância em todo o alimentador (erro médio ≈ +2,2 km,
R² negativo — ver `reatancia_compensada_metricas.csv`). Olhando o gráfico de
dispersão (ex.: `reatancia_compensada_ramificacao.png`), os pontos **não
estão espalhados**: eles caem quase exatamente sobre uma reta com
inclinação maior que a diagonal — ou seja, o método é muito **consistente**,
só está mal **calibrado** em escala de alimentador inteiro.

A causa: ao converter as linhas trifásicas para a geometria de referência
Cemig (necessário para R0/X0 fisicamente consistentes com a compensação
K0), o X1 de calibração do método passa a usar o X1 **da geometria de
referência** (≈0,30 Ω/km, condutor CAA 1/0 assumido) em vez do X1 real de
cada Linecode original do trecho percorrido (tipicamente 0,5-0,6 Ω/km neste
alimentador). Na Seção 4 (um trecho pequeno e com mistura parecida de
Linecodes) esse efeito é pequeno; aplicado ao alimentador inteiro, onde a
maior parte da extensão MT é trifásica (e portanto convertida para a
geometria), o viés se acumula proporcionalmente à distância. Em suma: o
condutor de referência adotado (ver `01_visao_geral`) não representa bem o
condutor predominante real deste alimentador — recalibrar X1 pela média
real dos Linecodes do alimentador (como a Seção 4 faz) corrigiria a maior
parte do viés, mas então a compensação K0 (que depende de R0/X0, só
disponíveis com geometria) perderia a mesma base de cálculo. É a
compensação entre as duas necessidades (X1 real vs. R0/X0 fisicamente
consistente) que fica evidenciada aqui, e vale a discussão no texto do TCC.
