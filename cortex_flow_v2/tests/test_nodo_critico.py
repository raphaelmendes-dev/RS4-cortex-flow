# -*- coding: utf-8 -*-
"""Teste rápido do Nó Agente 3 (Crítico Ácido de Engenharia) — Item 08.4, Dose 2 / Fase 2.

Executa 'nodo_critico' com estados simulados provenientes dos nós anteriores
do grafo V2 e confirma em dois cenários:

  1) Fluxo TÉCNICO  : estado com 'analise_mapeador' + 'analise_techscout'
                      (o nó audita o relatório técnico do Tech Scout);
  2) Fluxo COMERCIAL: estado com 'entrada_bruta' + 'copy_comercial'
                      (o nó audita a copy comercial do Redator).

E ainda valida:
  - retorno de 'analise_critico' não-vazio em AMBOS cenários (parecer
    cético/frio/cirúrgico sobre riscos, furos de lógica e complexidade);
  - consulta RAG na coleção 'decisoes' que recupera o DNA da Filosofia RS4
    (hits com metadata tipo 'dna_filosofia');
  - chamada ao Ollama no modelo preferido 'qwen2.5:7b' com fallback
    seguro para 'qwen2.5:3b';
  - atualização de 'Metrics/metrics_critico_v2.json' com status SUCCESS,
    exit_code 0 e py_compile OK (Regla CEO RS4).

Uso: python cortex_flow_v2/tests/test_nodo_critico.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Garante que a raiz do projeto esteja no sys.path para os imports
RAIZ_PROJETO = Path(__file__).resolve().parents[2]
if RAIZ_PROJETO not in sys.path:
    sys.path.insert(0, str(RAIZ_PROJETO))

from cortex_flow_v2.graph.state import CortexState
from cortex_flow_v2.nodes.critico import (
    MODELO_FALLBACKS,
    MODELO_PRINCIPAL,
    RUTA_METRICS_CRITICO,
    nodo_critico,
)

# ---------------- Cenário 1: fluxo TÉCNICO ----------------
# Estado vindo do Mapeador (Agente 1) + Tech Scout (Agente 2) para a ideia
# "Criar uma API Python simples" — o Crítico Ácido deve auditar o relatório
# técnico (fuente: analise_techscout).
ANALISE_MAPEADOR = (
    "ANÁLISE DO AGENTE 1 — Mapeador e Analista Estrutural\n\n"
    "**FATOS:**\n"
    "- O usuário quer criar uma API Python simples do tipo CRUD de tarefas.\n"
    "- O ambiente alvo é local/desktop, com custo R$ 0,00.\n"
    "- O banco de dados será SQLite (arquivo local, sem servidor).\n\n"
    "**PREMISSAS:**\n"
    "- Python 3.11+ disponível localmente.\n"
    "- Entrega via linha de comando/git.\n\n"
    "**PROBLEMA CENTRAL:**\n"
    "- Escolher a menor stack confiável e gratuita para entregar uma API "
    "Python CRUD com SQLite em ambiente local.\n\n"
    "[CRITICO-TESTE-08.4-A]"
)

ANALISE_TECHSCOUT = (
    "**RELATÓRIO TÉCNICO ENXUTO — AGENTE 2 (TECH SCOUT)**\n\n"
    "Stack recomendada: Python 3.11+ com FastAPI + Uvicorn, SQLite, pytest e "
    "documentación com docstrings. Alternativas: Flask e sqlite3 nativo.\n"
    "Boas práticas: arquitetura monolítica/simples para a v1, sem containers, "
    "sem orquestración, sem microservicios.\n"
    "[CRITICO-TESTE-08.4-A]"
)

ESTADO_TECNICO: CortexState = {
    "entrada_bruta": (
        "Criar uma API Python simples — CRUD de tarefas com SQLite, sem custo "
        "de hospedagem, usando apenas ferramentas open-source."
    ),
    "frente_alvo": "GERAL",
    "analise_mapeador": ANALISE_MAPEADOR,
    "analise_techscout": ANALISE_TECHSCOUT,
    "analise_critico": "",
    "sintese_final": "",
    "contexto_rag": [],
    "erros": [],
}

# ---------------- Cenário 2: fluxo COMERCIAL ----------------
# Estado vindo do Redator Comercial (Item 08.2) — o nó audita a copy
# comercial (fuente: copy_comercial) que, conforme a especificação do Item
# 08.4, também é material válido para o Crítico Ácido.
COPY_COMERCIAL = (
    "# COPY COMERCIAL / ANÚNCIO\n\n"
    "**Headline:** Análises de laboratório a R$ 99/ano para a sua clínica.\n\n"
    "**Corpo:** Plataforma de micro-saúde laboratorial que automatiza pedidos "
    "de exames de rotina para clínicas populares. Reduza custos operativos, "
    "elimine papel e entregue resultados mais rápido aos pacientes. Incluye "
    "agendamento, recordatorios por WhatsApp e reportes de laboratorio.\n\n"
    "**CTA:** Agende uma demo gratuita hoje.\n"
    "[CRITICO-TESTE-08.4-B]"
)

ESTADO_COMERCIAL: CortexState = {
    "entrada_bruta": (
        "Ideia: anúncio de Commerce — campanha de email marketing para lançar "
        "una oferta de R$ 99,00 na assinatura anual da plataforma de "
        "micro-saúde laboratorial, com copywriting persuasivo, landing page e "
        "call to action. Frente Alvo: [ ] LAB | [X] COMMERCE | [ ] GERAL."
    ),
    "frente_alvo": "COPY_OFFER",
    "analise_mapeador": "",
    "analise_techscout": "",
    "analise_critico": "",
    "sintese_final": "",
    "contexto_rag": [],
    "erros": [],
    "copy_comercial": COPY_COMERCIAL,  # entrega final do Redator (Item 08.2)
}


def _executar_cenario(nome: str, estado: CortexState) -> dict:
    """Executa o nó para um cenário e imprime um resumo compacto."""
    print("=" * 78)
    print(f"CENÁRIO: {nome}")
    print("=" * 78)
    estado_actualizado = nodo_critico(estado)

    analise = str(estado_actualizado.get("analise_critico") or "")
    contexto = estado_actualizado.get("contexto_rag") or []
    erros = estado_actualizado.get("erros") or []

    print(f"✔ analise_critico retornada  -> {len(analise)} caracteres")
    print(f"✔ contexto_rag retornado     -> {len(contexto)} resultado(s)")
    for i, hit in enumerate(contexto, 1):
        meta = hit.get("metadata") or {}
        print(
            f"   [{i}] id={hit.get('id')} tipo={meta.get('tipo')} "
            f"distância={hit.get('distancia')}"
        )
    if erros:
        print(f"⚠ erros registrados no estado: {erros}")

    print("\n→ Trecho inicial do parecer crítico:")
    print("-" * 78)
    print(analise[:700])
    print("-" * 78)
    return estado_actualizado


def main() -> int:
    """Executa o teste e retorna 0 se SUCCESS, 1 caso contrário."""
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    print("=" * 78)
    print("TESTE NÓ AGENTE 3 — CRÍTICO ÁCIDO DE ENGENHARIA (Item 08.4)")
    print("=" * 78)

    try:
        r1 = _executar_cenario(
            "1) Fluxo TÉCNICO (analise_mapeador + analise_techscout)",
            ESTADO_TECNICO,
        )
        r2 = _executar_cenario(
            "2) Fluxo COMERCIAL (copy_comercial do Redator)",
            ESTADO_COMERCIAL,
        )

        analise_r1 = str(r1.get("analise_critico") or "")
        analise_r2 = str(r2.get("analise_critico") or "")
        rag_r1 = r1.get("contexto_rag") or []
        rag_r2 = r2.get("contexto_rag") or []

        if not RUTA_METRICS_CRITICO.exists():
            print(
                f"\n❌ FAILURE — métricas não encontradas: {RUTA_METRICS_CRITICO}"
            )
            return 1

        metricas = json.loads(RUTA_METRICS_CRITICO.read_text(encoding="utf-8"))
        status_metrics = metricas.get("validacion", {}).get("status")
        exit_code_metrics = metricas.get("validacion", {}).get("exit_code")
        py_compile_state = metricas.get("validacion", {}).get(
            "py_compile_critico"
        )
        nodo_estado = metricas.get("validacion", {}).get("nodo_estado")
        duracao_ms = metricas.get("nodo", {}).get("duracao_total_ms")
        modelo_usado = metricas.get("ollama", {}).get("modelo")
        fallback_usado = metricas.get("ollama", {}).get("fallback_usado")
        fuente_material = metricas.get("nodo", {}).get("fuente_material")
        rag_total_metrics = metricas.get("nodo", {}).get("contexto_rag_total")
        modelos_permitidos = {MODELO_PRINCIPAL, *MODELO_FALLBACKS}

        print(f"\n📊 {RUTA_METRICS_CRITICO.name} atualizado (último cenário):")
        print(f"   status                : {status_metrics}")
        print(f"   exit_code             : {exit_code_metrics}")
        print(f"   py_compile_critico    : {py_compile_state}")
        print(f"   nodo_estado           : {nodo_estado}")
        print(f"   modelo ollama         : {modelo_usado}")
        print(f"   fallback_usado        : {fallback_usado}")
        print(f"   fuente_material       : {fuente_material}")
        print(f"   contexto_rag (nodo)   : {rag_total_metrics}")
        print(f"   nó duração total ms   : {duracao_ms}")

        def _hay_dna(hits: list) -> bool:
            """True se ao menos um hit do RAG traz DNA da Filosofia RS4."""
            return any(
                (h.get("metadata") or {}).get("tipo") == "dna_filosofia"
                for h in hits
            )

        # Critérios: parecer em AMBOS cenários, molécula RAG com DNA da
        # Filosofía RS4, métricas de SUCCESS com exit_code 0 (Regla CEO RS4)
        # e uso de um dos modelos da cadeia qwen2.5:7b -> qwen2.5:3b.
        sucesso = (
            bool(analise_r1.strip())
            and bool(analise_r2.strip())
            and bool(rag_r1)
            and bool(rag_r2)
            and _hay_dna(rag_r1)
            and _hay_dna(rag_r2)
            and status_metrics == "SUCCESS"
            and exit_code_metrics == 0
            and py_compile_state == "OK"
            and nodo_estado == "OK"
            and modelo_usado in modelos_permitidos
            and isinstance(duracao_ms, (int, float))
            and bool(fuente_material)
        )

        if sucesso:
            print(
                "\n✅ SUCCESS — Nó Crítico Ácido validado: material do estado "
                "(analise_techscout e copy_comercial), RAG do DNA da Filosofía "
                "RS4 via 'decisoes', parecer cético/frio/cirúrgico via Ollama "
                "("
                + str(modelo_usado)
                + ") e Metrics/metrics_critico_v2.json com status SUCCESS, "
                "exit_code 0."
            )
            return 0
        print("\n❌ FAILURE — critérios de validação não atendidos.")
        return 1
    finally:
        print("\n🧹 Teste finalizado (o nó não cria memórias persistentes).")


if __name__ == "__main__":
    raise SystemExit(main())