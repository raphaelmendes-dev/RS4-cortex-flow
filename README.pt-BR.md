<div align="center">
<img src="assets/Rs4Machine.png" alt="Logo Rs4Machine" width="380" />

# 🧠 RS4-cortex-flow — Rs4Machine

**Pipeline local de aprimoramento intelectual e refinamento multiagente**

Um fluxo determinístico e totalmente local para transformar pensamento bruto em briefings estruturados para tomada de decisão, com controle explícito de contexto, execução e rastreabilidade.

[![GitHub](https://img.shields.io/badge/GitHub-Perfil-181717?style=for-the-badge&logo=github)](https://github.com/raphaelmendes-dev)
[![License](https://img.shields.io/badge/Licença-MIT-green.svg?style=for-the-badge)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg?style=for-the-badge&logo=python)](https://www.python.org)
[![Ollama](https://img.shields.io/badge/Ollama-IA%20Local-black.svg?style=for-the-badge)](https://ollama.com)
[![Baseline Metrics](https://img.shields.io/badge/📊-Relat%C3%B3rio%20Base-informational?style=for-the-badge)](BASELINE.MD)

[🇺🇸 English](README.md) · **🇧🇷 Português do Brasil (este arquivo)**

</div>

---

## 📑 Sumário

- [Visão Geral](#-visão-geral)
- [Princípios de Engenharia](#-princípios-de-engenharia)
- [Arquitetura Sequencial Multiagente](#-arquitetura-sequencial-multiagente)
- [Estrutura de Diretórios](#-estrutura-de-diretórios)
- [Performance Empírica & Baseline](#-performance-empírica--baseline)
- [Executando Localmente](#-executando-localmente)
- [Executando via Docker](#-executando-via-docker)
- [Módulo de Contexto Global](#-módulo-de-contexto-global)
- [Licença](#-licença)
- [Contato](#-contato)

---

## 🎯 Visão Geral

O **RS4-cortex-flow** é um projeto de orquestração multiagente local desenvolvido pela **Rs4Machine** dentro do framework experimental do **RS4 Lab**. Ele transforma entradas humanas brutas em artefatos estruturados usando execução sequencial de agentes com limites explícitos de contexto e tempo.

O sistema é desenhado para reprodutibilidade, controle de custo e supervisão humana. Ele busca reduzir raciocínio ruidoso, limitar janelas de contexto e manter saídas rastreáveis.

**Posicionamento oficial:** Engenheiro de Sistemas de IA focado em arquiteturas híbridas (LLM + lógica determinística) para eliminar alucinações e garantir auditabilidade em produção.

---

## ⚡ Princípios de Engenharia

- **100% Local & Zero Custo** — Executa estritamente em infraestrutura local via API REST do Ollama, sem dependência de nuvem e com proteção de dados sensíveis.
- **Proteção Determinística de Recursos** — Um agente é acionado por vez para evitar saturação de RAM/VRAM em hardware padrão.
- **Chunking Controlado & Anti-Loop** — O contexto é limitado e as saídas são restringidas para evitar geração descontrolada.
- **Injeção Graciosa de Contexto** — `contexto_global.txt` é injetado quando presente; caso contrário, o sistema opera em modo isolado.
- **Resiliência de Console Multiplataforma** — Tratamento padronizado de saída UTF-8 para terminais Windows legados.

---

## 🏗️ Arquitetura Sequencial Multiagente

```text
[ Entrada do Pensamento Bruto (bruto/) ]
│
▼
[ AGENTE 1: Mapeador Estrutural ] → Decompõe o texto bruto em Fatos, Hipóteses e Riscos
│
▼
[ AGENTE 2: Tech Scout ]        → Avalia stacks locais e viabilidade
│
▼
[ AGENTE 3: Crítico Ácido ]     → Identifica complexidade prematura e falácias lógicas
│
▼
[ AGENTE 4: Sintetizador ]      → Gera front matter YAML e o próximo menor passo
│
▼
[ Base de Conhecimento Estruturada (biblioteca/Refinado_YYYYMMDD_HHMMSS.md) ]
```

---

## 📂 Estrutura de Diretórios

```text
RS4-cortex-flow/
├── bruto/                      → Entradas brutas (.txt)
│   ├── teste_frontend.txt
│   └── teste_backend.txt
├── agentes/                    → Prompts dos 4 agentes especializados
│   ├── agente1_mapeador.txt
│   ├── agente2_techscout.txt
│   ├── agente3_critico.txt
│   └── agente4_sintetizador.txt
├── biblioteca/                 → Saída da base de conhecimento
│   └── README.md
├── logs/                       → Logs locais (ignorados pelo git)
├── assets/                     → Visual do projeto e provas de benchmark
├── orquestrador_claudio.py     → Script principal do orquestrador
├── Dockerfile                  → Imagem leve do orquestrador em Python
├── docker-compose.yml          → Stack Docker Compose para Ollama local
├── BASELINE.MD                 → Métricas de runtime, RAM e CPU
├── LICENSE                     → Arquivo de licença MIT
├── .gitignore                  → Regras de segurança e higiene
└── README.md                   → Documentação principal
```

---

## 📊 Performance Empírica & Baseline

Medido em arquitetura local de CPU com Ollama + `qwen2.5:7b`:

| Etapa / Agente | Tempo Médio de Resposta | Footprint de RAM | Limite de Tokens de Saída | Status |
|---|---|---|---|---|
| **Agente 1 — Mapeador Estrutural** | ~37,9s | ~5,2 GB | 1.024 tokens | ✅ Operacional |
| **Agente 2 — Tech Scout** | ~48,9s | ~5,4 GB | 1.024 tokens | ✅ Operacional |
| **Agente 3 — Crítico Ácido** | ~62,0s | ~5,5 GB | 1.024 tokens | ✅ Operacional |
| **Agente 4 — Sintetizador** | ~62,0s | ~5,5 GB | 1.024 tokens | ✅ Operacional |
| **Execução Total do Pipeline** | **~219,7s** | **Máx. 5,5 GB** | **4.096 tokens** | **Determinística & Estável** |

> Esses valores refletem as medições documentadas em `BASELINE.MD`.

---

## 🚀 Executando Localmente

### 1. Pré-requisitos

- Python 3.10+
- [Ollama](https://ollama.com/) instalado e rodando localmente com `qwen2.5:7b`

```bash
ollama pull qwen2.5:7b
```

### 2. Execução

Coloque seu arquivo de texto bruto dentro do diretório `bruto/` e execute:

```bash
python orquestrador_claudio.py teste_frontend.txt
```

O orquestrador executa os 4 agentes sequencialmente e salva o relatório final em `biblioteca/Refinado_YYYYMMDD_HHMMSS.md`.

---

## 🐳 Executando via Docker

O repositório inclui uma stack Docker Compose (`Dockerfile` + `docker-compose.yml`) que executa o orquestrador isolado enquanto acessa a instância do Ollama no host.

### 1. Pré-requisitos

- [Docker](https://www.docker.com/) com Docker Compose v2
- Ollama rodando no host com `qwen2.5:7b` baixado

```bash
ollama pull qwen2.5:7b
```

### 2. Execução

```bash
docker compose run --rm claudio-project python orquestrador_claudio.py teste_frontend.txt
```

Coloque um arquivo `.txt` bruto dentro de `bruto/` e o relatório final é salvo diretamente em `biblioteca/Refinado_YYYYMMDD_HHMMSS.md` na sua máquina via bind-mount.

---

## 🌐 Módulo de Contexto Global

Você pode injetar diretrizes globais de laboratório (por exemplo, restrições de arquitetura ou regras de orçamento) no Agente 1 criando um arquivo `contexto_global.txt` na raiz do diretório ou dentro de `agentes/`.

- **Se detectado:** injetado automaticamente no prompt do Agente 1.
- **Se ausente:** o sistema opera em modo isolado e registra o evento.

---

## 📄 Licença

Este projeto é software open-source licenciado sob a **Licença MIT** — consulte [LICENSE](LICENSE) para detalhes.

---

## 📬 Contato

**Raphael Mendes**  
**AI Systems Engineer & Founder · Rs4Machine**

- 📧 [python.dev.raphael@gmail.com](mailto:python.dev.raphael@gmail.com)
- 🔗 [LinkedIn](https://www.linkedin.com/in/raphaelmendes-dev/)
- 🌐 [Portfolio](https://portfolio-modular-rs4-machine.vercel.app/)

---

*RS4-cortex-flow v1.0.1 — Setembro de 2026*
