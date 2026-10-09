# Seção 6b — Método da reatância compensada e corrigida (correção exata)

Gerado por
`tcc2026.reatancia.estudo_compensada_corrigida.executar_amostragem_e_estudo`,
rodando sobre o **alimentador completo** (JMLT310 reduzido, 437 barras),
com as linhas trifásicas convertidas para a geometria de referência Cemig
(mesma lógica da Seção 4/6a).

## Método

Mesma formulação da variante 5 da Seção 4 (compensação K0 + correção
**exata** do offset), agora varrida em todas as barras MT do alimentador:

```
K0 = (Z0 - Z1) / Z1
Ia_comp = Ia + K0 · I0
Zm = Va / Ia_comp
C = 3·Z1 / (2·Z1 + Z0)
d = Im(Zm · conj(C)) / Im(Z1 · conj(C))   <- correção exata (sistema 2x2)
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

## Resultado — ESTE É O ACHADO MAIS IMPORTANTE DAS SEÇÕES 4/6a/6b

Uma versão **anterior** desta seção usava uma correção **aproximada** do
offset (ajuste artificial do ângulo de Z0 para anular Im(C)) e tinha erro
médio de **+2,2 a +2,3 km** (viés sistemático, R² negativo) — pior que o
método de Takagi (Seção 6a) no mesmo alimentador.

Ao trocar para a correção **exata** (resolvendo o sistema `Zm = s·Z1 + Rf·C`
em vez de aproximar Z0), o resultado se inverteu completamente:

| Grupo | MAE (km) | R² |
|---|---|---|
| Ramificação | 0,026 | 0,9996 |
| Folha | 0,014 | 0,9999 |
| Aleatória | 0,037 | 0,9989 |
| Global | 0,037 | 0,9989 |

Comparando com a Seção 6a (Takagi, mesmas barras, mesmo Rf): a reatância
compensada com correção exata **supera o Takagi em todos os 4 grupos**
(MAE de 1,4 a 2,4 vezes menor). Isso mostra que a limitação encontrada na
versão anterior não era estrutural do método — era um artefato da
aproximação usada para corrigir o offset. Ver a discussão completa (e a
ressalva importante sobre essa comparação só ter sido feita com Rf fixo e
pequeno) no Capítulo 4 / Seção "Comparação Final" do texto do TCC.

## Gráficos

- `reatancia_compensada_ramificacao.png` / `_folha.png` / `_aleatoria.png`:
  distância real x estimada, 20 barras por grupo.
- `reatancia_compensada_boxplot.png`: boxplot do erro, 4 grupos lado a lado.
