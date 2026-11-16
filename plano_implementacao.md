# Plano de Implementação (retroativo)

Este documento reconstrói, a partir do histórico de commits e das sessões
de trabalho com o Claude Code, o que foi implementado, o que foi tentado e
não funcionou, e o que ainda pode ser feito. Serve para retomar o projeto
do zero após um `/clear` de contexto.

---

## 1. Pipeline principal (`main.py` / pacote `tcc2026/`) — IMPLEMENTADO

Construído incrementalmente, seção por seção (ver `git log` para a ordem
exata e `software.md` para o que cada módulo faz):

1. **Seção 1 — Visão geral**: fluxo de potência, curva horária, topologia
   MT, linecodes.
2. **Seção 2 — Tabela de 3 barras**: Thevenin, curto 1F/3F, dados para os
   3 circuitos equivalentes manuais do texto.
3. **Seção 3 — Trecho monofásico**: extração de mini-alimentador, método
   da reatância simples.
4. **Seção 4 — Trecho trifásico**: geometria Cemig aplicada, reatância em
   5 variantes (com/sem carga × com/sem K0 × correção de offset).
5. **Seção 5 — Efeito de Rf**: trecho monofásico (10 barras × valores de
   Rf) e superfície 3D analítica no trecho trifásico.
6. **Seção 6a — Takagi compensado** nas 300 barras MT do alimentador
   completo (ramificação/folha/aleatória/global).
7. **Seção 6b — Reatância compensada e corrigida** (correção EXATA do
   offset, sistema 2×2) nas mesmas 300 barras. **Achado**: supera o
   Takagi nos 4 grupos (MAE 1,4–2,4× menor); uma versão anterior com
   correção aproximada (ajuste de ângulo) tinha viés sistemático de
   ~2,2 km — corrigido substituindo pela solução exata do sistema linear.
8. **Seção 8 — Votação multi-folha (Algoritmo 3)**: consolidação por voto
   entre as 34 folhas candidatas. **Achado**: reduz a ambiguidade de
   ~17 caminhos válidos (critério isolado) para ~2,6 candidatos em média;
   taxa de acerto da barra exata é baixa (13,3% Takagi, 17,7% reatância),
   mas a distância estimada erra tipicamente <1% mesmo quando a barra
   exata não é a vencedora.
9. **Seção 9 — Análise de linecodes**: ranking por quilometragem +
   cruzamento com erro observado, para achar condutores atípicos
   associados a mais erro.
10. **Seção 10 — Análise de sensibilidade**: sensibilidade formal a Rf,
    carregamento e R1 de referência. **Achado**: a reatância corrigida é
    ~50× mais robusta que o Takagi a erro no R1 assumido (S≈-0,006 vs
    S≈0,30) — explicado pela estrutura da fórmula (C e Z1L cancelam-se
    parcialmente na razão da reatância corrigida; no Takagi, Z1L entra
    direto no denominador sem esse cancelamento).
11. **Seção 11 — Comparação direta sob variação de Rf**: Takagi e
    reatância corrigida calculados a partir dos MESMOS fasores simulados,
    nas mesmas 300 barras, variando Rf de 0,01 a 100 Ω. **Achado
    principal do projeto**: em Rf=10 Ω, o Takagi erra ~193× mais que a
    reatância corrigida; a vantagem da reatância cresce (não diminui)
    com Rf, ao contrário do que a dedução teórica do Takagi (cancelamento
    exato de Rf) sugeriria à primeira vista — a explicação proposta é que
    o cancelamento do Takagi depende de ΔI_comp ser um proxy limpo da
    corrente no ponto de falta, premissa que se degrada com carga real
    entre relé e falta à medida que Rf cresce (corrente de falta cai e se
    aproxima da ordem de grandeza da carga).

### Bug corrigido durante o desenvolvimento

- **`LoadMult=0` produz falsa convergência**: o OpenDSS reporta sucesso,
  mas a corrente no elemento `Fault` e na fonte deixam de respeitar
  Kirchhoff (divergem por ordens de grandeza) quando a carga é
  identicamente nula. Corrigido em `dss_core.escalar_carregamento`
  substituindo `fator=0` por `LOADMULT_MINIMO = 1e-4` (0,01% da carga
  nominal, numericamente equivalente a zero para qualquer finalidade do
  trabalho, mas evita esse grau de liberdade patológico).

---

## 2. Frente de Geração Distribuída (GD) — validação separada, PARCIALMENTE INTEGRADA

Trabalho posterior ao pipeline principal, inicialmente como investigação
isolada ("não é para implementar ainda, preciso ter certeza que os
valores são condizentes e reais"), rodando sobre uma **cópia separada** do
alimentador (`JMLT310_reduzido_com_GD`, fora deste repositório Git), para
nunca arriscar o pipeline/resultados já publicados do TCC. Depois,
resultados selecionados foram escritos de volta no texto do TCC (Capítulo
4, Seção 4.11) e no Capítulo 4 (Seção 4.9, figura do multifolhas) — ver
`escopo.md` para o que isso implica.

### 2.1 Achados de modelagem (defeitos no próprio pacote BDGD exportado)

- **Conexão Wye da GD sem referência de neutro local**: 13-18 unidades de
  GD (dependendo do alimentador testado: JMLT310, JMLT306, JMLT309) têm
  `bus1` monofásico sem o nó `.4` explícito e `kv` errado (0,22 fase-fase
  em vez de 0,12 fase-neutro) — corrigido manualmente seguindo o padrão da
  única unidade já correta.
- **Carga duplicada (M1+M2)**: cada consumidor físico é representado por
  DOIS objetos `Load` (`_M1` model=2, `_M2` model=3) com o MESMO kW, ambos
  habilitados por padrão — o parâmetro do exportador (`intAdequarModeloCarga`)
  deveria ESCOLHER um dos dois, não somar. Confirmado empiricamente
  (desabilitar `_M2` reduziu a carga total de 519 kW para 303 kW). Não foi
  corrigido no pipeline principal — não pedido, e mudaria os resultados já
  publicados.
- **"Sobretensão" de até 1,44 pu era majoritariamente artefato de
  medição**: confirmado fisicamente impossível (carga pura, sem GD/
  capacitor, não pode elevar tensão acima de 1,0 pu). Causa raiz:
  ~648 cargas BT monofásicas sem referência de neutro local, retornando
  pelo "terra" do sistema em vez do neutro físico — que é aterrado por um
  reator de 15 Ω (fraco) em TODOS os transformadores. Tensão real
  (fase-neutro local) corrigida fica em ~0,996-1,05 pu. Esse mesmo
  problema reaparece no alimentador base SEM GD nenhuma (mapa de
  curto-circuito, Seção 2.3 abaixo), confirmando que é estrutural do
  próprio alimentador BDGD, não um efeito da GD.

### 2.2 Teste controlado: GD replicada em média tensão (item 3 das pendências)

Para isolar o efeito da GD da carga real e dos defeitos acima, criou-se um
cenário controlado (arquivos **novos**, sem tocar no alimentador original):
`GD_MT_espalhada.dss` + `Master_DU01_GD_MT_espalhada.dss`, 14 unidades
trifásicas corretamente conectadas, em barras MT espalhadas por distância
(1,3 a 8,4 km). Três cenários testados (nenhuma/pouca=70kW/muita=560kW) ao
longo de um perfil diário de 24h: **as 72 combinações convergiram, Vmax
sempre <1,005 pu** — confirma que os problemas de convergência/tensão da
GD real vêm do defeito de conexão, não da penetração em si.

### 2.3 Efeito sobre Takagi e reatância corrigida

Repetindo uma falta numa barra MT com GD, nos 3 níveis de penetração: o
Takagi se mostrou ~5,2× mais sensível à injeção de GD que a reatância
corrigida (consistente, em direção, com o achado da Seção 11 do pipeline
principal sobre sensibilidade a perturbações na corrente medida no relé).

### 2.4 Mapa de curto-circuito (item 6 das pendências)

Falta simulada nas 300 barras MT do alimentador **oficial sem GD**,
medindo afundamento/sobretensão nas 437 barras observáveis, somado por
barra. Revelou 4 barras MT com sensibilidade de sequência-zero atípica
(afetadas por 100% das 300 faltas, independente da distância) e um grupo
de barras significativamente mais expostas que a média — candidatas a
estudo de QEE/ajuste de proteção caso o alimentador real seja
instrumentado.

### 2.5 Figura "multi-folha" (item 2 das pendências)

Mapa geográfico (coordenadas `buscoords.csv`) com a topologia MT, a
subestação, a falta real e os candidatos equidistantes (folhas cuja
avaliação do Algoritmo 1 produz a mesma distância estimada, mapeada para
barras diferentes via votação). Usa um caso onde a votação **acerta** a
barra exata (NODE#442497697, 5/10 votos) — a primeira versão usava um caso
de erro, substituída a pedido por ser menos didática como primeira
ilustração do mecanismo (a taxa real de acerto/erro já está documentada
na Tabela de votação do Capítulo 4).

---

## 3. O que foi tentado e NÃO funcionou (becos sem saída documentados)

Documentado em detalhe para não serem re-tentados sem necessidade:

- **`dss.pvsystems.enabled = False` (setter da API COM do `py_dss_interface`)
  não propaga para o motor do OpenDSS** — a leitura de volta da mesma
  propriedade engana (parece ter funcionado), mas uma query de texto
  (`? PVSystem.X.enabled`) revela que o estado real não mudou. **Correção**:
  usar sempre o comando de texto `disable PVSystem.X` / `enable PVSystem.X`,
  ou, quando possível, `irradiance=0.0` (confirmado confiável) em vez de
  desabilitar.
- **Nomes de objeto com ponto** (ex. `gd.mg.001.445.801`, convenção de
  nomenclatura de GD do BDGD) **quebram comandos de texto no formato
  `Classe.Nome.Propriedade=Valor`** — o parser do OpenDSS confunde os
  pontos do nome com separadores, e em alguns casos isso disparava uma
  caixa de diálogo de erro NATIVA e bloqueante (travou o processo até ser
  morto manualmente). Formas seguras confirmadas: `Edit Classe.Nome
  propriedade=valor` (com espaço), ou selecionar via API
  (`dss.pvsystems.name = n`) e então `dss.pvsystems.propriedade = valor`.
- **Trocar de modo `daily` para `snap` no meio de uma sessão OpenDSS
  quebra a convergência** mesmo sem tocar na GD — o salto abrupto de carga
  (de valor reduzido pelo shape horário, em `daily`, para nameplate cheio,
  em `snap`) é, por si só, um "choque" para o Newton. Lição: escolher UM
  modo e manter, ou reconstruir o estado do zero ao trocar.
- **Modo `daily` zera a potência de toda `PVSystem` independente do valor
  manual de `irradiance=`** quando usado via `dss_core.definir_modo_instantaneo`
  (criado antes de o projeto ter GD, nunca testado com `PVSystem`).
  Correção: forçar `set mode=snap` depois de `definir_modo_instantaneo`
  sempre que houver GD no circuito.
- **Rampa de irradiância em múltiplos sub-passos, dentro do mesmo processo,
  piorou a convergência em vez de ajudar** num teste específico (GD
  espalhada em MT) — provavelmente convergência para uma solução não-física
  diferente a cada sub-passo. A técnica de continuação/rampa funcionou bem
  em outros contextos deste mesmo projeto (documentada como boa prática
  geral), então isso não invalida a técnica, só mostra que não é garantia
  universal — testar com e sem rampa antes de assumir qual ajuda.
- **Adicionar impedância de linha real (linecode) entre a carga/GD e o
  secundário do transformador, na rede reduzida, NÃO melhora a
  convergência** — testado explicitamente, piorou (um ponto que antes
  convergia passou a falhar). Hipótese: a carga ainda retorna pelo "terra"
  (defeito de neutro não corrigido nesse teste), e a queda de tensão extra
  pela linha soma ao deslocamento de neutro já existente.
- **Calibrar a distância pelo linecode real de cada segmento, numa
  população grande de barras**, via `metodo_reatancia.x1_medio_ponderado_trecho`,
  **causou uma falha de acesso à memória (`OSError: access violation`)** na
  leitura de `linecodes.x1` via COM — a função foi desenhada para um
  recorte pequeno (um trecho extraído), não para iterar sobre centenas de
  segmentos do alimentador completo de uma vez. Contornado usando a
  referência de geometria uniforme (`z1_ref.imag`) para todos os métodos
  em vez de tentar ler por segmento.
- **Nomes de barra do grafo (`NetworkX`, via `grafo_alimentador`) usam
  `NODE#` maiúsculo; `dss.circuit.nodes_names` devolve `node#` minúsculo**
  — comparação direta sem `.lower()` em ambos os lados falha silenciosamente
  (não dá erro, só não bate nenhuma barra, ou só bate por coincidência as
  que não têm letras no nome, como `"100#..."`). Já causou dois bugs
  distintos nesta investigação (uma vez no mapa de calor de curto-circuito,
  outra vez ao tentar reler tensão por barra) — sempre normalizar para
  minúsculas nas duas pontas antes de comparar/indexar.
- **A barra de origem do circuito (`SEGM#194789369`) não tem coordenada em
  `buscoords.csv`** — ao plotar mapas geográficos, ela precisa de um
  fallback (usado: o vizinho imediato via chave MT, `100#207301442`).

---

## 4. O que ainda pode ser feito (trabalho futuro)

- **Decidir se a frente de GD é formalizada** como seção do pipeline
  principal (novo subpacote `tcc2026/geracao_distribuida/` + seção no
  `main.py`) ou permanece como validação à parte (ver nota em
  `software.md`).
- **Corrigir a duplicação de carga M1+M2** no alimentador oficial, se o
  autor decidir que isso deveria afetar os resultados já publicados do
  pipeline principal (hoje os resultados de Takagi/reatância das Seções 6
  em diante rodam com a carga duplicada, sem ter sido pedido para corrigir).
- **Expandir a prosa da Seção 4.11 do TCC** (resultados de GD) — está mais
  enxuta que o resto do capítulo; se o autor quiser uma discussão mais
  completa (motivação, limitações, comparação com literatura de GD em
  localização de falta), ainda não foi feita em profundidade.
- **Rodar a bateria de Rf (Seção 11 do pipeline, 0,01 a 100 Ω) também com
  GD habilitada**, para fechar com dados a combinação dos dois efeitos
  (hoje cada um foi testado isoladamente).
- **Testar a redução topológica (BT→secundário do trafo) em JMLT306 e
  JMLT309** (só JMLT310 foi de fato reduzido e testado; para os outros
  dois, só havia uma previsão estrutural de que a fragilidade de
  convergência seria igual ou pior, nunca confirmada empiricamente).
- **Investigar mais a fundo as 4 barras de sequência-zero atípica** do
  mapa de curto-circuito (Seção 2.4) — hoje só documentado que existem e
  são insensíveis à distância da falta, sem uma causa raiz definitiva
  (diferente do defeito de neutro da GD, que tem causa raiz confirmada).
