<div align="center">
<img src="assets/Rs4Machine.png" alt="Rs4Machine Logo" width="380" />

# 🧠 Claudio Project — Rs4Machine

**Intellectual Augmentation & Multi-Agent Refinement System v1.0.0**

A 100% local, zero-cost deterministic multi-agent pipeline that transforms raw human thoughts into structured decision-making briefs.

[![GitHub](https://img.shields.io/badge/GitHub-Profile-181717?style=for-the-badge&logo=github)](https://github.com/raphaelmendes-dev)
[![License](https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg?style=for-the-badge&logo=python)](https://www.python.org)
[![Ollama](https://img.shields.io/badge/Ollama-Qwen2.5%3A7b-black.svg?style=for-the-badge)](https://ollama.com)
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
- [Global Context Module](#-global-context-module)
- [License](#-license)
- [Corporate & Research Contact](#-corporate--research-contact)

---

## 🎯 Overview

**Claudio Project (v1.0)** is an offline intellectual augmentation engine built under the **RS4 Lab** experiment framework (*Experiment-005*). Designed to eliminate cognitive fatigue and premature complexity, it ingests unstructured "raw thoughts" and passes them through a deterministic 4-stage local AI reasoning chain powered by Ollama (`qwen2.5:7b`).

The system produces standardized Markdown reports enriched with Front-Matter metadata, automatically categorized into dedicated operational fronts (`LAB`, `COMMERCE`, `FREELAS`, or `SISTEMAS`) for a personal knowledge library.

---

## ⚡ Key Engineering Principles

- **100% Offline & $0.00 Cost:** Runs strictly locally via Ollama REST API (`http://localhost:11434`), guaranteeing data privacy and zero API bills.
- **Deterministic Resource Protection:** Calls one agent at a time to prevent RAM/VRAM saturation on standard host hardware.
- **Controlled Chunking & Anti-Looping:** Context capped at 1,500 characters and responses bounded to 256 max tokens to preserve execution stability (~38s–62s per agent).
- **Graceful Context Injection:** Dynamically integrates `contexto_global.txt` when present, or seamlessly defaults to isolated mode.
- **Cross-Platform Console Resilience:** Standardized UTF-8 stdout re-configuration for legacy Windows terminals (cp1252).

---

## 🏗️ Multi-Agent Sequential Architecture

[ Raw Thought Input (bruto/) ]
│
▼
[ AGENT 1: Structural Mapper ] ──> Deconstructs raw text into Facts, Hypotheses & Risks
│
▼
[ AGENT 2: Tech Scout ]      ──> Evaluates 2026 local tech stacks & feasibility
│
▼
[ AGENT 3: Acid Critic ]     ──> Identifies premature complexity & logical fallacies
│
▼
[ AGENT 4: Synthesizer ]    ──> Generates YAML Front-Matter & "Smallest Next Step"
│
▼
[ Structured Knowledge Base (biblioteca/Refinado_YYYYMMDD_HHMMSS.md) ]


---

## 📂 Project Directory Structure

Claudio-Project.v1/
├── bruto/                      → Input folder for raw thought files (.txt)
│   ├── teste_frontend.txt      → Sample UI/UX input
│   └── teste_backend.txt       → Sample Architecture input
├── agentes/                    → System prompts for the 4 specialized agents
│   ├── agente1_mapeador.txt    → Structural Mapper Prompt
│   ├── agente2_techscout.txt   → Tech Scout Prompt
│   ├── agente3_critico.txt     → Acid Critic Prompt
│   └── agente4_sintetizador.txt → Final Synthesizer Prompt
├── biblioteca/                 → Knowledge Base output folder
│   └── README.md               → Library documentation
├── logs/                       → Local execution logs (git-ignored)
├── assets/                     → Project visual assets & benchmark proofs
├── orquestrador_claudio.py     → Core Python Orchestrator script
├── BASELINE.MD                 → Measured execution times, RAM footprint & CPU benchmarks
├── LICENSE                     → MIT License file
├── .gitignore                  → Strict security & hygiene rules
└── README.md                   → Main documentation


---

## 📊 Empirical Performance & Baseline

Tested on local CPU architecture running Ollama with `qwen2.5:7b`:

| Stage / Agent | Avg Response Time | RAM Footprint | Output Token Cap | Status |
|---|---|---|---|---|
| **Agent 1 — Structural Mapper** | ~37.9s | ~5.2 GB | 256 tokens | ✅ Operational |
| **Agent 2 — Tech Scout** | ~48.9s | ~5.4 GB | 256 tokens | ✅ Operational |
| **Agent 3 — Acid Critic** | ~62.0s | ~5.5 GB | 256 tokens | ✅ Operational |
| **Agent 4 — Synthesizer** | ~62.0s | ~5.5 GB | 256 tokens | ✅ Operational |
| **Total Pipeline Run** | **~219.7s** | **Max 5.5 GB** | **1,024 tokens total** | **Deterministic & Stable** |

For detailed hardware resource utilization graphs and environment specifications, check [BASELINE.MD](./BASELINE.MD).

---

## 🚀 Running Locally

### 1. Prerequisites
- Python 3.10+ (Standard library only — **zero `pip` third-party dependencies**)
- [Ollama](https://ollama.com/) installed and running locally with `qwen2.5:7b`:
  ```bash
  ollama pull qwen2.5:7b
  ```

### 2. Execution
Place your raw text input file inside the `bruto/` directory and execute:

```bash
# Example using the sample front-end test file
python orquestrador_claudio.py teste_frontend.txt
```

The orchestrator will execute the 4 agents sequentially and save the final report inside `biblioteca/Refinado_YYYYMMDD_HHMMSS.md`.

## 🌐 Global Context Module

You can inject global laboratory guidelines (e.g., target architecture constraints or budget rules) into Agent 1 by creating a `contexto_global.txt` file in the root directory or inside `agentes/`.

- **If detected:** Automatically injected into Agent 1 prompt (truncated gracefully at 500 characters).
- **If absent:** System logs `ℹ️ Nenhum arquivo 'contexto_global.txt' detectado. Rodando em modo isolado.` and operates normally.

## 📄 License

This project is open-source software licensed under the MIT License — see the LICENSE file for details.

## 🏢 Corporate & Research Contact

Rs4Machine — AI Research Lab & Autonomous Systems

Founder / Lead Engineer: Raphael Mendes

📧 python.dev.raphael@gmail.com

🔗 GitHub: github.com/raphaelmendes-dev

🏢 LinkedIn Company: RS4Machine Lab

Claudio Project v1.0.0 — September 2026
