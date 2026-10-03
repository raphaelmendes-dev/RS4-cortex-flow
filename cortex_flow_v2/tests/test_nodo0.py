# -*- coding: utf-8 -*-
"""Teste rápido do Nó 0 (Agente 0 — Triador / Roteador Dinâmico) — Dose 2 / Fase 2.

Executa 'nodo_triagem' com um estado fictício e confirma:
  - texto de exemplo do Commerce          -> frente_alvo == 'COPY_OFFER';
  - texto de ejemplo Freela / Vaga / Cód. -> frente_alvo == 'BUILDER_TEMPLATE';
  - atualización de 'Metrics/metrics_triagem_v2.json' com status SUCCESS e
    exit_code 0 (e duração medida).

A execução da rama BUILDER é feita primeiro para que o relatório de telemetria
final (metrics_triagem_v2.json) corresponda à ejecución do texto do Commerce,
que é o cenário principal pedido.

Uso: python cortex_flow_v2/tests/test_nodo0.py
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
from cortex_flow_v2.nodes.triagem import (
    INTENCAO_BUILDER_TEMPLATE,
    INTENCAO_COPY_OFFER,
    RUTA_METRICS_TRIAGEM,
    nodo_triagem,
)

# Texto de exemplo do Commerce: copy/anúncio com marcador [X] COMMERCE.
ESTADO_FICTICIO_COPY: CortexState = {
    "entrada_bruta": (
        "Ideia: anúncio de Commerce — campanha de email marketing para lançar "
        "uma oferta com copywriting persuasivo, landing page e call to action. "
        "Frente Alvo: [ ] LAB | [X] COMMERCE | [ ] GERAL. "
        "Objetivo: incrementar as vendas da tienda com promoção."
    ),
    "frente_alvo": "",
    "analise_mapeador": "",
    "analise_techscout": "",
    "analise_critico": "",
    "sintese_final": "",
    "contexto_rag": [],
    "erros": [],
}

# Texto de contraste: freela / vaga / código com marcador [X] FREELAS.
ESTADO_FICTICIO_BUILDER: CortexState = {
    "entrada_bruta": (
        "Ideia: vaga para freelancer remoto — entregar template de código "
        "backend em Python com API e integração. Frente Alvo: [ ] LAB | "
        "[ ] COMMERCE | [X] FREELAS. Objetivo: maquetar projeto técnico "
        "para cliente no-code."
    ),
    "frente_alvo": "",
    "analise_mapeador": "",
    "analise_techscout": "",
    "analise_critico": "",
    "sintese_final": "",
    "contexto_rag": [],
    "erros": [],
}


def main() -> int:
    """Executa o teste e retorna 0 se SUCCESS, 1 caso contrário."""
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    print("=" * 78)
    print("TESTE NÓ 0 — AGENTE 0 (TRIADOR / ROTEADOR DINÁMICO) — Dose 2 / Fase 2")
    print("=" * 78)

    # (a) Rama BUILDER_TEMPLATE (executa primeiro — ver docstring do módulo)
    print("\n→ Invocando nodo_triagem(ESTADO_BUILDER) ...")
    res_builder = nodo_triagem(dict(ESTADO_FICTICIO_BUILDER))
    frente_builder = str(res_builder.get("frente_alvo") or "")
    erros_builder = res_builder.get("erros") or []
    print(f"   frente_alvo -> {frente_builder}")
    ok_builder = (
        frente_builder == INTENCAO_BUILDER_TEMPLATE and not erros_builder
    )

    # (b) Rama COPY_OFFER — texto de exemplo do Commerce (telemetria final)
    print("\n→ Invocando nodo_triagem(ESTADO_COPY_COMMERCE) ...")
    res_copy = nodo_triagem(dict(ESTADO_FICTICIO_COPY))
    frente_copy = str(res_copy.get("frente_alvo") or "")
    erros_copy = res_copy.get("erros") or []
    print(f"   frente_alvo -> {frente_copy}")
    ok_copy = frente_copy == INTENCAO_COPY_OFFER and not erros_copy

    if not RUTA_METRICS_TRIAGEM.exists():
        print(f"\n❌ FAILURE — métricas não encontradas: {RUTA_METRICS_TRIAGEM}")
        return 1

    metricas = json.loads(RUTA_METRICS_TRIAGEM.read_text(encoding="utf-8"))
    validacion = metricas.get("validacion", {})
    status_metrics = validacion.get("status")
    exit_code_metrics = validacion.get("exit_code")
    py_compile_state = validacion.get("py_compile_triagem")
    duracao_ms = metricas.get("nodo", {}).get("duracao_total_ms")
    intencao_metrics = metricas.get("clasificacion", {}).get("intencao")

    print(f"\n📊 {RUTA_METRICS_TRIAGEM.name} atualizado:")
    print(f"   intención registrada  : {intencao_metrics}")
    print(f"   status                : {status_metrics}")
    print(f"   exit_code             : {exit_code_metrics}")
    print(f"   py_compile_triagem    : {py_compile_state}")
    print(f"   nó duração total ms   : {duracao_ms}")

    sucesso = (
        ok_copy
        and ok_builder
        and status_metrics == "SUCCESS"
        and exit_code_metrics == 0
        and py_compile_state == "OK"
        and isinstance(duracao_ms, (int, float))
    )

    if sucesso:
        print(
            "\n✅ SUCCESS — Nó 0 (Triador / Roteador Dinâmico) validado, "
            "frontes rotados e métricas atualizadas."
        )
        return 0
    print("\n❌ FAILURE — critérios de validação não atendidos.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())