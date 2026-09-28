<div align="center">
<img src="assets/Rs4Machine.png" alt="Rs4Machine Logo" width="380" />

# 🧠 RS4-cortex-flow — Rs4Machine

**Local multi-agent orchestration pipeline for structured knowledge refinement**

A deterministic, fully local workflow for transforming raw human thought into structured decision briefs and organized knowledge outputs, with strict control over context, runtime, and auditability.

[![GitHub](https://img.shields.io/badge/GitHub-Profile-181717?style=for-the-badge&logo=github)](https://github.com/raphaelmendes-dev)
[![License](https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg?style=for-the-badge&logo=python)](https://www.python.org)
[![Ollama](https://img.shields.io/badge/Ollama-Local%20LLM-black.svg?style=for-the-badge)](https://ollama.com)
[![Baseline Metrics](https://img.shields.io/badge/📊-Baseline%20Report-informational?style=for-the-badge)](BASELINE.MD)

**🇺🇸 English (this file)** · [🇧🇷 Português do Brasil](README.pt-BR.md)

</div>

---

## 📑 Table of Contents

- [Overview](#-overview)
- [Key Engineering Principles](#-key-engineering-principles)
- [Multi-Agent Sequential Architecture](#-multi-agent-sequential-architecture)
- [Project Directory Structure](#-project-directory-structure)
- [Empirical Performance & Baseline](#-empirical-performance--baseline)
- [Running Locally](#-running-locally)
- [Running via Docker](#-running-via-docker)
- [Global Context Module](#-global-context-module)
- [License](#-license)
- [Contact](#-contact)

---

## 🎯 Overview

**RS4-cortex-flow** is a local multi-agent orchestration project developed by **Rs4Machine** under the **RS4 Lab** experimental framework. It converts raw human input into structured operational artifacts using controlled, sequential agent execution and explicit runtime guardrails.

The system is designed around repeatability, budget control, and human oversight. It is built to reduce noisy reasoning, constrain context windows, and keep outputs traceable.

**Official positioning:** AI Systems Engineer focused on hybrid architectures (LLM + deterministic logic) to eliminate hallucinations and ensure auditability in production.

---

## ⚡ Key Engineering Principles

- **100% Local & Zero Cost** — Runs strictly on local infrastructure via the Ollama REST API, avoiding cloud dependency and protecting sensitive input.
- **Deterministic Resource Protection** — One agent is invoked at a time to prevent RAM/VRAM saturation on standard host hardware.
- **Controlled Chunking & Anti-Looping** — Context is capped and outputs are constrained to prevent runaway generation.
- **Graceful Context Injection** — `contexto_global.txt` is injected when present, otherwise the system operates in isolated mode.
- **Cross-Platform Console Resilience** — Standardized UTF-8 output handling for legacy Windows terminals.

---

## 🏗️ Multi-Agent Sequential Architecture

```text
[ Raw Thought Input (bruto/) ]
│
▼
[ AGENT 1: Structural Mapper ] → Deconstructs raw text into Facts, Hypotheses & Risks
│
▼
[ AGENT 2: Tech Scout ]      → Evaluates local tech stacks and feasibility
│
▼
[ AGENT 3: Acid Critic ]     → Identifies premature complexity and logical fallacies
│
▼
[ AGENT 4: Synthesizer ]      → Generates YAML front matter and a small next step
│
▼
[ Structured Knowledge Base (biblioteca/Refinado_YYYYMMDD_HHMMSS.md) ]
```

---

## 📂 Project Directory Structure

```text
RS4-cortex-flow/
├── bruto/                      → Raw thought inputs (.txt)
│   ├── teste_frontend.txt
│   └── teste_backend.txt
├── agentes/                    → System prompts for the 4 specialized agents
│   ├── agente1_mapeador.txt
│   ├── agente2_techscout.txt
│   ├── agente3_critico.txt
│   └── agente4_sintetizador.txt
├── biblioteca/                 → Output knowledge base
│   └── README.md
├── logs/                       → Local execution logs (git-ignored)
├── assets/                     → Project visuals and benchmark proofs
├── orquestrador_claudio.py     → Core orchestrator script
├── Dockerfile                  → Lightweight Python orchestrator image
├── docker-compose.yml          → Docker Compose stack for host Ollama access
├── BASELINE.MD                 → Runtime, RAM, and CPU baseline metrics
├── LICENSE                     → MIT license
├── .gitignore                  → Security and hygiene rules
└── README.md                   → Main documentation
```

---

## 📊 Empirical Performance & Baseline

Measured on a local CPU architecture with Ollama + `qwen2.5:7b`:

| Stage / Agent | Avg Response Time | RAM Footprint | Output Token Cap | Status |
|---|---|---|---|---|
| **Agent 1 — Structural Mapper** | ~37.9s | ~5.2 GB | 1,024 tokens | ✅ Operational |
| **Agent 2 — Tech Scout** | ~48.9s | ~5.4 GB | 1,024 tokens | ✅ Operational |
| **Agent 3 — Acid Critic** | ~62.0s | ~5.5 GB | 1,024 tokens | ✅ Operational |
| **Agent 4 — Synthesizer** | ~62.0s | ~5.5 GB | 1,024 tokens | ✅ Operational |
| **Total Pipeline Run** | **~219.7s** | **Max 5.5 GB** | **4,096 tokens** | **Deterministic & Stable** |

> These values reflect the baseline measurements documented in `BASELINE.MD`.

---

## 🚀 Running Locally

### 1. Prerequisites

- Python 3.10+
- [Ollama](https://ollama.com/) installed and running locally with `qwen2.5:7b`

```bash
ollama pull qwen2.5:7b
```

### 2. Execution

Place your raw text file inside the `bruto/` directory and run:

```bash
python orquestrador_claudio.py teste_frontend.txt
```

The orchestrator runs the 4 agents sequentially and saves the final report in `biblioteca/Refinado_YYYYMMDD_HHMMSS.md`.

---

## 🐳 Running via Docker

The repository includes a Docker Compose stack (`Dockerfile` + `docker-compose.yml`) that runs the orchestrator in isolation while reaching the Ollama instance on the host.

### 1. Prerequisites

- [Docker](https://www.docker.com/) with Docker Compose v2
- Ollama running on the host with `qwen2.5:7b` downloaded

```bash
ollama pull qwen2.5:7b
```

### 2. Execution

```bash
docker compose run --rm claudio-project python orquestrador_claudio.py teste_frontend.txt
```

Place a raw `.txt` file inside `bruto/` and the final report is saved directly to `biblioteca/Refinado_YYYYMMDD_HHMMSS.md` on your machine via bind-mount.

---

## 🌐 Global Context Module

You can inject global laboratory guidance (for example, architecture constraints or budget rules) into Agent 1 by creating a `contexto_global.txt` file in the root directory or inside `agentes/`.

- **If detected:** Automatically injected into Agent 1 prompt.
- **If absent:** The system runs in isolated mode and logs the event.

---

## 📄 License

This project is open-source software licensed under the **MIT License** — see [LICENSE](LICENSE) for details.

---

## 📬 Contact

**Raphael Mendes**  
**AI Systems Engineer & Founder · Rs4Machine**

- 📧 [python.dev.raphael@gmail.com](mailto:python.dev.raphael@gmail.com)
- 🔗 [LinkedIn](https://www.linkedin.com/in/raphaelmendes-dev/)
- 🌐 [Portfolio](https://portfolio-modular-rs4-machine.vercel.app/)

---

*RS4-cortex-flow v1.0.1 — September 2026*
