# -*- coding: utf-8 -*-
"""Nó Agente 1 (Mapeador Estrutural) — Cortex-Flow V2 (Dose 2 / Fase 2).

Primeiro nó funcional do grafo V2 (LangGraph-ready) sobre o CortexState:

  a) Consulta a coleção 'decisoes' no ChromaDB e recupera antecedentes e
     decisões similares à 'entrada_bruta' (RAG).
  b) Monta o prompt do Mapeador Estrutural: regras do prompt do Agente 1
     (agentes/agente1_mapeador.txt) + entrada_bruta + contexto RAG.
  c) Executa a chamada local ao Ollama ('qwen2.5:7b' com fallback seguro
     para 'qwen2.5:3b'), temperature=0.1, num_predict=512.
  d) Retorna a atualização de estado com 'analise_mapeador' e 'contexto_rag'.

Telemetria (Regra CEO RS4): mede a latência exata do ChromaDB e do Ollama e
grava o resultado completo da execução em Metrics/metrics_agente1_v2.json.
"""

from __future__ import annotations

import datetime
import json
import platform
import py_compile
import socket
import time
import urllib.error
import urllib.request
from pathlib import Path

import chromadb

from cortex_flow_v2.graph.state import CortexState
from cortex_flow_v2.vectorstore.chroma_client import (
    COLLECTION_DECISOES,
    OLLAMA_BASE_URL,
    crear_cliente_chroma,
    garantizar_coleccion_decisoes,
)

# ---------------- Constantes ----------------
MODELO_PRINCIPAL = "qwen2.5:7b"
MODELO_FALLBACK = "qwen2.5:3b"
TEMPERATURA = 0.1
NUM_PREDICT = 512
TIMEOUT_OLLAMA_S = 240
N_RESULTADOS_RAG = 3

DIR_RAIZ = Path(__file__).resolve().parents[2]
CHROMA_DATA_DIR_ABSOLUTO = str(DIR_RAIZ / "chroma_db_data")
CAMINHO_PROMPT_AGENTE1 = DIR_RAIZ / "agentes" / "agente1_mapeador.txt"
RUTA_METRICS_AGENTE1 = DIR_RAIZ / "Metrics" / "metrics_agente1_v2.json"
OLLAMA_API_GENERATE = f"{OLLAMA_BASE_URL}/api/generate"


def _agora() -> datetime.datetime:
    """Timestamp ISO/legível para a telemetria."""
    return datetime.datetime.now()


def cargar_reglas_agente1() -> str:
    """Lê e retorna as regras do prompt do Agente 1 (Mapeador Estrutural)."""
    if not CAMINHO_PROMPT_AGENTE1.exists():
        raise FileNotFoundError(
            f"Prompt do Agente 1 não encontrado: {CAMINHO_PROMPT_AGENTE1}"
        )
    return CAMINHO_PROMPT_AGENTE1.read_text(encoding="utf-8").strip()


def recuperar_contexto_rag(
    entrada_bruta: str, n_resultados: int = N_RESULTADOS_RAG
) -> dict:
    """Consulta a coleção 'decisoes' no ChromaDB e mede a latência exata.

    Em caso de falha não levanta exceção: devolve status 'ERROR' para que o nó
    continue com contexto RAG vazio (degradação graciosa, sem abortar o grafo).
    """
    inicio = time.perf_counter()
    try:
        cliente = crear_cliente_chroma(CHROMA_DATA_DIR_ABSOLUTO)
        coleccion = garantizar_coleccion_decisoes(cliente)
        resultado = coleccion.query(
            query_texts=[entrada_bruta], n_results=n_resultados
        )
        latencia_ms = round((time.perf_counter() - inicio) * 1000, 4)

        if isinstance(resultado, dict):  # chromadb >= 1.5
            ids = resultado.get("ids") or [[]]
            docs = resultado.get("documents") or [[]]
            metas = resultado.get("metadatas") or [[]]
            dists = resultado.get("distances") or [[]]
        else:  # chromadb < 1.5 (QueryResult)
            ids = resultado.ids or [[]]
            docs = resultado.documents or [[]]
            metas = resultado.metadatas or [[]]
            dists = resultado.distances or [[]]

        lista_ids = ids[0] if ids and isinstance(ids[0], list) else []
        lista_docs = docs[0] if docs and isinstance(docs[0], list) else []
        lista_metas = metas[0] if metas and isinstance(metas[0], list) else []
        lista_dists = dists[0] if dists and isinstance(dists[0], list) else []

        hits: list[dict] = []
        for i, doc_id in enumerate(lista_ids):
            hits.append(
                {
                    "id": doc_id,
                    "documento": lista_docs[i] if i < len(lista_docs) else "",
                    "metadata": lista_metas[i] if i < len(lista_metas) else {},
                    "distancia": (
                        round(float(lista_dists[i]), 6)
                        if i < len(lista_dists) and lista_dists[i] is not None
                        else None
                    ),
                }
            )

        return {
            "coleccion": COLLECTION_DECISOES,
            "query_preview": entrada_bruta[:120],
            "n_resultados_requeridos": n_resultados,
            "total_resultados": len(hits),
            "hits": hits,
            "latencia_ms": latencia_ms,
            "status": "OK",
            "erro": None,
        }
    except Exception as exc:
        latencia_ms = round((time.perf_counter() - inicio) * 1000, 4)
        return {
            "coleccion": COLLECTION_DECISOES,
            "query_preview": entrada_bruta[:120],
            "n_resultados_requeridos": n_resultados,
            "total_resultados": 0,
            "hits": [],
            "latencia_ms": latencia_ms,
            "status": "ERROR",
            "erro": f"{type(exc).__name__}: {exc}",
        }


def montar_prompt_agente1(
    regras_agente: str, entrada_bruta: str, rag: dict
) -> str:
    """Monta o prompt do Agente 1 concatenando regras + entrada + contexto RAG."""
    hits = rag.get("hits") or []
    if hits:
        linhas = []
        for i, hit in enumerate(hits, 1):
            dist = hit.get("distancia")
            dist_str = f" (distância={dist})" if dist is not None else ""
            texto_doc = str(hit.get("documento") or "")[:400]
            linhas.append(f"  [{i}] {texto_doc}{dist_str}")
        contexto_rag = "\n".join(linhas)
    else:
        contexto_rag = (
            "  Nenhum antecedente/decisão similar encontrado na base ChromaDB "
            "para esta entrada."
        )

    return (
        "SYSTEM — AGENTE 1 (MAPEADOR ESTRUTURAL):\n"
        f"{regras_agente}\n\n"
        "ENTRADA BRUTA A ANALISAR:\n"
        f"{entrada_bruta}\n\n"
        "CONTEXTO RAG (ANTECEDENTES E DECISÕES SIMILARES — CHROMADB):\n"
        f"{contexto_rag}\n\n"
        "INSTRUÇÃO DE SAÍDA:\n"
        "Apresente sua análise do Agente 1: FATOS, PREMISSAS, SUPOSIÇÕES e o "
        "problema central, conforme as diretrizes acima. Seja direto e objetivo."
    )


def _chamar_modelo(modelo: str, prompt: str) -> tuple[str | None, dict]:
    """Chama /api/generate para um modelo específico e mede a latência exata."""
    payload = {
        "model": modelo,
        "prompt": prompt,
        "stream": False,
        "options": {"num_predict": NUM_PREDICT, "temperature": TEMPERATURA},
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        OLLAMA_API_GENERATE,
        data=data,
        headers={"Content-Type": "application/json"},
    )
    inicio = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_OLLAMA_S) as resp:
            resposta_raw = json.loads(resp.read().decode("utf-8"))
        latencia_ms = round((time.perf_counter() - inicio) * 1000, 4)
        texto = str(resposta_raw.get("response", "")).strip()
        return texto, {
            "modelo": modelo,
            "status_http": resp.status,
            "latencia_ms": latencia_ms,
            "tokens_prompt": resposta_raw.get("prompt_eval_count"),
            "tokens_resposta": resposta_raw.get("eval_count"),
            "eval_duration_ms": (
                round(resposta_raw.get("eval_duration", 0) / 1e6, 2)
                if resposta_raw.get("eval_duration")
                else None
            ),
            "done_reason": resposta_raw.get("done_reason"),
            "erro": None,
        }
    except (
        urllib.error.URLError,
        urllib.error.HTTPError,
        socket.timeout,
        OSError,
    ) as exc:
        latencia_ms = round((time.perf_counter() - inicio) * 1000, 4)
        return None, {
            "modelo": modelo,
            "status_http": None,
            "latencia_ms": latencia_ms,
            "tokens_prompt": None,
            "tokens_resposta": None,
            "eval_duration_ms": None,
            "done_reason": None,
            "erro": f"{type(exc).__name__}: {exc}",
        }


def chamar_ollama_com_fallback(prompt: str) -> tuple[str, dict]:
    """Executa o 'qwen2.5:7b' com fallback seguro para 'qwen2.5:3b'.

    Retorna (texto_gerado, telemetria_agregada). Se ambos falharem, levanta
    RuntimeError — o nó captura a exceção e degrada graciosamente.
    """
    tentativas: list[dict] = []
    for modelo in (MODELO_PRINCIPAL, MODELO_FALLBACK):
        texto, telemetria = _chamar_modelo(modelo, prompt)
        telemetria = dict(telemetria)
        telemetria["fallback_usado"] = modelo != MODELO_PRINCIPAL
        tentativas.append(telemetria)
        if texto:
            # Cópias independentes (evita referência circular ao serializar)
            telemetria["tentativas"] = [dict(t) for t in tentativas]
            return texto, telemetria

    erros = "; ".join(
        f"{t['modelo']}: {t['erro']}" for t in tentativas if t.get("erro")
    )
    raise RuntimeError(f"Todos os modelos Ollama falharam. {erros}")


def nodo_mapeador(state: CortexState) -> dict:
    """Executa o Agente 1 (Mapeador Estrutural) sobre o CortexState.

    Retorna a atualização parcial do estado:
        {"analise_mapeador": str, "contexto_rag": list, "erros": list}
    E registra a telemetria completa em Metrics/metrics_agente1_v2.json.
    """
    inicio_nodo = time.perf_counter()
    estado = dict(state)
    entrada_bruta = str(estado.get("entrada_bruta", "")).strip()
    frente_alvo = (
        str(estado.get("frente_alvo", "LAB / GERAL")).strip() or "LAB / GERAL"
    )

    agora = _agora()
    reporte: dict = {
        "proyecto": "RS4-cortex-flow v2 (Cortex-Flow V2)",
        "dose": "Dose 2 (Fase 2) - Nó Agente 1 (Mapeador Estrutural)",
        "regla": "Regla CEO RS4 - Telemetria de nó LangGraph",
        "descripcion": (
            "Nó Agente 1: RAG no ChromaDB (coleção 'decisoes') + prompt do "
            "Mapeador Estrutural + Ollama local (qwen2.5:7b, fallback qwen2.5:3b)."
        ),
        "fecha_hora": agora.strftime("%Y-%m-%d %H:%M:%S"),
        "fecha_hora_iso": agora.isoformat(timespec="seconds"),
        "ambiente": {
            "python": platform.python_version(),
            "chromadb_version": chromadb.__version__,
            "plataforma": platform.platform(),
            "workdir": str(DIR_RAIZ),
        },
        "entrada": {
            "frente_alvo": frente_alvo,
            "entrada_bruta_caracteres": len(entrada_bruta),
            "entrada_bruta_preview": entrada_bruta[:200],
        },
        "rag_chromadb": {},
        "prompt_agente1": {},
        "ollama": {},
        "nodo": {},
        "erros": list(estado.get("erros") or []),
        "validacion": {},
    }

    # (a) RAG — consulta da coleção 'decisoes' no ChromaDB
    rag = recuperar_contexto_rag(entrada_bruta)
    reporte["rag_chromadb"] = rag
    contexto_rag: list = rag.get("hits") or []
    if rag.get("status") != "OK":
        reporte["erros"].append(f"RAG: {rag.get('erro')}")

    # (b) Prompt do Agente 1 (Mapeador Estrutural)
    try:
        regras = cargar_reglas_agente1()
    except Exception as exc:
        regras = (
            "Você é o AGENTE 1 — Mapeador e Analista Estrutural do "
            "RS4-cortex-flow."
        )
        reporte["erros"].append(f"PROMPT_RULES: {type(exc).__name__}: {exc}")
    prompt = montar_prompt_agente1(regras, entrada_bruta, rag)
    reporte["prompt_agente1"] = {
        "fonte_regras": str(CAMINHO_PROMPT_AGENTE1),
        "caracteres_prompt": len(prompt),
        "preview": prompt[:300],
    }

    # (c) Chamada local ao Ollama (qwen2.5:7b com fallback seguro p/ qwen2.5:3b)
    try:
        analise_mapeador, tele_ollama = chamar_ollama_com_fallback(prompt)
        tele_ollama = dict(tele_ollama)
        tele_ollama["url_api_generate"] = OLLAMA_API_GENERATE
        tele_ollama["temperatura"] = TEMPERATURA
        tele_ollama["num_predict"] = NUM_PREDICT
        reporte["ollama"] = tele_ollama
        estado_nodo = "OK"
    except Exception as exc:
        reporte["erros"].append(f"OLLAMA: {type(exc).__name__}: {exc}")
        reporte["ollama"] = {
            "modelo": None,
            "url_api_generate": OLLAMA_API_GENERATE,
            "temperatura": TEMPERATURA,
            "num_predict": NUM_PREDICT,
            "erro": f"{type(exc).__name__}: {exc}",
        }
        analise_mapeador = (
            "[ERRO OLLAMA] O Agente 1 não obteve resposta do modelo local — "
            f"sem análise estrutural. Detalhe: {exc}"
        )
        estado_nodo = "ERRO_OLLAMA"

    duracao_nodo_ms = round((time.perf_counter() - inicio_nodo) * 1000, 4)
    reporte["nodo"] = {
        "funcao": "nodo_mapeador",
        "assinatura": "nodo_mapeador(state: CortexState) -> dict",
        "duracao_total_ms": duracao_nodo_ms,
        "analise_mapeador_caracteres": len(analise_mapeador),
        "analise_mapeador_preview": analise_mapeador[:300],
        "contexto_rag_total": len(contexto_rag),
        "estado": estado_nodo,
    }

    # Telemetria/validação (Regra CEO RS4)
    try:
        py_compile.compile(__file__, doraise=True)
        ok_sintaxe = True
    except py_compile.PyCompileError as exc:
        ok_sintaxe = False
        reporte["erros"].append(f"PY_COMPILE: {exc}")

    sucesso = estado_nodo == "OK" and ok_sintaxe
    reporte["validacion"] = {
        "py_compile_mapeador": "OK" if ok_sintaxe else "ERRO",
        "nodo_estado": estado_nodo,
        "status": "SUCCESS" if sucesso else "FAILURE",
        "exit_code": 0 if sucesso else 1,
    }

    try:
        RUTA_METRICS_AGENTE1.parent.mkdir(parents=True, exist_ok=True)
        RUTA_METRICS_AGENTE1.write_text(
            json.dumps(reporte, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except (OSError, TypeError, ValueError) as exc:
        reporte["erros"].append(f"METRICS_WRITE: {exc}")

    return {
        "analise_mapeador": analise_mapeador,
        "contexto_rag": contexto_rag,
        "erros": reporte["erros"],
    }


def _main_demo() -> int:
    """Executa o nó com um estado fictício (uso manual / demonstração)."""
    try:
        import sys as _sys

        _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    demo: CortexState = {
        "entrada_bruta": (
            "Ideia: plataforma de micro-saúde laboratorial para clínicas "
            "populares. Frente Alvo: [X] LAB | [ ] COMMERCE | [ ] GERAL. "
            "Objetivo: reduzir custo de exames de rotina com automação."
        ),
        "frente_alvo": "LAB / GERAL",
        "analise_mapeador": "",
        "analise_techscout": "",
        "analise_critico": "",
        "sintese_final": "",
        "contexto_rag": [],
        "erros": [],
    }
    resultado = nodo_mapeador(demo)
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    return 0 if resultado.get("analise_mapeador") else 1


if __name__ == "__main__":
    raise SystemExit(_main_demo())