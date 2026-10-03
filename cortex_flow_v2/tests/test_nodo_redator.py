# -*- coding: utf-8 -*-
"""Teste rápido do Nó Agente Redator Comercial (Item 08.2) — Dose 2 / Fase 2.

Executa 'nodo_redator' com um estado inicial fictício (oferta COMMERCE) e
confirma:

  - retorno de 'copy_comercial' não-vazio;
  - retorno de 'contexto_rag' (lista — tons/regras de ofertas do DNA);
  - geração do Markdown em 'drafts/ofertas/' com carimbo de data/hora no nome;
  - atualização de 'Metrics/metrics_redator_v2.json' com status SUCCESS e
    exit_code 0 (e duração medida).

Uso: python cortex_flow_v2/tests/test_nodo_redator.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# Garante que a raiz do projeto esteja no sys.path para os imports
RAIZ_PROJETO = Path(__file__).resolve().parents[2]
if RAIZ_PROJETO not in sys.path:
    sys.path.insert(0, str(RAIZ_PROJETO))

from cortex_flow_v2.graph.state import CortexState
from cortex_flow_v2.nodes.redator import (
    DIR_RAFTS_OFERTAS,
    RUTA_METRICS_REDATOR,
    nodo_redator,
)
from cortex_flow_v2.vectorstore.chroma_client import (
    crear_cliente_chroma,
    garantizar_coleccion_decisoes,
)

CHROMA_DATA_DIR_ABSOLUTO = str(RAIZ_PROJETO / "chroma_db_data")

# Oferta fictícia de Commerce: anúncio com frente [X] COMMERCE.
ESTADO_FICTICIO: CortexState = {
    "entrada_bruta": (
        "Ideia: anúncio de Commerce — campanha de email marketing para lançar "
        "uma oferta de assinatura anual da plataforma de micro-saúde "
        "laboratorial a R$ 99,00, com copywriting persuasivo, landing page e "
        "call to action. Frente Alvo: [ ] LAB | [X] COMMERCE | [ ] GERAL. "
        "Objetivo: converter leads em assinantes com promoção."
    ),
    "frente_alvo": "COPY_OFFER",
    "analise_mapeador": "",
    "analise_techscout": "",
    "analise_critico": "",
    "sintese_final": "",
    "contexto_rag": [],
    "erros": [],
}

# Sondas: tons e regras de ofertas como seriam salvos no DNA (coleção 'decisoes').
DOCUMENTOS_ANTECEDENTES = [
    {
        "id": "test_redator_tom_oferta_1",
        "texto": (
            "TOM E REGRA DE OFERTA: As ofertas comerciais do RS4 usam tom "
            "direto, simples e persuasivo, sem promessas exageradas. Headline "
            "curta seguida de benefícios concretos e um CTA único. Focar no "
            "problema resolvido para o cliente, não nas features."
        ),
        "metadata": {"tipo": "ton_oferta", "anio": 2026, "probe_test": True},
    },
    {
        "id": "test_redator_tom_oferta_2",
        "texto": (
            "TOM E REGRA DE OFERTA: Copywriting responsável — nunca inventar "
            "resultados, preços ou estatísticas. Tom otimista porém honesto; "
            "urgência leve em promoções reais; landing page com chamada clara "
            "para o próximo passo do lead."
        ),
        "metadata": {"tipo": "ton_oferta", "anio": 2026, "probe_test": True},
    },
]


def sembrar_antecedentes() -> None:
    """Insere tons/regras de oferta de exemplo na coleção 'decisoes'."""
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
    print("TESTE NÓ REDATOR — AGENTE REDATOR COMERCIAL — Dose 2 / Fase 2 (Item 08.2)")
    print("=" * 78)

    sembrado = False
    try:
        sembrar_antecedentes()
        sembrado = True
        print("✔ Tons/regras de oferta de exemplo inseridos na coleção 'decisoes'.")
    except Exception as exc:
        print(f"⚠ Sem sondas de tons/regras (o RAG seguirá com o DNA real): {exc}")

    try:
        print("\n→ Invocando nodo_redator(ESTADO_FICTICIO) ...")
        estado_atualizado = nodo_redator(ESTADO_FICTICIO)

        copy_comercial = str(estado_atualizado.get("copy_comercial") or "")
        contexto = estado_atualizado.get("contexto_rag") or []
        caminho_md = str(estado_atualizado.get("caminho_copy_md") or "")
        erros = estado_atualizado.get("erros") or []

        print(f"\n✔ copy_comercial retornada     -> {len(copy_comercial)} caracteres")
        print(f"✔ contexto_rag retornado       -> {len(contexto)} resultado(s)")
        for i, hit in enumerate(contexto, 1):
            print(f"   [{i}] id={hit.get('id')} distância={hit.get('distancia')}")
        print(f"✔ caminho_copy_md              -> {caminho_md}")
        if erros:
            print(f"⚠ erros registrados no estado: {erros}")

        # Verificação do Markdown salvo em drafts/ofertas/ com carimbo de hora
        ok_markdown = False
        if caminho_md:
            arquivo_md = Path(caminho_md)
            carimbo_ok = bool(
                re.search(r"oferta_\d{8}_\d{6}\.md$", arquivo_md.name)
            )
            ok_markdown = arquivo_md.is_file() and carimbo_ok
            print(f"✔ arquivo Markdown existe      -> {arquivo_md.is_file()}")
            print(f"✔ carimbo de data/hora no nome -> {carimbo_ok}")

        print("\n→ Trecho inicial da copy comercial gerada:")
        print("-" * 78)
        print(copy_comercial[:800])
        print("-" * 78)

        if not RUTA_METRICS_REDATOR.exists():
            print(f"\n❌ FAILURE — métricas não encontradas: {RUTA_METRICS_REDATOR}")
            return 1

        metricas = json.loads(RUTA_METRICS_REDATOR.read_text(encoding="utf-8"))
        status_metrics = metricas.get("validacion", {}).get("status")
        exit_code_metrics = metricas.get("validacion", {}).get("exit_code")
        py_compile_state = metricas.get("validacion", {}).get("py_compile_redator")
        duracao_ms = metricas.get("nodo", {}).get("duracao_total_ms")
        modelo_usado = metricas.get("ollama", {}).get("modelo")

        print(f"\n📊 {RUTA_METRICS_REDATOR.name} atualizado:")
        print(f"   status                : {status_metrics}")
        print(f"   exit_code             : {exit_code_metrics}")
        print(f"   py_compile_redator    : {py_compile_state}")
        print(f"   modelo ollama         : {modelo_usado}")
        print(f"   nó duração total ms   : {duracao_ms}")

        sucesso = (
            bool(copy_comercial.strip())
            and ok_markdown
            and status_metrics == "SUCCESS"
            and exit_code_metrics == 0
            and py_compile_state == "OK"
            and isinstance(duracao_ms, (int, float))
        )

        if sucesso:
            print(
                "\n✅ SUCCESS — Nó Redator Comercial validado: RAG do DNA, copy "
                "gerada, Markdown salvo e métricas atualizadas."
            )
            return 0
        print("\n❌ FAILURE — critérios de validação não atendidos.")
        return 1
    finally:
        if sembrado:
            limpar_antecedentes()
            print("\n🧹 Tons/regras de oferta de exemplo removidos da coleção 'decisoes'.")


if __name__ == "__main__":
    raise SystemExit(main())