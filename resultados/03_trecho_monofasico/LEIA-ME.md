# Seção 3 — Trecho monofásico (JMLT310)

Gerado por `tcc2026.reatancia.estudo_monofasico.executar_estudo_monofasico`.

## Trecho escolhido

Selecionado automaticamente (`grafo_alimentador.selecionar_trecho_monofasico_mais_diverso`)
entre todos os trechos estritamente monofásicos do alimentador: o de maior
diversidade topológica (mais barras, ramificações e transformadores).
Raiz do trecho: barra onde ele se deriva da rede trifásica — ver
`subalimentador/Master_MINI_1F.dss` para o mini-alimentador standalone
gerado (linhas, transformadores MRT e cargas filtrados dos arquivos
originais, fonte de tensão equivalente na tensão real observada ali no
alimentador completo). 7 transformadores monofásicos MRT, ~227,5 kVA
instalados.

## Fluxo de potência e curva horária

`fluxo_potencia_resumo.csv` (ponto de operação padrão) e `curva_horaria.csv`
+ gráficos `curva_*.png` (24 h, modo daily). As perdas do trecho são
dominadas pelas perdas a vazio (núcleo) dos 7 transformadores MRT, que são
praticamente fixas e grandes frente à carga leve do trecho — por isso o
percentual de perdas aparece alto (~65-70%) mesmo com pouca potência
entregue; não é um erro de modelagem, é a característica real de um ramal
rural pouco carregado.

## Método da reatância aparente (simples, sem compensação)

`reatancia_resultados.csv`: para cada barra MT do trecho, uma falta
monofásica-terra franca (Rf = 0,01 Ω) é aplicada e a distância é estimada
por `d = Im(V/I) / X1`, com X1 calibrado pela média ponderada (por
comprimento) dos Linecodes reais do trecho (`reatancia_metricas.csv`/`.txt`
trazem X1 implícito e as métricas MAE/RMSE/R²/erro máx/erro médio/desvio
padrão, em km e %, para os cenários "sem cargas" e "com cargas").

Os dois cenários deram praticamente o mesmo erro aqui: como a carga
nominal do trecho é pequena (poucos kW) frente à corrente de curto, a
corrente de carga pré-falta tem efeito desprezível sobre a medição no relé
— um resultado esperado para um ramal levemente carregado, não um erro de
implementação.

## Gráficos

- `reatancia_real_vs_estimado.png`: distância real x estimada (sem/com carga).
- `reatancia_boxplot.png`: boxplot do erro (estimado − real), sem x com carga.
- `trecho_isolado.png`: topologia esquemática (layout de grafo, **não**
  geográfico — o pacote de dados não traz coordenadas completas para esse
  nível de zoom) só do trecho monofásico.
- `trecho_destacado_no_alimentador.png`: o mesmo trecho (vermelho) destacado
  dentro da topologia completa do alimentador.
