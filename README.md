# TCC2_2026 — Localização de Faltas no Alimentador JMLT310

Código em Python do TCC2 (2026): estudo de métodos de localização de faltas
(reatância aparente, Takagi com compensação de corrente e de tensão) sobre o
alimentador de distribuição **JMLT310** (Conceição do Mato Dentro/João
Monlevade, padrão de exportação BDGD/ANEEL, mesmo usado pela Cemig), simulado
no **OpenDSS** via `py_dss_interface`.

A rede usada é a **versão reduzida** do JMLT310 (439 barras, rede secundária
eliminada e cargas BT concentradas no secundário de cada transformador — ver
`JMLT310_reduzido/LEIA-ME.txt` na pasta de dados original), o que permite
simulações e testes rápidos sem lidar com milhares de barras de baixa tensão.

## Estrutura do projeto

```
TCC2_2026/
├── main.py                     # orquestrador (CLI): roda cada secao do trabalho
├── requirements.txt
├── tcc2026/
│   ├── configuracao.py         # caminhos e parametros globais
│   ├── nucleo/                 # infraestrutura comum a todas as secoes
│   │   ├── dss_core.py         # compilar alimentador, fluxo de potencia, curva horaria
│   │   ├── grafo_alimentador.py# grafo eletrico (networkx), distancias, folhas, tronco
│   │   ├── geometria_eletrica.py # verificacao/adaptacao de LineGeometry (espacador losangular Cemig)
│   │   ├── metricas.py         # MAE, RMSE, R2, erro max/medio, desvio padrao
│   │   ├── graficos.py         # estilo seaborn padrao do projeto + salvamento com descricao
│   │   ├── latex_utils.py      # tabelas LaTeX (estilo booktabs) + .txt individuais
│   │   ├── falta_injecao.py    # objeto Fault do OpenDSS + leitura de V/I no rele
│   │   ├── amostragem_barras.py   # selecao de barras ramificacao/folha/aleatorias
│   │   └── varredura_falta_rele.py # varre uma lista de barras medindo V/I pre/pos-falta
│   ├── topologia/
│   │   └── visao_geral.py      # Secao 1: fluxo de potencia, curva horaria, topologia MT
│   ├── faltas/                 # Secao 2: tabela de 3 barras (Thevenin/curto-circuito)
│   │   ├── selecao_barras.py   # escolha das barras representativas (com/sem carga)
│   │   ├── curto_circuito.py   # Thevenin, curto 1f/3f (modo FaultStudy), V/I de operacao
│   │   └── tabela_barras.py    # orquestra a secao e gera as 3 tabelas (CSV + LaTeX)
│   ├── extracao/
│   │   └── extrator_trecho.py  # extrai um ramal como mini-alimentador .dss standalone
│   ├── reatancia/                # Secao 3/4/6b: metodo da reatancia aparente
│   │   ├── metodo_reatancia.py   # formulas: simples, compensacao K0, correcao EXATA de offset (sistema 2x2)
│   │   ├── estudo_monofasico.py  # orquestra a Secao 3 (trecho monofasico)
│   │   ├── estudo_trifasico.py   # orquestra a Secao 4 (trecho trifasico, 5 variantes)
│   │   └── estudo_compensada_corrigida.py  # orquestra a Secao 6b (alimentador inteiro)
│   ├── takagi/                   # Secao 6a: metodo de Takagi (corrente e tensao, compensado)
│   │   ├── metodo_takagi.py      # formula (com e sem compensacao K0)
│   │   └── estudo_takagi.py      # orquestra a Secao 6a (300 barras MT, 4 grupos)
│   └── resistencia_falta/
│       └── efeito_rf.py          # Secao 5: Rf no trecho 1f (10 barras) e superficie 3D no trecho 3f
└── resultados/                  # saida de cada secao: CSVs, graficos .png e tabelas .tex/.txt
```

Cada módulo expõe funções nomeadas em português (snake_case, nomes que
funcionam como comentário) e documentadas com docstrings `'''...'''`
definindo entradas, saídas e unidades.

## Pré-requisitos

- Python 3.11 (ambiente virtual em `venv/`, já configurado neste repositório
  localmente — não versionado no Git).
- **OpenDSS** instalado (motor COM `OpenDSSEngine.DSS` registrado no Windows;
  vem com a instalação padrão do EPRI OpenDSS).
- Pacote de dados do alimentador `JMLT310_reduzido` (não incluído neste
  repositório — ver variável de ambiente abaixo).

## Configuração

Por padrão, o caminho do alimentador reduzido aponta para:

```
C:\Users\nilbe\Documents\DISCIPLINAS\TCC2026\TCC2\JMLT310_reduzido\rede_reduzida
```

Para usar outra pasta, defina a variável de ambiente antes de rodar:

```bash
set TCC2026_PASTA_ALIMENTADOR=C:\caminho\para\outra\rede_reduzida
```

## Como rodar

```bash
venv\Scripts\python.exe main.py --secoes visao_geral
venv\Scripts\python.exe main.py --secoes todas
```

Seções disponíveis: `visao_geral`, `tabela_tres_barras`, `trecho_monofasico`,
`trecho_trifasico`, `resistencia_falta`, `takagi`,
`reatancia_compensada_corrigida` (ou `todas`, que roda todas em ordem — o
pipeline completo leva poucos minutos, a maior parte do tempo é a varredura
de ~300 faltas nas Seções 6a/6b).

Os resultados de cada seção são gravados em `resultados/<NN>_<secao>/`:
CSVs com os dados brutos, gráficos `.png` (seaborn, sem títulos grandes) com
descrição em `descricoes.json`, e tabelas `.tex`/`.txt` no padrão booktabs
usado no texto do TCC.

## Observação importante: geometria das linhas MT (LineGeometry)

O pacote de dados original **não define `LineGeometry` nem `WireData`** —
cada `Linecode` só traz `r1`/`x1` (sequência positiva) e `normamps`; os
valores de `r0`/`x0`/`c1`/`c0` lidos diretamente do `Linecode` (ou de uma
`Line` sem matriz/geometria própria) são o **valor padrão genérico do
OpenDSS**, não um cálculo físico real da linha (confirmado comparando-os com
o resultado de uma `Line` recém-criada sem nenhum dado — são idênticos).

Por isso, o módulo `tcc2026.nucleo.geometria_eletrica` verifica o uso de
`LineGeometry` no alimentador (`verificar_uso_linegeometry`) e, como ele está
ausente, define uma geometria de referência em **espaçador losangular**
(arranjo típico de rede compacta MT, 3 fases + mensageiro neutro reduzido),
usada para obter `R1/X1/R0/X0/C1/C0` fisicamente consistentes (por
componentes simétricas, a partir da matriz de fase calculada pelo próprio
OpenDSS para essa geometria). As dimensões do losango e o condutor de
referência (CAA 1/0 AWG) são valores típicos de catálogo, adotados por não
haver a especificação dimensional completa no pacote de dados fornecido —
ver `tcc2026/configuracao.py` (`CONDUTOR_REFERENCIA`,
`GEOMETRIA_LOSANGULAR_CEMIG`) para os valores exatos assumidos.

**Atenção para quem for estender o código:** o motor OpenDSS (COM) é um
singleton por processo — compilar o circuito auxiliar da geometria substitui
qualquer alimentador já compilado na mesma engine. A função
`calcular_parametros_sequencia_losangular_cemig()` é cacheada (`lru_cache`,
roda só uma vez por processo); mesmo assim, sempre a chame **antes** de
compilar o alimentador real num mesmo pipeline, ou recompile o alimentador
logo em seguida.

## Status

- [x] Seção 1 — Alimentador base e overview (fluxo de potência, curva
      horária, tronco/folhas/ramificações, transformadores por kVA, top-5
      linecodes, verificação/adaptação de LineGeometry).
- [x] Seção 2 — Tabela de 3 barras (Thevenin, curto monofásico/trifásico,
      parâmetros de linha e carga concentrada para os 3 circuitos
      equivalentes — ver `resultados/02_tabela_falta_tres_barras/LEIA-ME.md`).
- [x] Seção 3 — Trecho monofásico: extração automática do ramal mais
      diverso, fluxo de potência, curva horária e método da reatância
      simples (sem/com cargas) — ver `resultados/03_trecho_monofasico/LEIA-ME.md`.
- [x] Seção 4 — Trecho trifásico: extração com geometria Cemig aplicada,
      fluxo/curva horária e as 5 variantes do método da reatância
      (com/sem carga × com/sem compensação K0 × correção EXATA do offset,
      resolvendo s e Rf como sistema de 2 equações — ver Apêndice C do
      texto do TCC) — ver `resultados/04_trecho_trifasico/LEIA-ME.md`.
- [x] Seção 5 — Efeito da resistência de falta: 10 barras × 4 valores de Rf
      no trecho monofásico, e superfície 3D (Rf × diferença angular Z0/Z1)
      no trecho trifásico — ver `resultados/05_resistencia_falta/LEIA-ME.md`.
- [x] Seção 6a — Método de Takagi compensado (tensão no relé + compensação
      K0) nas 300 barras MT do alimentador, agrupadas em
      ramificação/folha/aleatória/global — ver `resultados/06_takagi/LEIA-ME.md`.
- [x] Seção 6b — Método da reatância compensada com correção EXATA do
      offset, mesma amostragem do alimentador inteiro — ver
      `resultados/07_reatancia_compensada_corrigida/LEIA-ME.md`. Com a
      correção exata, supera o Takagi (Seção 6a) nos 4 grupos de barras
      (MAE 1,4–2,4x menor); uma versão anterior com correção aproximada
      tinha viés sistemático de ~2,2 km — achado documentado no LEIA-ME.
