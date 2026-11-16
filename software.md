# Software — Catálogo de Código Python

Este documento lista **todo** arquivo `.py` do repositório (exceto
`__init__.py` vazios), o que cada um faz, e as bibliotecas usadas.
Gerado a partir dos docstrings de módulo + inspeção de imports.

## Bibliotecas

### Terceiros (ver `requirements.txt`)

| Biblioteca | Versão fixada | Uso no projeto |
|---|---|---|
| `py-dss-interface` | 2.3.0 | Motor de simulação — bindings Python para o OpenDSS (COM, Windows). Toda interação com o alimentador passa por aqui. |
| `pandas` | 3.0.6 | Tabelas de resultados (DataFrames), CSVs de saída. |
| `numpy` | 2.4.6 | Álgebra numérica auxiliar (poucos usos diretos; principalmente via pandas/matplotlib). |
| `networkx` | 3.6.1 | Grafo elétrico do alimentador (`tcc2026/nucleo/grafo_alimentador.py`) — distâncias, folhas, caminhos. |
| `matplotlib` | 3.11.2 | Geração de gráficos e mapas geográficos. |
| `seaborn` | 0.13.2 | Estilo visual padronizado dos gráficos (`tcc2026/nucleo/graficos.py`). |
| `scipy` | 1.17.1 | Listada no `requirements.txt`; não encontrada em nenhum `import` direto do código do projeto no momento desta documentação — possivelmente dependência transitiva de outro pacote, ou reservada para uso futuro (ex.: regressão na análise de sensibilidade, que hoje usa só aritmética simples). |

### Biblioteca padrão usada

`argparse`, `cmath` (fasores complexos — base de quase todos os cálculos
elétricos), `collections.Counter`, `csv`, `functools.lru_cache`, `json`,
`math`, `os`, `pathlib.Path`, `random` (amostragem com semente fixa),
`re`, `statistics`.

### Requisito não-Python

**OpenDSS** precisa estar instalado e registrado como engine COM
(`OpenDSSEngine.DSS`) no Windows — é o que `py_dss_interface` controla.
Sem isso, nenhum script roda.

---

## `main.py`

Orquestrador/CLI. Importa cada módulo de "estudo" (`estudo_*`,
`executar_*`) e expõe um dicionário `SECOES_DISPONIVEIS` mapeando um nome
de seção → (subpasta de resultados, função a rodar). `--secoes todas` roda
tudo em ordem. Cada seção grava em `resultados/<NN>_<nome>/`.

Seções registradas atualmente (11, numeradas pela ordem de execução):

1. `visao_geral` → `01_visao_geral`
2. `tabela_tres_barras` → `02_tabela_falta_tres_barras`
3. `trecho_monofasico` → `03_trecho_monofasico`
4. `trecho_trifasico` → `04_trecho_trifasico`
5. `resistencia_falta` → `05_resistencia_falta`
6. `takagi` → `06_takagi`
7. `reatancia_compensada_corrigida` → `07_reatancia_compensada_corrigida`
8. `votacao_multifolha` → `08_votacao_multifolha`
9. `analise_linecodes` → `09_analise_linecodes`
10. `analise_sensibilidade` → `10_analise_sensibilidade`
11. `rf_sweep_comparativo` → `11_rf_sweep_comparativo`

---

## `tcc2026/configuracao.py`

Constantes globais: caminho do alimentador (sobrescrevível por
`TCC2026_PASTA_ALIMENTADOR`), tensão/frequência base, semente aleatória
padrão, parâmetros da geometria de referência losangular (`CONDUTOR_REFERENCIA`,
`GEOMETRIA_LOSANGULAR_CEMIG`) e dados reais da subestação a montante
(`SUBESTACAO`, fonte EPE-DEE-NT-094/2017).

---

## `tcc2026/nucleo/` — infraestrutura comum

| Arquivo | O que faz |
|---|---|
| `dss_core.py` | Camada fina sobre `py_dss_interface`: localizar/compilar o Master, resolver fluxo de potência (snapshot ou curva horária 24h), aplicar a impedância real da subestação (`aplicar_impedancia_fonte_real`), escalar carregamento (`escalar_carregamento`, com proteção contra o bug de `LoadMult=0` — ver nota em `plano_implementacao.md`), extrair resumo de potência/perdas/tensão. |
| `grafo_alimentador.py` | Constrói o grafo elétrico (NetworkX) do alimentador a partir do circuito OpenDSS compilado: barras MT, ligações transformador primário-secundário, distâncias desde a origem, classificação de barras (folha/ramificação), caminho entre duas barras. |
| `geometria_eletrica.py` | Verifica se o alimentador usa `LineGeometry` real (não usa) e calcula R1/X1/R0/X0/C1/C0 de uma geometria de referência em espaçador losangular Cemig, via componentes simétricas sobre a matriz de fase que o próprio OpenDSS calcula para essa geometria. Resultado cacheado (`lru_cache`) — chamar antes de compilar o alimentador real no mesmo processo. |
| `metricas.py` | MAE, RMSE, R², erro máximo, erro médio (viés), desvio padrão — comparando distância real × estimada. |
| `graficos.py` | Estilo seaborn padrão do projeto (sóbrio, sem títulos grandes) + utilitário de salvar figura com descrição registrada em `descricoes.json`. |
| `latex_utils.py` | Gera tabelas LaTeX estilo booktabs (vírgula decimal `{,}`), grava também um `.txt` individual com contexto. |
| `mapa_geografico.py` | Desenha o alimentador (linhas + barras) sobre longitude/latitude (`buscoords.csv`), com opção de destacar um subconjunto de barras. |
| `falta_injecao.py` | Cria/aplica/remove o objeto `Fault` do OpenDSS (monofásico-terra ou trifásico) e lê tensão/corrente "no relé" (barra de origem), inclusive a corrente de sequência zero. |
| `amostragem_barras.py` | Seleciona barras de ramificação, folha e aleatórias (semente fixa) para os estudos de validação. |
| `varredura_falta_rele.py` | Para uma lista de barras: aplica falta monofásica-terra, resolve, lê fasores pré/pós-falta no relé — base comum do Takagi e da reatância compensada. |
| `avaliacao_multifolha.py` | Algoritmo 1 (avalia um caminho relé-folha candidato) aplicado contra **todas** as folhas candidatas, não só a correta; Algoritmo 3 (consolidação por votação: cada caminho válido vota na barra mais próxima do seu caminho, vence a mais votada). Usado por `takagi/estudo_votacao.py`. |

---

## `tcc2026/topologia/visao_geral.py` (Seção 1)

Fluxo de potência, curva horária 24h, topologia MT (tronco/folhas/
ramificações), transformadores por kVA, top-5 linecodes, verificação da
geometria de linha.

## `tcc2026/faltas/` (Seção 2)

| Arquivo | O que faz |
|---|---|
| `selecao_barras.py` | Escolhe 3 barras representativas: primeira com carga, barra com carga mais distante, folha sem carga. |
| `curto_circuito.py` | Equivalente de Thevenin, V/I de operação, curto monofásico/trifásico via modo `FaultStudy` do OpenDSS, para qualquer barra. |
| `tabela_barras.py` | Orquestra a Seção 2: monta a tabela das 3 barras com todos os dados acima (CSV + LaTeX) — insumo para 3 circuitos equivalentes manuais no texto do TCC. |

## `tcc2026/extracao/extrator_trecho.py`

Extrai um ramal (sub-árvore do grafo) como mini-alimentador `.dss`
standalone: filtra o texto dos arquivos originais preservando a sintaxe
exata, mantém só os elementos cujas barras pertencem ao recorte, e cria um
novo `Master` com fonte de tensão equivalente (tensão real observada ali
no alimentador completo). Suporta converter trechos trifásicos/monofásicos
para a geometria de referência Cemig (`usar_geometria_cemig_trifasica`/
`_monofasica`). **Não copia objetos `PVSystem`/geração distribuída** —
relevante para quem for reutilizá-lo em estudos com GD.

## `tcc2026/reatancia/` (Seções 3, 4, 6b)

| Arquivo | O que faz |
|---|---|
| `metodo_reatancia.py` | As fórmulas: `distancia_reatancia_simples` (sem compensação), `fator_compensacao_k0` + `corrente_compensada` + `distancia_reatancia_compensada` (com K0), `distancia_reatancia_corrigida_exata` + `resistencia_falta_estimada_exata` (correção exata do offset de Rf, resolvendo um sistema linear 2×2 real — ver Apêndice C do texto). |
| `estudo_monofasico.py` | Seção 3: trecho monofásico — extração, fluxo, curva horária, reatância simples (sem/com carga). |
| `estudo_trifasico.py` | Seção 4: trecho trifásico — 5 variantes (com/sem carga × com/sem K0 × correção de offset). |
| `estudo_compensada_corrigida.py` | Seção 6b: reatância compensada e corrigida nas 300 barras MT do alimentador completo (mesma amostragem da Seção 6a). |

## `tcc2026/takagi/` (Seções 6a, 8)

| Arquivo | O que faz |
|---|---|
| `metodo_takagi.py` | Fórmula de Takagi adaptada (tensão lida direto no relé): `distancia_takagi` e `distancia_takagi_compensado` (com K0). |
| `estudo_takagi.py` | Seção 6a: Takagi compensado nas 300 barras MT, agrupado em ramificação/folha/aleatória/global; também avalia o Algoritmo 1 em modo multi-folha real. |
| `estudo_votacao.py` | Seção 8: Algoritmo 3 (votação multi-folha) comparando Takagi × reatância corrigida nas 300 barras. |

## `tcc2026/resistencia_falta/efeito_rf.py` (Seção 5)

Efeito de Rf: 10 barras × 5 valores de Rf (0,01/10/25/50/100 Ω — faixa de
literatura, GABR et al. 2017 e DAVI/OLESKOVICZ/LOPES 2023) no trecho
monofásico; superfície 3D analítica (Rf × diferença angular Z0/Z1) no
trecho trifásico.

## `tcc2026/sensibilidade/analise_sensibilidade.py` (Seção 10)

Sensibilidade formal `S = (∂d/∂p)·(p/d)` dos dois métodos a três
parâmetros: Rf (forma fechada quando possível), carregamento e R1 de
referência (regressão/perturbação finita quando não há forma fechada).

## `tcc2026/analise_linecodes/analise_linecodes.py` (Seção 9)

Ranking dos linecodes reais por quilometragem no alimentador; cruza com os
erros já calculados (Seções 6a/6b) para achar quais condutores atípicos
mais se associam a erro; exporta coordenadas dos piores casos para inspeção
visual manual (fora do pipeline automatizado).

## `tcc2026/comparacao/rf_sweep_comparativo.py` (Seção 11)

Takagi × reatância corrigida, calculados a partir dos **mesmos fasores**
simulados (mesma falta, mesma barra, mesmo Rf) nas 300 barras MT, varrendo
Rf de 0,01 a 100 Ω — fecha a comparação da Seção 6 que só usava Rf=0,01 Ω.

---

## Nota sobre o código da frente de GD (fora deste repositório)

A investigação de geração distribuída (ver `plano_implementacao.md`) roda
sobre scripts **fora deste repositório Git**, em
`C:\Users\nilbe\Documents\DISCIPLINAS\TCC2026\TCC2\JMLT310_reduzido_com_GD\`
e pastas irmãs (`JMLT310_completo_com_GD`, `JMLT306`, `JMLT309`), e em
scripts ad-hoc no scratchpad de sessões do Claude Code (não versionados).
Reaproveita as funções deste pacote (`dss_core`, `grafo_alimentador`,
`avaliacao_multifolha`, `metodo_takagi`, `metodo_reatancia`) apontando
`TCC2026_PASTA_ALIMENTADOR` para essas pastas alternativas, sem nunca
alterar os arquivos deste repositório. Se decidir formalizar essa frente,
o lugar natural seria um novo subpacote `tcc2026/geracao_distribuida/` e
uma nova seção no `main.py`.
