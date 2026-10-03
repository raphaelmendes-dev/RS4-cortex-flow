# -*- coding: utf-8 -*-
"""Teste rápido do Nó Agente 2 (Tech Scout & Search Engine) — Item 08.3, Dose 2 / Fase 2.

Executa 'nodo_techscout' com estados simulados provenientes do Mapeador
(ex.: "Criar uma API Python simples") e confirma em dois cenários:

  1) RAG suficiente (decisão técnica semeada) -> busca web pulada (memória);
  2) RAG insuficiente (tema novo)             -> busca web acionada
     (duckduckgo-search);

E ainda:
  - retorno de 'analise_techscout' não-vazio (relatório técnico enxuto);
  - execução do fluxo RAG -> (se insuficiente) busca web -> Ollama -> memória;
  - registro da flag 'busca_web_acionada' no estado E nas métricas;
  - gravação da nova memória/decisão na coleção 'decisoes' do ChromaDB;
  - atualização de 'Metrics/metrics_techscout_v2.json' com status SUCCESS,
    exit_code 0 e py_compile OK (Regra CEO RS4).

A memória gerada pelo nó é removida ao final do teste (cleanup por id
determinístico), para não poluir a base 'decisoes'.

Uso: python cortex_flow_v2/tests/test_nodo_techscout.py
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
from cortex_flow_v2.nodes.techscout import (
    RUTA_METRICS_TECHSCOUT,
    gerar_id_memoria,
    nodo_techscout,
)
from cortex_flow_v2.vectorstore.chroma_client import (
    crear_cliente_chroma,
    garantizar_coleccion_decisoes,
)

CHROMA_DATA_DIR_ABSOLUTO = str(RAIZ_PROJETO / "chroma_db_data")

# Estado simulado vindo do Mapeador (Agente 1) para a ideia "Criar uma API
# Python simples" (cenário do item 08.3). Para este cenário o teste SEMEIA uma
# decisão técnica relevante na coleção (tipo 'dec_techscout'), fazendo o RAG ser
# suficiente e a busca web ser corretamente pulada (busca_web_acionada=False):
# isso valida o mecanismo de 'evitar buscas futuras repetidas'.
ANALISE_MAPEADOR = (
    "ANÁLISE DO AGENTE 1 — Mapeador e Analista Estrutural\n\n"
    "**FATOS:**\n"
    "- O usuário quer criar uma API Python simples do tipo CRUD de tarefas.\n"
    "- O ambiente alvo é local/desktop, com custo R$ 0,00.\n"
    "- O banco de dados será SQLite (arquivo local, sem servidor).\n"
    "- A ferramenta principal é código aberto e roda sem nuvem paga.\n\n"
    "**PREMISSAS:**\n"
    "- Python 3.11+ disponível localmente.\n"
    "- Entrega via linha de comando/git.\n\n"
    "**SUPOSIÇÕES:**\n"
    "- Framework web (FastAPI ou Flask) é aceitável.\n\n"
    "**PROBLEMA CENTRAL:**\n"
    "- Escolher a menor stack confiável e gratuita para entregar uma API "
    "Python CRUD com SQLite em ambiente local.\n\n"
    "[TECHSCOUT-TESTE-08.3-A]"
)

ESTADO_FICTICIO: CortexState = {
    "entrada_bruta": (
        "Criar uma API Python simples — CRUD de tarefas com SQLite, sem custo "
        "de hospedagem, usando apenas ferramentas open-source."
    ),
    "frente_alvo": "GERAL",
    "analise_mapeador": ANALISE_MAPEADOR,
    "analise_techscout": "",
    "analise_critico": "",
    "sintese_final": "",
    "contexto_rag": [],
    "erros": [],
}

# Segundo estado: análise com tema FORA do escopo da base 'decisoes' (não há
# antecedentes similares). Nesse cenário o RAG é insuficiente e o nó DEVE
# acionar a busca web via duckduckgo-search (busca_web_acionada=True), exercitando
# o caminho completo RAG -> WEB -> Ollama -> memória.
ANALISE_MAPEADOR_WEB = (
    "ANÁLISE DO AGENTE 1 — Mapeador e Analista Estrutural\n\n"
    "**FATOS:**\n"
    "- Cliente veterinário deseja um sistema de agendamento de consultas "
    "com lembrete automático por WhatsApp.\n"
    "- Funciona offline/na loja, sem requisito de nuvem paga.\n"
    "- Precisa de relatório simples de clientes e horários.\n\n"
    "**PROBLEMA CENTRAL:**\n"
    "- Montar uma solução local de baixo custo (ideal R$ 0,00) para "
    "agendamento veterinário com integração WhatsApp.\n\n"
    "[TECHSCOUT-TESTE-08.3-B-WEB]"
)

ESTADO_FICTICIO_WEB: CortexState = {
    "entrada_bruta": (
        "Sistema de agendamento para clínica veterinária com lembrete por "
        "WhatsApp, operação local e custo zero de software."
    ),
    "frente_alvo": "GERAL",
    "analise_mapeador": ANALISE_MAPEADOR_WEB,
    "analise_techscout": "",
    "analise_critico": "",
    "sintese_final": "",
    "contexto_rag": [],
    "erros": [],
}


# Semente de "decisão técnica relevante" para o cenário 1: simula uma memória
# do próprio Tech Scout já salva na coleção, cujo conteúdo casa com a análise
# "API Python simples" (id determinístico igual ao id que o nó usaria).
ID_DECISAO_SEMEADA = gerar_id_memoria(ANALISE_MAPEADOR)
DECISAO_SEMEADA = (
    "DECISÃO DO TECH SCOUT (memória de decisão técnica de teste):\n"
    "Análise: criar uma API Python simples do tipo CRUD de tarefas, ambiente "
    "local/desktop com custo R$ 0,00, banco SQLite, ferramenta open-source.\n"
    "Stack recomendada: Python 3.11+ com FastAPI + Uvicorn, banco SQLite, "
    "testes com pytest, documentação com docstrings.\n"
    "Alternativas: Flask, sqlite3 nativo.\n"
    "Boas práticas: manter arquitetura simples/monolítica para a v1."
)


def sembrar_decisao_python() -> None:
    """Insere uma decisão técnica relevante na coleção 'decisoes' (cenário 1)."""
    cliente = crear_cliente_chroma(CHROMA_DATA_DIR_ABSOLUTO)
    coleccion = garantizar_coleccion_decisoes(cliente)
    coleccion.upsert(
        ids=[ID_DECISAO_SEMEADA],
        documents=[DECISAO_SEMEADA],
        metadatas=[
            {
                "tipo": "dec_techscout",
                "frente_alvo": "GERAL",
                "origem": "chroma",
                "modelo": "qwen2.5:7b",
                "probe_test": True,
            }
        ],
    )


def _ids_teste() -> list[str]:
    """Ids determinísticos criados pelo teste (deduplicados).

    A semente do cenário 1 usa o MESMO id da memória que o nó gravaria para
    ANALISE_MAPEADOR — o set remove o duplicado, pois o ChromaDB rejeita ids
    repetidos na chamada delete().
    """
    return sorted(
        {
            gerar_id_memoria(ANALISE_MAPEADOR),
            gerar_id_memoria(ANALISE_MAPEADOR_WEB),
        }
    )


def limpar_memoria_teste() -> None:
    """Remove as memórias/sementes do teste no ChromaDB (ids determinísticos)."""
    try:
        cliente = crear_cliente_chroma(CHROMA_DATA_DIR_ABSOLUTO)
        coleccion = garantizar_coleccion_decisoes(cliente)
        coleccion.delete(ids=_ids_teste())
    except Exception:
        pass


def _executar_cenario(nome: str, estado: CortexState) -> dict:
    """Executa o nó para um cenário e imprime um resumo compacto."""
    print("=" * 78)
    print(f"CENÁRIO: {nome}")
    print("=" * 78)
    estado_atualizado = nodo_techscout(estado)

    analise = str(estado_atualizado.get("analise_techscout") or "")
    contexto = estado_atualizado.get("contexto_rag") or []
    busca_web = bool(estado_atualizado.get("busca_web_acionada"))
    erros = estado_atualizado.get("erros") or []

    print(f"✔ analise_techscout retornada   -> {len(analise)} caracteres")
    print(f"✔ contexto_rag retornado        -> {len(contexto)} resultado(s)")
    for i, hit in enumerate(contexto, 1):
        print(
            f"   [{i}] id={hit.get('id')} distância={hit.get('distancia')}"
        )
    print(f"✔ busca_web_acionada           -> {busca_web}")
    if erros:
        print(f"⚠ erros registrados no estado: {erros}")

    print("\n→ Trecho inicial do relatório técnico do Tech Scout:")
    print("-" * 78)
    print(analise[:700])
    print("-" * 78)
    return estado_atualizado


def main() -> int:
    """Executa o teste e retorna 0 se SUCCESS, 1 caso contrário."""
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    print("=" * 78)
    print("TESTE NÓ AGENTE 2 — TECH SCOUT & SEARCH ENGINE (Item 08.3)")
    print("=" * 78)

    try:
        # Cenário 1: Mapeador -> "Criar uma API Python simples".
        # Semeia decisão técnica relevante => RAG suficiente => busca web pulada
        # (mecanismo de memória: evitar buscas futuras repetidas).
        sembrar_decisao_python()
        r1 = _executar_cenario(
            "1) API Python simples (decisão técnica semeada => RAG suficiente)",
            ESTADO_FICTICIO,
        )
        web_r1 = bool(r1.get("busca_web_acionada"))

        # Remove a semente e a memória do cenário 1 para isolar o cenário 2.
        limpar_memoria_teste()

        # Cenário 2: tema sem decisões técnicas na base => RAG insuficiente =>
        # busca web acionada via duckduckgo-search.
        r2 = _executar_cenario(
            "2) Agendamento veterinário + WhatsApp (RAG insuficiente => WEB)",
            ESTADO_FICTICIO_WEB,
        )

        analise_r1 = str(r1.get("analise_techscout") or "")
        analise_r2 = str(r2.get("analise_techscout") or "")
        web_r2 = bool(r2.get("busca_web_acionada"))

        if not RUTA_METRICS_TECHSCOUT.exists():
            print(
                f"\n❌ FAILURE — métricas não encontradas: {RUTA_METRICS_TECHSCOUT}"
            )
            return 1

        metricas = json.loads(RUTA_METRICS_TECHSCOUT.read_text(encoding="utf-8"))
        status_metrics = metricas.get("validacion", {}).get("status")
        exit_code_metrics = metricas.get("validacion", {}).get("exit_code")
        py_compile_state = metricas.get("validacion", {}).get(
            "py_compile_techscout"
        )
        duracao_ms = metricas.get("nodo", {}).get("duracao_total_ms")
        modelo_usado = metricas.get("ollama", {}).get("modelo")
        web_acionada_metrics = metricas.get("nodo", {}).get(
            "busca_web_acionada"
        )
        resultados_web_total = metricas.get("nodo", {}).get(
            "resultados_web_total"
        )
        memoria_salva = metricas.get("nodo", {}).get("memoria_salva")
        memoria_id_metrics = metricas.get("memoria_chromadb", {}).get(
            "id_memoria"
        )
        busca_web_block = metricas.get("busca_web", {})
        web_status = busca_web_block.get("status")
        web_motivo = busca_web_block.get("motivo") or (
            busca_web_block.get("consulta_web_preview") or ""
        )

        print(f"\n📊 {RUTA_METRICS_TECHSCOUT.name} atualizado (último cenário):")
        print(f"   status                : {status_metrics}")
        print(f"   exit_code             : {exit_code_metrics}")
        print(f"   py_compile_techscout  : {py_compile_state}")
        print(f"   modelo ollama         : {modelo_usado}")
        print(f"   busca_web_acionada    : {web_acionada_metrics}")
        print(f"   busca_web status      : {web_status}")
        print(f"   resultados_web_total  : {resultados_web_total}")
        print(f"   memoria_salva         : {memoria_salva}")
        print(f"   memoria_id            : {memoria_id_metrics}")
        print(f"   nó duração total ms   : {duracao_ms}")
        if web_motivo:
            print(f"   busca_web motivo      : {web_motivo[:120]}")

        # Critérios: relatório em AMBOS cenários, web pulada no cenário 1
        # (memória suficiente) e acionada no cenário 2 (RAG insuficiente);
        # métricas de SUCCESS com exit_code 0 (Regra CEO RS4).
        sucesso = (
            bool(analise_r1.strip())
            and bool(analise_r2.strip())
            and not web_r1
            and web_r2
            and status_metrics == "SUCCESS"
            and exit_code_metrics == 0
            and py_compile_state == "OK"
            and isinstance(duracao_ms, (int, float))
            and isinstance(web_acionada_metrics, bool)
            and memoria_salva
        )

        if sucesso:
            print(
                "\n✅ SUCCESS — Nó Tech Scout validado: RAG no ChromaDB, busca "
                "web acionada quando o RAG é insuficiente (duckduckgo-search), "
                "relatório técnico enxuto via Ollama, memória gravada de volta "
                "e métricas atualizadas com exit_code 0."
            )
            return 0
        print("\n❌ FAILURE — critérios de validação não atendidos.")
        return 1
    finally:
        limpar_memoria_teste()
        print(
            "\n🧹 Memórias criadas pelo teste removidas da coleção 'decisoes' "
            "(ids determinísticos)."
        )


if __name__ == "__main__":
    raise SystemExit(main())

