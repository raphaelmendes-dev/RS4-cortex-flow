<div align="center">
<img src="assets/Rs4Machine.png" alt="Logo Rs4Machine" width="380" />

# 🧠 RS4-cortex-flow

**Sistema de Aumento Intelectual & Refino Multiagente v1.0.1**

Um pipeline multiagente determinístico, 100% local e de custo zero, que transforma pensamentos humanos brutos em briefings estruturados para tomada de decisão.

[![GitHub](https://img.shields.io/badge/GitHub-Profile-181717?style=for-the-badge&logo=github)](https://github.com/raphaelmendes-dev)
[![License](https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg?style=for-the-badge&logo=python)](https://www.python.org)
[![Ollama](https://img.shields.io/badge/Ollama-Qwen2.5%3A7b-black.svg?style=for-the-badge)](https://ollama.com)
[![Baseline Metrics](https://img.shields.io/badge/📊-Baseline%20Report-informational?style=for-the-badge)](BASELINE.MD)

[🇺🇸 English](README.md) · **🇧🇷 Português do Brasil (este arquivo)**

</div>

---

## 📑 Sumário

- [Visão Geral](#-visão-geral)
- [Princípios-Chave de Engenharia](#-princípios-chave-de-engenharia)
- [Arquitetura Sequencial Multiagente](#-arquitetura-sequencial-multiagente)
- [Estrutura de Diretórios do Projeto](#-estrutura-de-diretórios-do-projeto)
- [Performance Empírica & Baseline](#-performance-empírica--baseline)
- [Executando Localmente](#-executando-localmente)
- [🐳 Executando via Docker](#-executando-via-docker)
- [Módulo de Contexto Global](#-módulo-de-contexto-global)
- [Licença](#-licença)
- [Contato Corporativo & Pesquisa](#-contato-corporativo--pesquisa)

---

## 🎯 Visão Geral

O **RS4-cortex-flow (v1.0.1)** — anteriormente **Projeto Claudio** — é um motor de aumento intelectual offline construído sob o framework experimental do **RS4 Lab** (*Experiment-005*). Projetado para eliminar a fadiga cognitiva e a complexidade prematura, ele ingere "pensamentos brutos" não estruturados e os conduz por uma cadeia de raciocínio de IA local determinística em 4 estágios, alimentada pelo Ollama (`qwen2.5:7b`).

O sistema gera relatórios Markdown padronizados, enriquecidos com metadados de Front-Matter, automaticamente categorizados em frentes operacionais dedicadas (`LAB`, `COMMERCE`, `FREELAS` ou `SISTEMAS`) para uma biblioteca pessoal de conhecimento.

---

## ⚡ Princípios-Chave de Engenharia

- **100% Offline & Custo R$ 0,00:** executa estritamente de forma local via API REST do Ollama (`http://localhost:11434`, ou `host.docker.internal` quando usando a imagem Docker Compose), garantindo privacidade de dados e zero custos de API.
- **Proteção Determinística de Recursos:** chama um agente por vez para evitar saturação de RAM/VRAM em hardware host padrão.
- **Chunking Controlado & Anti-Loop:** contexto limitado a 1.500 caracteres e respostas limitadas a **1.024 tokens máximos** (`num_predict`) com **timeout HTTP de 240s (4 minutos) por requisição** para que cada agente entregue respostas completas, sem cortes, preservando a estabilidade de execução.
- **Injeção Graciosa de Contexto:** integra dinamicamente o `contexto_global.txt` quando presente, ou cai, sem fricção, para o modo isolado.
- **Resiliência de Console Multiplataforma:** reconfiguração padronizada de stdout para UTF-8 em terminais Windows legados (cp1252).

---

## 🏗️ Arquitetura Sequencial Multiagente

[ Entrada do Pensamento Bruto (bruto/) ]
│
▼
[ AGENTE 1: Mapeador Estrutural ] ──> Decompõe o texto bruto em Fatos, Hipóteses & Riscos
│
▼
[ AGENTE 2: Tech Scout ]        ──> Avalia stacks tecnológicas locais 2026 & viabilidade
│
▼
[ AGENTE 3: Crítico Ácido ]     ──> Identifica complexidade prematura & falácias lógicas
│
▼
[ AGENTE 4: Sintetizador ]      ──> Gera o Front-Matter YAML & o "Menor Próximo Passo"
│
▼
[ Base de Conhecimento Estruturada (biblioteca/Refinado_YYYYMMDD_HHMMSS.md) ]


---

## 📂 Estrutura de Diretórios do Projeto

RS4-cortex-flow/
├── bruto/                      → Pasta de entrada para arquivos de pensamento bruto (.txt)
│   ├── teste_frontend.txt      → Exemplo de entrada de UI/UX
│   └── teste_backend.txt       → Exemplo de entrada de Arquitetura
├── agentes/                    → Prompts de sistema dos 4 agentes especializados
│   ├── agente1_mapeador.txt    → Prompt do Mapeador Estrutural
│   ├── agente2_techscout.txt   → Prompt do Tech Scout
│   ├── agente3_critico.txt     → Prompt do Crítico Ácido
│   └── agente4_sintetizador.txt → Prompt do Sintetizador Final
├── biblioteca/                 → Pasta de saída da Base de Conhecimento
│   └── README.md               → Documentação da biblioteca
├── logs/                       → Logs de execução locais (ignorados pelo git)
├── assets/                     → Assets visuais do projeto & provas de benchmark
├── orquestrador_claudio.py     → Script orquestrador principal em Python
├── Dockerfile                  → Imagem leve `python:3.10-slim` do orquestrador
├── docker-compose.yml          → Serviço Docker Compose (volumes + acesso ao Ollama do host)
├── BASELINE.MD                 → Tempos de execução medidos, footprint de RAM & benchmarks de CPU
├── LICENSE                     → Arquivo da Licença MIT
├── .gitignore                  → Regras estritas de segurança & higiene
└── README.md                   → Documentação principal


---

## 📊 Performance Empírica & Baseline

Testado em arquitetura de CPU local rodando Ollama com `qwen2.5:7b`:

| Etapa / Agente | Tempo Médio de Resposta | Footprint de RAM | Limite de Tokens de Saída | Status |
|---|---|---|---|---|
| **Agente 1 — Mapeador Estrutural** | ~37,9s | ~5,2 GB | 1.024 tokens | ✅ Operacional |
| **Agente 2 — Tech Scout** | ~48,9s | ~5,4 GB | 1.024 tokens | ✅ Operacional |
| **Agente 3 — Crítico Ácido** | ~62,0s | ~5,5 GB | 1.024 tokens | ✅ Operacional |
| **Agente 4 — Sintetizador** | ~62,0s | ~5,5 GB | 1.024 tokens | ✅ Operacional |
| **Execução Total do Pipeline** | **~219,7s** | **Máx. 5,5 GB** | **4.096 tokens (4 × 1.024)** | **Determinística & Estável** |

> ⏱️ Os tempos acima correspondem à **linha de base v1.0.0** (medida com o cap de 256 tokens). A partir da **v1.0.1**, cada agente pode gerar até **1.024 tokens** (4.096 no pipeline completo) dentro de um **timeout de 240s por requisição**, garantindo respostas completas sem cortes. Para gráficos detalhados de utilização de recursos de hardware e especificações de ambiente, consulte [BASELINE.MD](./BASELINE.MD).

---

## 🚀 Executando Localmente

### 1. Pré-requisitos
- Python 3.10+ (somente biblioteca padrão — **zero dependências de terceiros via `pip`**)
- [Ollama](https://ollama.com/) instalado e rodando localmente com `qwen2.5:7b`:
  ```bash
  ollama pull qwen2.5:7b
  ```

### 2. Execução
Coloque seu arquivo de texto bruto dentro do diretório `bruto/` e execute:

```bash
# Exemplo usando o arquivo de teste de front-end
python orquestrador_claudio.py teste_frontend.txt
```

O orquestrador executará os 4 agentes sequencialmente e salvará o relatório final em `biblioteca/Refinado_YYYYMMDD_HHMMSS.md`.

## 🐳 Executando via Docker

O repositório inclui uma pilha oficial de Docker Compose (`Dockerfile` + `docker-compose.yml`) que executa o orquestrador **isolado em um container** enquanto acessa a **instância do Ollama rodando na máquina hospedeira** através de `host.docker.internal` (o `extra_hosts` já está configurado no Compose, incluindo hosts Linux). As pastas locais `./bruto`, `./agentes` e `./biblioteca` são montadas como volumes.

### 1. Pré-requisitos
- [Docker](https://www.docker.com/) com Docker Compose v2
- [Ollama](https://ollama.com/) rodando no host com `qwen2.5:7b` baixado:

  ```bash
  ollama pull qwen2.5:7b
  ```

### 2. Execução

```bash
docker compose run --rm claudio-project python orquestrador_claudio.py teste_frontend.txt
```

Coloque seu arquivo `.txt` bruto dentro de `bruto/` e o relatório final é salvo diretamente em `biblioteca/Refinado_YYYYMMDD_HHMMSS.md` na sua máquina (através do volume montado).

## 🌐 Módulo de Contexto Global

Você pode injetar diretrizes globais de laboratório (ex.: restrições de arquitetura-alvo ou regras de orçamento) no Agente 1 criando um arquivo `contexto_global.txt` na raiz do diretório ou dentro de `agentes/`.

- **Se detectado:** injetado automaticamente no prompt do Agente 1 (truncado graciosamente em 500 caracteres).
- **Se ausente:** o sistema registra `ℹ️ Nenhum arquivo 'contexto_global.txt' detectado. Rodando em modo isolado.` e opera normalmente.

## 📄 Licença

Este projeto é software open-source licenciado sob a Licença MIT — consulte o arquivo LICENSE para detalhes.

## 🏢 Contato Corporativo & Pesquisa

Rs4Machine — Laboratório de Pesquisa em IA & Sistemas Autônomos

Fundador / Engenheiro Chefe: Raphael Mendes

📧 python.dev.raphael@gmail.com

🔗 GitHub: github.com/raphaelmendes-dev

🏢 LinkedIn Empresa: Rs4Machine Lab

RS4-cortex-flow v1.0.1 — Setembro de 2026
