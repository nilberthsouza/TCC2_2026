# Seção 2 — Tabela de 3 barras representativas (Thevenin / curto-circuito)

Gerado por `tcc2026.faltas.tabela_barras.executar_tabela_barras`.

## Barras selecionadas (ver `barras_selecionadas.csv`)

- **Caso 1** — primeira barra com carga conectada (mais próxima da origem
  entre as barras MT que têm um transformador ou uma carga MT ligada
  diretamente): `NODE#2566408161`, 0,751 km da origem.
- **Caso 2** — barra com carga conectada mais distante da origem:
  `NODE#445010762`, 8,399 km (praticamente o próprio "tronco" do
  alimentador, ver `01_visao_geral`).
- **Caso 3** — barra folha MT (fim de ramal, sem transformador) sem
  nenhuma carga conectada: `NODE#1194264563`, 8,079 km. A última carga do
  mesmo ramal, usada no circuito equivalente, é `NODE#445010992`.

## Circuitos equivalentes (para montar no Simulink)

- **Casos 1 e 2**: fonte de tensão → linha (`tabela_parametros_linha.csv`,
  segmento "fonte até a barra") → disjuntor → medição → carga concentrada
  (`tabela_cargas_concentradas.csv`).
- **Caso 3**: fonte de tensão → linha até a última carga do ramal → carga
  concentrada → linha até a barra da falta (sem carga). Os dois segmentos
  de linha ficam em `tabela_parametros_linha.csv`, com rótulos "fonte até a
  última carga do ramal" e "última carga até a barra da falta".

## Tabelas

- `tabela_principal.csv`/`.txt`: tensão de operação (pu), corrente de
  operação na barra (A), impedância de Thevenin de sequência positiva e
  zero (Z1/Z0, Ω) e correntes de curto-circuito trifásico e
  monofásico-terra francos (Ω) em cada uma das 3 barras.
- `tabela_parametros_linha.csv`/`.txt`: r1/x1/r0/x0/c1/c0 e distância (km)
  de cada segmento de linha dos 3 circuitos equivalentes, calculados com a
  geometria de referência em espaçador losangular Cemig (ver
  `01_visao_geral` e `tcc2026/nucleo/geometria_eletrica.py` — o alimentador
  original não define LineGeometry).
- `tabela_cargas_concentradas.csv`/`.txt`: potência ativa e reativa (QL
  indutivo / Qc capacitivo) e corrente média a jusante de cada ponto de
  carga concentrada.
- `impedancia_subestacao.csv`: impedância de Thevenin equivalente da
  subestação (r1/x1/r0/x0, Ω, base 13,8 kV) aplicada à fonte do circuito —
  ver observação abaixo.

## Observação sobre a impedância da fonte equivalente

O `New Circuit...` do alimentador, tal como exportado da BDGD, usa uma
fonte praticamente ideal (`r1=0, x1=0.0001`), sem impedância de
transformador de subestação modelada. Isso foi corrigido: antes de
resolver o fluxo de potência, `dss_core.compilar_alimentador()` substitui
a fonte pela impedância de Thevenin real da subestação que atende o
JMLT310 (375 MVA de curto-circuito em 69 kV, transformador 69/13,8 kV de
12,5 MVA — ver `tcc2026.configuracao.SUBESTACAO` e
`dss_core.calcular_impedancia_equivalente_subestacao`), aplicada de forma
centralizada a **todas** as seções deste trabalho, não apenas a esta
tabela.

Com a correção, a corrente de curto trifásico no Caso 1 (próximo à
origem, Z1 ≈ 0,39+j1,99 Ω) cai de ≈ 22 kA (fonte ideal) para ≈ 3,9 kA —
valor agora compatível com o de um alimentador real de média tensão —
permanecendo mais elevada que nos Casos 2 e 3 (≈ 0,8 kA) por ser a barra
com a menor impedância de linha acumulada entre a fonte e o ponto de
falta.
