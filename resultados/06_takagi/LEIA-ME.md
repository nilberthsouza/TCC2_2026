# Seção 6 — Método de Takagi (compensação de corrente, tensão no relé)

Gerado por `tcc2026.takagi.estudo_takagi.executar_amostragem_e_estudo`,
rodando sobre o **alimentador completo** (JMLT310 reduzido, 437 barras),
com as linhas trifásicas convertidas para a geometria de referência Cemig
(`alimentador_geometria_cemig/`, mesma lógica da Seção 4) para que R0/X0
sejam fisicamente consistentes com a compensação K0.

## Método

Adaptação do método 1 (por corrente) do artigo de referência: em vez de
localizar a falta só por corrente, a tensão é lida diretamente na barra do
relé (origem do alimentador) e a corrente de fase é compensada pela
sequência zero antes de aplicar a fórmula de Takagi:

```
Icomp = Ia + K0·I0           (antes e depois da falta)
ΔIcomp = Icomp_falta − Icomp_pré-falta
m = Im(Va·ΔIcomp*) / Im(Z1·Icomp_falta·ΔIcomp*)   (Z1 em Ω/km → m já em km)
```

Uma falta monofásica-terra franca (Rf = 0,01 Ω) é aplicada em **todas as
300 barras MT** do alimentador (exceto a origem) em uma única varredura;
os resultados são depois agrupados por categoria.

## Amostragem e tabela de métricas

- **Ramificação**: todas as 161 barras de ramificação (grau ≥ 3).
- **Folha**: todas as 34 barras folha MT verdadeiras (fim de ramal, sem
  transformador — barras folha que são secundário de transformador são BT
  e não entram em um estudo de falta MT).
- **Aleatória**: amostra de 100 barras (semente fixa 42) entre todas as MT.
- **Global**: todas as 300 barras MT.

`takagi_metricas.csv`/`.txt` trazem MAE/RMSE/R²/erro máx/erro médio/desvio
padrão para cada grupo, usando a **população completa** de cada categoria
(não só as 20 plotadas). Os gráficos de dispersão (`takagi_ramificacao.png`,
`takagi_folha.png`, `takagi_aleatoria.png`) mostram 20 barras de cada grupo
(distribuídas por distância, ou a mesma amostra aleatória de 20 de 100).

## Resultado

O método acerta muito bem em todo o alimentador: R² entre 0,992 e 0,9998,
erro médio entre -0,03 km e -0,09 km (tendência de sub-estimar um pouco a
distância), erro máximo absoluto de 1,25 km no grupo global (ver
`takagi_boxplot.png` para a distribuição completa do erro nos 4 grupos).
