<div align="center">
<img src="assets/Rs4Machine.png" alt="Logo Rs4Machine" width="380" />

# 🧠 Projeto Claudio — Rs4Machine

**Sistema de Aumento Intelectual & Refino Multiagente v1.0.0**

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
- [Módulo de Contexto Global](#-módulo-de-contexto-global)
- [Licença](#-licença)
- [Contato Corporativo & Pesquisa](#-contato-corporativo--pesquisa)

---

## 🎯 Visão Geral

O **Projeto Claudio (v1.0)** é um motor de aumento intelectual offline construído sob o framework experimental do **RS4 Lab** (*Experiment-005*). Projetado para eliminar a fadiga cognitiva e a complexidade prematura, ele ingere "pensamentos brutos" não estruturados e os conduz por uma cadeia de raciocínio de IA local determinística em 4 estágios, alimentada pelo Ollama (`qwen2.5:7b`).

O sistema gera relatórios Markdown padronizados, enriquecidos com metadados de Front-Matter, automaticamente categorizados em frentes operacionais dedicadas (`LAB`, `COMMERCE`, `FREELAS` ou `SISTEMAS`) para uma biblioteca pessoal de conhecimento.

---

## ⚡ Princípios-Chave de Engenharia

- **100% Offline & Custo R$ 0,00:** executa estritamente de forma local via API REST do Ollama (`http://localhost:11434`), garantindo privacidade de dados e zero custos de API.
- **Proteção Determinística de Recursos:** chama um agente por vez para evitar saturação de RAM/VRAM em hardware host padrão.
- **Chunking Controlado & Anti-Loop:** contexto limitado a 1.500 caracteres e respostas limitadas a 256 tokens máximos para preservar a estabilidade de execução (~38s–62s por agente).
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

Claudio-Project.v1/
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
├── BASELINE.MD                 → Tempos de execução medidos, footprint de RAM & benchmarks de CPU
├── LICENSE                     → Arquivo da Licença MIT
├── .gitignore                  → Regras estritas de segurança & higiene
└── README.md                   → Documentação principal


---

## 📊 Performance Empírica & Baseline

Testado em arquitetura de CPU local rodando Ollama com `qwen2.5:7b`:

| Etapa / Agente | Tempo Médio de Resposta | Footprint de RAM | Limite de Tokens de Saída | Status |
|---|---|---|---|---|
| **Agente 1 — Mapeador Estrutural** | ~37,9s | ~5,2 GB | 256 tokens | ✅ Operacional |
| **Agente 2 — Tech Scout** | ~48,9s | ~5,4 GB | 256 tokens | ✅ Operacional |
| **Agente 3 — Crítico Ácido** | ~62,0s | ~5,5 GB | 256 tokens | ✅ Operacional |
| **Agente 4 — Sintetizador** | ~62,0s | ~5,5 GB | 256 tokens | ✅ Operacional |
| **Execução Total do Pipeline** | **~219,7s** | **Máx. 5,5 GB** | **1.024 tokens no total** | **Determinística & Estável** |

Para gráficos detalhados de utilização de recursos de hardware e especificações de ambiente, consulte [BASELINE.MD](./BASELINE.MD).

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

Projeto Claudio v1.0.0 — Setembro de 2026
