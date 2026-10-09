# Seção 5 — Efeito da resistência de falta (Rf)

Gerado por `tcc2026.resistencia_falta.efeito_rf.executar_efeito_resistencia_falta`.

## `monofasico/` — 10 curtos-circuitos no trecho monofásico (Seção 3)

10 barras MT distribuídas ao longo do trecho monofásico (mesmo trecho da
Seção 3), cada uma com curto monofásico-terra franco/resistivo em 4 valores
de Rf (0,01, 5, 15 e 25 Ω), pelo método da reatância simples (sem
compensação — o trecho é monofásico, não há sequência zero a compensar).

**Resultado**: o erro praticamente não muda com Rf (`efeito_rf_monofasico.png`
— as 4 curvas quase se sobrepõem). Isso é esperado: a fonte equivalente do
alimentador é quase puramente reativa (R≈0 no `New Circuit`), então a
impedância de Thevenin vista pelo relé tem ângulo próximo de 90°, e somar
uma resistência de falta em série praticamente só altera a parte **real**
da impedância aparente — exatamente a razão de o método da reatância
(que usa só a parte imaginária) ser historicamente preferido por ser pouco
sensível a Rf. A barra em ~0,27 km foge do padrão para Rf = 25 Ω (ver
`efeito_rf_monofasico.csv`), provavelmente por ficar próxima de um ponto de
troca de linecode onde a reatância local diverge bastante da X1 média do
trecho usada como referência.

## `trifasico/` — superfície 3D (Rf × diferença angular Z0/Z1 × offset)

Cálculo analítico (não simulado no OpenDSS ponto a ponto — é a própria
fórmula do offset aplicada em uma malha de valores) de como o offset
introduzido na distância estimada pelo método da reatância com compensação
K0 (`Rf·Im(C)/X1`, com `C = 3·Z1/(2·Z1+Z0)`) varia com Rf (0 a 25 Ω) e com a
diferença entre o ângulo de Z0 e o de Z1 (-60° a +60°, módulo de Z0 mantido
no valor de referência da geometria Cemig, só o ângulo é variado). Ver
`efeito_rf_trifasico_3d.png`/`.csv`.

**Resultado**: o offset é exatamente zero quando a diferença angular é
zero (∠Z0 = ∠Z1, confirmando `Im(C) = 0 ⟺ X0/R0 = X1/R1`) e cresce de forma
aproximadamente linear com Rf e com a diferença angular — a superfície tem
o formato de sela esperado pela fórmula.
