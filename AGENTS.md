# AGENTS.md — TCC2_2026

## Descrição do projeto

Código em Python do TCC2 (2026) de Nilberth: estudo comparativo de dois
métodos de localização de faltas em distribuição — **reatância aparente**
(sem compensação / com compensação K0 / com correção exata do offset de
Rf) e **Takagi compensado** — aplicados ao alimentador real **JMLT310**
(padrão de exportação BDGD/ANEEL, Cemig), simulado no **OpenDSS** via
`py_dss_interface`. Ver `escopo.md` para o escopo completo e
`software.md` para o catálogo de todo o código.

## Modelo e subagentes — OBRIGATÓRIO

- **Use sempre o modelo Sonnet** para trabalhar neste projeto (análise
  numérica, debugging de OpenDSS, redação de LaTeX/documentação, decisões
  de modelagem). Não faça downgrade de modelo para este projeto.
- **Para tarefas menos complexas e bem delimitadas** (buscar um trecho em
  um arquivo, listar algo, conferir um valor já calculado, tarefas
  mecânicas de poucos passos), pode delegar a **subagentes Haiku**.

## Documentação deste repositório — leia nesta ordem

1. **`escopo.md`** — o que o projeto é, o que está dentro/fora do escopo.
2. **`software.md`** — todo arquivo `.py`, o que faz, bibliotecas usadas.
3. **`plano_implementacao.md`** — histórico retroativo: o que foi
   implementado, o que foi tentado e não funcionou (com a causa raiz, para
   não repetir o mesmo erro), o que ainda pode ser feito.
4. **`README.md`** — como configurar e rodar o pipeline (`main.py`),
   pré-requisitos (Python 3.11 + venv local, OpenDSS instalado, pacote de
   dados do alimentador fora do repositório).

**Sempre que o repositório for limpo (`/clear` de contexto), releia estes
4 documentos antes de continuar qualquer trabalho** — eles existem
justamente para que o trabalho continue de onde parou sem precisar
reconstruir o contexto a partir do zero.

## Última tarefa concluída

(Atualizar esta seção ao final de cada sessão de trabalho relevante.)

**2026-11-15** — Criação desta documentação (`AGENTS.md`, `software.md`,
`plano_implementacao.md`, `escopo.md`, `CLAUDE.md`), reconstruindo
retroativamente todo o histórico de implementação do pipeline principal
(Seções 1-11) e da frente complementar de geração distribuída (GD), que já
havia sido parcialmente escrita de volta no texto do TCC (Capítulo 4,
Seções 4.9 e 4.11) numa sessão anterior.

## Convenções do projeto (resumo — detalhes em `software.md`)

- Módulos e funções nomeados em português (snake_case), com docstrings
  `'''Entradas/Saída'''` descrevendo tipos e unidades.
- Cada seção do trabalho é independente, orquestrada por `main.py`, e
  grava em `resultados/<NN>_<secao>/` (CSV + PNG + tabela LaTeX).
- O motor OpenDSS (COM) é singleton por processo — cuidado ao compilar
  mais de um circuito na mesma sessão Python (ver nota em `README.md`
  sobre `calcular_parametros_sequencia_losangular_cemig`).
- A pasta de dados do alimentador fica **fora** deste repositório Git
  (caminho configurável via variável de ambiente `TCC2026_PASTA_ALIMENTADOR`).
