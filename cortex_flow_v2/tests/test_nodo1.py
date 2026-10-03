# -*- coding: utf-8 -*-
"""Teste rápido do Nó 1 (Agente 1 — Mapeador Estrutural) — Dose 2 / Fase 2.

Executa 'nodo_mapeador' com um estado inicial fictício e confirma:
  - retorno de 'analise_mapeador' não-vazio;
  - retorno de 'contexto_rag' (lista);
  - atualização de 'Metrics/metrics_agente1_v2.json' com status SUCCESS.

Uso: python cortex_flow_v2/tests/test_nodo1.py
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
from cortex_flow_v2.nodes.mapeador import (
    CHROMA_DATA_DIR_ABSOLUTO,
    RUTA_METRICS_AGENTE1,
    nodo_mapeador,
)
from cortex_flow_v2.vectorstore.chroma_client import (
    crear_cliente_chroma,
    garantizar_coleccion_decisoes,
)

ESTADO_FICTICIO: CortexState = {
    "entrada_bruta": (
        "Ideia: plataforma de micro-saúde laboratorial para clínicas populares "
        "em comunidades carentes. Frente Alvo: [X] LAB | [ ] COMMERCE | [ ] GERAL. "
        "Objetivo: reduzir custo de exames de rotina com automação de "
        "agendamento e integração com laboratórios parceiros."
    ),
    "frente_alvo": "LAB / GERAL",
    "analise_mapeador": "",
    "analise_techscout": "",
    "analise_critico": "",
    "sintese_final": "",
    "contexto_rag": [],
    "erros": [],
}

DOCUMENTOS_ANTECEDENTES = [
    {
        "id": "test_nodo1_antecedente_lab",
        "texto": (
            "Decisão anterior: automação de agendamento para laboratórios de "
            "análise clínica em clínicas populares. FATOS: demanda alta por "
            "exames de rotina, agendamento manual gera filas. PREMISSAS: "
            "integração com laboratórios parceiros é viável. SUPOSIÇÕES: o "
            "público-alvo possui acesso a smartphones."
        ),
        "metadata": {"tipo": "decisao_lab", "anio": 2025, "probe_test": True},
    },
    {
        "id": "test_nodo1_antecedente_microsaude",
        "texto": (
            "Decisão anterior: plataforma de micro-saúde para comunidades de "
            "baixa renda, focando exames de rotina. Aprendizado: começar por "
            "LAB antes de COMMERCE, validando o fluxo de coleta com um piloto."
        ),
        "metadata": {"tipo": "decisao_microsaude", "anio": 2025, "probe_test": True},
    },
]


def sembrar_antecedentes() -> None:
    """Insere documentos de exemplo na coleção 'decisoes' (limpos ao final)."""
    cliente = crear_cliente_chroma(CHROMA_DATA_DIR_ABSOLUTO)
    coleccion = garantizar_coleccion_decisoes(cliente)
    coleccion.upsert(
        ids=[d["id"] for d in DOCUMENTOS_ANTECEDENTES],
        documents=[d["texto"] for d in DOCUMENTOS_ANTECEDENTES],
        metadatas=[d["metadata"] for d in DOCUMENTOS_ANTECEDENTES],
    )


def limpar_antecedentes() -> None:
    """Remove os documentos de exemplo da coleção 'decisoes'."""
    try:
        cliente = crear_cliente_chroma(CHROMA_DATA_DIR_ABSOLUTO)
        coleccion = garantizar_coleccion_decisoes(cliente)
        coleccion.delete(where={"probe_test": True})
    except Exception:
        pass


def main() -> int:
    """Executa o teste e retorna 0 se SUCCESS, 1 caso contrário."""
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    print("=" * 78)
    print("TESTE NÓ 1 — AGENTE 1 (MAPEADOR ESTRUTURAL) — Dose 2 / Fase 2")
    print("=" * 78)

    sembrado = False
    try:
        sembrar_antecedentes()
        sembrado = True
        print("✔ Antecedentes de exemplo inseridos na coleção 'decisoes'.")
    except Exception as exc:
        print(f"⚠ Sem sondas de antecedentes (o RAG seguirá vazio): {exc}")

    try:
        print("\n→ Invocando nodo_mapeador(ESTADO_FICTICIO) ...")
        estado_atualizado = nodo_mapeador(ESTADO_FICTICIO)

        analise = str(estado_atualizado.get("analise_mapeador") or "")
        contexto = estado_atualizado.get("contexto_rag") or []
        erros = estado_atualizado.get("erros") or []

        print(f"\n✔ analise_mapeador retornada  -> {len(analise)} caracteres")
        print(f"✔ contexto_rag retornado       -> {len(contexto)} resultado(s)")
        for i, hit in enumerate(contexto, 1):
            print(
                f"   [{i}] id={hit.get('id')} "
                f"distância={hit.get('distancia')}"
            )
        if erros:
            print(f"⚠ erros registrados no estado: {erros}")

        print("\n→ Trecho inicial da análise do Mapeador Estrutural:")
        print("-" * 78)
        print(analise[:800])
        print("-" * 78)

        if not RUTA_METRICS_AGENTE1.exists():
            print(f"\n❌ FAILURE — métricas não encontradas: {RUTA_METRICS_AGENTE1}")
            return 1

        metricas = json.loads(RUTA_METRICS_AGENTE1.read_text(encoding="utf-8"))
        status_metrics = metricas.get("validacion", {}).get("status")
        print(f"\n📊 {RUTA_METRICS_AGENTE1.name} atualizado:")
        print(f"   status                : {status_metrics}")
        print(
            "   rag latência ms       : "
            f"{metricas.get('rag_chromadb', {}).get('latencia_ms')}"
        )
        print(
            "   rag hits              : "
            f"{metricas.get('rag_chromadb', {}).get('total_resultados')}"
        )
        print(
            "   ollama latência ms    : "
            f"{metricas.get('ollama', {}).get('latencia_ms')}"
        )
        print(
            "   ollama modelo         : "
            f"{metricas.get('ollama', {}).get('modelo')}"
        )
        print(
            "   nó duração total ms   : "
            f"{metricas.get('nodo', {}).get('duracao_total_ms')}"
        )

        sucesso = bool(analise.strip()) and status_metrics == "SUCCESS"
        if sucesso:
            print(
                "\n✅ SUCCESS — Nó 1 (Mapeador Estrutural) validado "
                "e métricas atualizadas."
            )
            return 0
        print("\n❌ FAILURE — critérios de validação não atendidos.")
        return 1
    finally:
        if sembrado:
            limpar_antecedentes()
            print("\n🧹 Antecedentes de exemplo removidos da coleção 'decisoes'.")


if __name__ == "__main__":
    raise SystemExit(main())