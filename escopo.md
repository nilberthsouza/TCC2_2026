# Escopo do Projeto — TCC2_2026

## Objetivo

Comparar dois métodos de localização de faltas em redes de distribuição —
**reatância aparente** (com variantes: sem compensação, com compensação de
sequência zero K0, com correção exata do offset de Rf) e **Takagi**
(adaptado para ler tensão direto no relé, com compensação K0) — aplicados
a um alimentador de distribuição **real**, não a um sistema de teste
acadêmico padrão (IEEE 13/34/123 barras).

O alimentador usado é o **JMLT310** (Conceição do Mato Dentro/João
Monlevade — MG), extraído no formato de exportação **BDGD/ANEEL** (o mesmo
usado pela Cemig), na sua **versão reduzida** (rede secundária eliminada,
cargas BT concentradas no secundário de cada transformador — 439 barras).
A simulação do fluxo de potência e das faltas é feita no **OpenDSS**,
controlado via Python pelo pacote `py_dss_interface`.

## Perguntas que o trabalho responde

1. Qual método localiza faltas com menor erro, no alimentador real, em
   diferentes condições: carregamento, resistência de falta (Rf),
   diferentes trechos (monofásico, trifásico), toda a população de 300
   barras MT?
2. O ganho teórico do Takagi (cancelamento exato de Rf via `ΔI_comp`) se
   mantém num alimentador real e carregado, ou se degrada por premissas
   que só valem em sistemas idealizados (sem carga entre relé e falta)?
3. Quando o relé não sabe a priori em qual ramo a falta ocorreu (situação
   real), qual método discrimina melhor o ramo correto entre vários
   candidatos plausíveis ("problema das múltiplas estimativas"), usando
   consolidação por votação multi-folha?
4. O quanto a ausência de dados reais de geometria de linha (`LineGeometry`)
   no pacote BDGD, suprida por uma geometria de referência assumida, afeta
   os resultados? Os condutores reais mais atípicos (frente a essa
   referência) são também os que mais geram erro?
5. **(Frente complementar, iniciada em paralelo)** Como a presença de
   geração distribuída (GD) fotovoltaica — já instalada nesse alimentador
   segundo a própria BDGD — afeta a convergência do fluxo de potência, o
   perfil de tensão, e a precisão dos dois métodos de localização de falta?

## O que está dentro do escopo

- Simulação de fluxo de potência e curto-circuito monofásico-terra/trifásico
  no JMLT310 reduzido, via OpenDSS.
- Implementação e validação numérica das fórmulas de reatância aparente e
  Takagi (dedução matemática no texto do TCC, Apêndices; implementação em
  `tcc2026/reatancia/` e `tcc2026/takagi/`).
- Varredura de faltas em até 300 barras MT, com e sem variação de Rf e de
  carregamento.
- Geometria de referência (espaçador losangular Cemig) para suprir a
  ausência de `LineGeometry`/`WireData` reais no pacote de dados.
- Análise de sensibilidade formal (Rf, carregamento, R1 de referência) dos
  dois métodos.
- Consolidação por votação multi-folha (Algoritmo 3) como resposta ao
  problema de discriminação de ramo em campo.
- Frente complementar de GD: validação de penetração, convergência e efeito
  sobre os dois métodos (ver `plano_implementacao.md` para o detalhamento —
  essa frente roda sobre uma cópia separada do alimentador, fora deste
  repositório, e ainda não está integrada ao pipeline principal `main.py`).

## O que está fora do escopo

- Qualquer sistema de teste acadêmico padrão (IEEE 13/34/123 barras) como
  objeto principal de estudo — usados apenas como referência de literatura.
- Modelagem de proteção real (relés comerciais, curvas de atuação,
  coordenação) — o "relé" aqui é só o ponto de medição na origem do
  alimentador.
- Geometria de linha real medida em campo — assumida por referência
  (losango Cemig), documentado como limitação explícita.
- Integração definitiva da frente de GD ao pipeline principal — está
  validada separadamente, decisão de incorporar ou não ainda em aberto.
- Qualquer alteração de hardware/software de proteção ou automação do
  alimentador real — é um estudo de simulação, não um projeto de campo.

## Alimentador e dados

- **Fonte dos dados**: exportação BDGD/ANEEL (padrão nacional) do
  alimentador JMLT310, convertida para arquivos `.dss` do OpenDSS.
- **Pasta de dados**: fora deste repositório Git (`JMLT310_reduzido/`,
  caminho configurável via `TCC2026_PASTA_ALIMENTADOR` — ver
  `tcc2026/configuracao.py`).
- **Limitação de dados conhecida**: o pacote não inclui `LineGeometry` nem
  `WireData` — ver nota detalhada no `README.md` e em
  `tcc2026/nucleo/geometria_eletrica.py`.
- **Dados reais da subestação** (impedância de Thevenin a montante):
  EPE-DEE-NT-094/2017 — ver `SUBESTACAO` em `tcc2026/configuracao.py`.
