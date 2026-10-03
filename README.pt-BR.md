<div align="center">

[🇺🇸 English](README.md) · **🇧🇷 Português do Brasil (este arquivo)**

<img src="assets/Rs4Machine.png" alt="Logo Rs4Machine" width="380" />

# RS4-cortex-flow

**Motor Local de Orquestração Multiagente · Cortex-Flow V2 · v2.0.0**

Um pipeline LangGraph determinístico que transforma entrada humana bruta em entregáveis pontuados e auditáveis.
Inferência e armazenamento vetorial ficam na sua máquina — **R$ 0,00 por execução**.

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org)
[![LangGraph](https://img.shields.io/badge/LangGraph-V2-1C3C3C?style=for-the-badge)](https://github.com/langchain-ai/langgraph)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-RAG-FF6B4A?style=for-the-badge)](https://www.trychroma.com)
[![Ollama](https://img.shields.io/badge/Ollama-R%24%200.00-000000?style=for-the-badge&logo=ollama&logoColor=white)](https://ollama.com)
[![License](https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge)](LICENSE)

**Autor:** Raphael Mendes · Rs4Machine Lab — 📧 [python.dev.raphael@gmail.com](mailto:python.dev.raphael@gmail.com)

</div>

---

## 📑 Sumário

- [1. Que problema este sistema resolve?](#1-que-problema-este-sistema-resolve)
- [2. Como resolve?](#2-como-resolve)
- [3. Quais são os limites e o desempenho?](#3-quais-são-os-limites-e-o-desempenho)
- [4. Quem governa a decisão?](#4-quem-governa-a-decisão)
- [📈 Benchmarks Reais (Suíte E2E)](#-benchmarks-reais-suíte-e2e)
- [🧪 Rodando o Teste End-to-End](#-rodando-o-teste-end-to-end)
- [🚀 Primeiros Passos](#-primeiros-passos)
- [📁 Estrutura do Projeto](#-estrutura-do-projeto)
- [📄 Licença](#-licença)
- [🏢 Contato](#-contato)

---

## 1. Que problema este sistema resolve?

Transformar ideias brutas em decisões estruturadas normalmente exige horas de análise manual — ou o envio de material privado a APIs de LLM na nuvem, com cobrança por token.

O RS4-cortex-flow ataca a lacuna de orquestração: encadeia agentes especializados localmente para produzir **artefatos padronizados e auditáveis** (Markdown com front-matter YAML, templates de código, registros de avaliação), mantendo:

- **Custo de R$ 0,00** — sem taxas de API; a inferência roda na máquina local via Ollama.
- **Dados locais** — prompts, contexto e a base vetorial não saem do host durante inferência e armazenamento (ver fronteira de egress na [seção 3](#3-quais-são-os-limites-e-o-desempenho)).
- **Decisões auditáveis** — cada nó grava telemetria em `Metrics/` e toda execução termina com um registro escrito de decisão humana.

## 2. Como resolve?

Um **`StateGraph` do LangGraph** move um **`CortexState`** tipado (`TypedDict`, 17 campos) por nós especializados, com dois **roteadores determinísticos, sem LLM** (baseados em regras) que selecionam a rota de produção:

| Rota | Sequência de nós | Saída |
|---|---|---|
| **A — `COPY_OFFER`** | `triagem → redator → critico → evaluator` | Copy comercial / anúncio em `drafts/ofertas/` |
| **B — `BUILDER_TEMPLATE`** | `triagem → mapeador → techscout → critico → sintetizador → builder → evaluator` | Síntese refinada + template MVP em `drafts/templates/` |

![Grafo do Cortex-Flow V2](assets/cortex_flow_v2_graph.png)

Camadas de suporte:

- **Estado tipado:** `cortex_flow_v2/graph/state.py` define o `CortexState`; o wrapper em `cortex_flow_v2/graph/__init__.py` compila o grafo e exporta o diagrama acima.
- **RAG (ChromaDB):** base vetorial local persistente (`./chroma_db_data`, coleção `decisoes`) com embeddings `nomic-embed-text` via Ollama local, semeados de forma idempotente a partir de `filosofia_rs4.txt` (`python cortex_flow_v2/vectorstore/seed_dna.py`). Crítico, Sintetizador, Builder e Evaluator consultam a base antes de montar os prompts.
- **Inferência local (Ollama):** chamadas REST a `localhost:11434` usando `qwen2.5:7b` (padrão), `qwen2.5-coder:7b` (Builder) e `qwen2.5:3b` (fallback), com `temperature=0.2`, `num_predict=1024` e timeout HTTP de **240 s** por requisição.
- **Conector Commerce:** `cortex_flow_v2/inbox/conector_commerce.py` carrega as oportunidades `PENDENTE` de `cortex_flow_v2/inbox/payload_commerce.json` para o estado inicial.

## 3. Quais são os limites e o desempenho?

- **Sequencial FIFO em CPU:** os nós executam estritamente um de cada vez — sem execução paralela. É uma escolha deliberada para manter RAM/VRAM limitados em hardware de consumo.
- **Pausa de hardware:** `time.sleep(2.0)` em cada transição de nó (`PAUSA_HARDWARE_S = 2.0`, Item 09) — 8,0 s no total na Rota A e 14,0 s na Rota B.
- **Limites do modelo:** modelos locais da classe 7B; máximo de **1.024 tokens** por resposta (`num_predict`); contexto de prompt limitado a **1.500 caracteres**; timeout de **240 s** por requisição. Os nós degradam graciosamente (modelo menor ou regra embutida) em vez de travar.
- **Tempo de parede:** **481,56 s** na Rota A e **2.031,86 s** na Rota B na máquina de referência (Windows 11 + Ollama local) — cerca de **41,9 minutos** para a suíte E2E completa, pausas de hardware incluídas.
- **Gate de disponibilidade:** a suíte E2E nunca fabrica resultados — com o Ollama offline ela aborta com `FALHA_OLLAMA_OFFLINE`.
- **Egress de rede:** inferência e armazenamento vetorial são estritamente locais. A única saída opcional é a busca DuckDuckGo do Tech Scout, acionada apenas quando o RAG retorna hits insuficientes; falha de forma suave offline e é reportada na telemetria.
- **Fronteira de determinismo:** triagem e roteamento são regras puras (sub-milissegundo, zero chamadas de LLM). O texto gerado pelo LLM é estocástico dentro dos limites acima.

## 4. Quem governa a decisão?

**Nível 1 de Automação — HITL (Human in the Loop): o sistema propõe, o humano decide.**

1. O **Evaluator** avalia cada entregável e emite uma nota preliminar (`NOTA_PRELIMINAR`, 1 a 5) mais uma recomendação:

   | Nota | Recomendação |
   |---|---|
   | **Nota ≥ 4** | `APROVAR` |
   | Nota = 3 | `REVISAR` |
   | Nota ≤ 2 | `REJEITAR` |

2. A avaliação é persistida em `drafts/avaliacoes/avaliacao_*.md` com status `AGUARDANDO_DECISAO_HUMANA`.
3. **A autoridade final é o CEO / Raphael Mendes (Rs4Machine Lab).** A nota é apenas consultiva: nada é aprovado ou publicado de forma autônoma, e o filtro de aprovação é **Nota ≥ 4 + confirmação humana explícita**.

## 📈 Benchmarks Reais (Suíte E2E)

Medidos por `Metrics/metrics_integracao_v2.json` na execução E2E completa da carga do Commerce (2026-10-03):

| Execução | Rota | Tempo total | Nota | Decisão | Artefatos principais |
|---|---|---:|---|---|---|
| **A** | `COPY_OFFER` | **481,56 s** | **3 / 5** | **REVISAR** | Rascunhos em `drafts/ofertas/` |
| **B** | `BUILDER_TEMPLATE` | **2.031,86 s** | **4 / 5** | **APROVAR** | MVP em `drafts/templates/` |
| 0 | Triagem (Agente 0) — classificador determinístico, sem LLM | **0,17 ms** | — | — | `frente_alvo` no `CortexState` |

Notas: tempo acumulado das duas rotas = **2.513,42 s** (pausas de hardware incluídas); toda execução grava também um registro HITL em `drafts/avaliacoes/`.

## 🧪 Rodando o Teste End-to-End

```bash
python cortex_flow_v2/tests/test_esteira_completa.py        # ambas as rotas (padrão)
python cortex_flow_v2/tests/test_esteira_completa.py A      # apenas a Rota A
python cortex_flow_v2/tests/test_esteira_completa.py B      # apenas a Rota B
```

Pré-requisitos: Ollama online com os modelos listados abaixo e ao menos uma oportunidade `PENDENTE` em `cortex_flow_v2/inbox/payload_commerce.json`.

A suíte valida: integridade via `py_compile`; travas do orquestrador (`num_predict=1024`, `timeout=240s`); carga do payload do Commerce; saúde do Ollama; execução real de cada rota via `app.invoke(...)`; sequência de nós pelos `Metrics/*.json` individuais; entregáveis (copy / síntese / código / avaliação / nota 1–5); e o relatório consolidado em `Metrics/metrics_integracao_v2.json`.

## 🚀 Primeiros Passos

### 1. Pré-requisitos

- Python **3.11+** (validado na 3.14)
- [Ollama](https://ollama.com/) rodando localmente com:

  ```bash
  ollama pull qwen2.5:7b
  ollama pull qwen2.5-coder:7b
  ollama pull qwen2.5:3b        # fallback
  ollama pull nomic-embed-text  # embeddings do RAG
  ```

- Dependências Python para a V2 (o orquestrador legado usa apenas a stdlib):

  ```bash
  pip install langgraph chromadb ollama
  pip install duckduckgo-search   # opcional: fallback web do Tech Scout
  ```

### 2. Semear a base vetorial (RAG)

```bash
python cortex_flow_v2/vectorstore/seed_dna.py
```

### 3. Rodar o pipeline

```bash
# Suíte E2E completa (ambas as rotas)
python cortex_flow_v2/tests/test_esteira_completa.py

# Regenerar o diagrama do grafo
python -m cortex_flow_v2.graph
```

### 4. Orquestrador legado (v1, somente biblioteca padrão)

```bash
python orquestrador_claudio.py teste_frontend.txt
```

### 5. Docker (orquestrador legado)

```bash
docker compose run --rm claudio-project python orquestrador_claudio.py teste_frontend.txt
```

A pilha Compose isola o orquestrador em um container enquanto alcança o Ollama do host via `host.docker.internal`; `./bruto`, `./agentes`, `./biblioteca` e `./Metrics` são montados como volumes.

**Telemetria:** cada nó grava `Metrics/metrics_*_v2.json` (dimensões sistema / modelo / agente — Regra CEO RS4) com latência, consumo de tokens e status de saída.

## 📁 Estrutura do Projeto

```
RS4-cortex-flow/
├── cortex_flow_v2/
│   ├── graph/          # StateGraph, CortexState, roteadores, pausas de hardware
│   ├── nodes/          # triagem, redator, mapeador, techscout, critico, ...
│   ├── inbox/          # conector Commerce + payload_commerce.json
│   ├── vectorstore/    # cliente ChromaDB + seed_dna (RAG)
│   └── tests/          # testes unitários + suíte E2E
├── agentes/            # arquivos de prompt dos agentes (pt-BR)
├── assets/             # Rs4Machine.png + cortex_flow_v2_graph.png
├── bruto/              # entradas brutas (apenas amostras versionadas)
├── drafts/             # saídas: ofertas/, templates/, refinados/, avaliacoes/ (git-ignored)
├── Metrics/            # telemetria por nó (git-ignored)
├── chroma_db_data/     # base vetorial local (git-ignored)
├── orquestrador_claudio.py   # orquestrador legado v1 (somente stdlib)
├── docker-compose.yml / Dockerfile
└── README.md           # versão em inglês
```

## 📄 Licença

Este projeto é software de código aberto licenciado sob a Licença MIT — consulte o arquivo [LICENSE](LICENSE) para detalhes.

## 🏢 Contato

**Rs4Machine — Laboratório de Pesquisa em IA & Sistemas Autônomos**

- **Autor:** Raphael Mendes / Rs4Machine Lab
- 📧 **E-mail técnico:** [python.dev.raphael@gmail.com](mailto:python.dev.raphael@gmail.com)
- 🔗 GitHub: [github.com/raphaelmendes-dev](https://github.com/raphaelmendes-dev)

RS4-cortex-flow v2.0.0 — Outubro de 2026





