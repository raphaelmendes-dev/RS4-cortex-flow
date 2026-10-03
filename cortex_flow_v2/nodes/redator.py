# -*- coding: utf-8 -*-
"""Nó Agente Redator Comercial — Cortex-Flow V2 (Dose 2 / Fase 2 — Item 08.2).

Nó LangGraph-ready que gera copy comercial/anúncio a partir do CortexState:

  a) RAG no ChromaDB (coleção 'decisoes'): resgata os tons e regras de ofertas
     salvos no DNA (seed_dna.py / filosofia_rs4.txt) similares à oferta.
  b) Monta o prompt do Agente Redator Comercial: regras de copywriting +
     entrada_bruta (oferta a anunciar) + contexto RAG de tons/regras.
  c) Executa a chamada local ao Ollama ('qwen2.5:7b' com fallback seguro para
     'qwen2.5:3b'), temperature=0.7, num_predict=1024 (copy criativa e completa).
  d) Salva a copy gerada em 'drafts/ofertas/' em formato Markdown com carimbo
     de data/hora no nome do arquivo (ex.: oferta_20260927_113000.md).

Telemetria (Regra CEO RS4): mede a latência exata do ChromaDB e do Ollama e
grava o resultado completo da execução em Metrics/metrics_redator_v2.json
(tempo, status, exit_code).
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
TEMPERATURA = 0.7  # copy comercial: criatividade controlada
NUM_PREDICT = 1024  # copy completa (headline + corpo + CTA)
TIMEOUT_OLLAMA_S = 240
N_RESULTADOS_RAG = 3

DIR_RAIZ = Path(__file__).resolve().parents[2]
CHROMA_DATA_DIR_ABSOLUTO = str(DIR_RAIZ / "chroma_db_data")
DIR_RAFTS_OFERTAS = DIR_RAIZ / "drafts" / "ofertas"
RUTA_METRICS_REDATOR = DIR_RAIZ / "Metrics" / "metrics_redator_v2.json"
OLLAMA_API_GENERATE = f"{OLLAMA_BASE_URL}/api/generate"

# Regras do Agente Redator Comercial (sistema embutido no nó; os tons e regras
# de ofertas são resgatados dinamicamente do DNA via RAG no ChromaDB).
REGRAS_REDATOR = (
    "Você é o AGENTE REDATOR COMERCIAL do RS4-cortex-flow.\n"
    "Sua função é transformar uma oferta/ideia bruta em uma copy comercial "
    "persuasiva e em um anúncio pronto para publicação.\n"
    "DIRETRIZES:\n"
    "1. Escreva em português do Brasil, com tom direto, claro e persuasivo, "
    "sem enrolação.\n"
    "2. Estruture o anúncio em: headline, subheadline, corpo (3 a 5 benefícios "
    "concretos), prova/credibilidade (se houver dados) e call to action (CTA) "
    "único e direto.\n"
    "3. Respeite os tons e regras de ofertas resgatados do DNA (contexto RAG): "
    "siga o tom indicado, evite promessas exageradas e mantenha a "
    "responsabilidade construtiva.\n"
    "4. Mantenha a copy com extensão de anúncio (150 a 350 palavras) e "
    "finalize sempre com um CTA claro.\n"
    "5. Não invente números, depoimentos ou estatísticas que não estejam na "
    "entrada ou no contexto RAG."
)


def _agora() -> datetime.datetime:
    """Timestamp ISO/legível para a telemetria."""
    return datetime.datetime.now()


def recuperar_contexto_rag(
    entrada_bruta: str, n_resultados: int = N_RESULTADOS_RAG
) -> dict:
    """Consulta a coleção 'decisoes' no ChromaDB e mede a latência exata.

    A query é a oferta + um reforço de intenção para resgatar os tons e regras
    de ofertas salvos no DNA. Em caso de falha não levanta exceção: devolve
    status 'ERROR' para que o nó continue com contexto RAG vazio (degradação
    graciosa, sem abortar o grafo).
    """
    query = (
        f"{entrada_bruta}\nRegras de ofertas: resgatar tons de voz, tom "
        "persuasivo e regras de copywriting salvos no DNA para redação "
        "comercial."
    )
    inicio = time.perf_counter()
    try:
        cliente = crear_cliente_chroma(CHROMA_DATA_DIR_ABSOLUTO)
        coleccion = garantizar_coleccion_decisoes(cliente)
        resultado = coleccion.query(
            query_texts=[query], n_results=n_resultados
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
            "query_preview": query[:180],
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
            "query_preview": query[:180],
            "n_resultados_requeridos": n_resultados,
            "total_resultados": 0,
            "hits": [],
            "latencia_ms": latencia_ms,
            "status": "ERROR",
            "erro": f"{type(exc).__name__}: {exc}",
        }


def montar_prompt_redator(
    regras: str, entrada_bruta: str, frente_alvo: str, rag: dict
) -> str:
    """Monta o prompt do Redator Comercial: regras + oferta + contexto RAG."""
    hits = rag.get("hits") or []
    if hits:
        linhas = []
        for i, hit in enumerate(hits, 1):
            dist = hit.get("distancia")
            dist_str = f" (distância={dist})" if dist is not None else ""
            texto_doc = str(hit.get("documento") or "")[:500]
            linhas.append(f"  [{i}] {texto_doc}{dist_str}")
        contexto_rag = "\n".join(linhas)
    else:
        contexto_rag = (
            "  Nenhum tom/regra de oferta similar encontrado na base ChromaDB "
            "para esta oferta. Use as regras gerais do sistema."
        )

    return (
        "SYSTEM — AGENTE REDATOR COMERCIAL:\n"
        f"{regras}\n\n"
        "FRENTE ALVO:\n"
        f"{frente_alvo}\n\n"
        "OFERTA A ANUNCIAR (entrada_bruta):\n"
        f"{entrada_bruta}\n\n"
        "CONTEXTO RAG — TONS E REGRAS DE OFERTAS SALVOS NO DNA (CHROMADB):\n"
        f"{contexto_rag}\n\n"
        "INSTRUÇÃO DE SAÍDA:\n"
        "Produza a copy comercial completa (headline + subheadline + corpo + "
        "CTA) em Markdown, seguindo as diretrizes acima. Seja direto, "
        "persuasivo e finalize com um CTA único."
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


def _nome_arquivo_copy(agora: datetime.datetime) -> str:
    """Nome do arquivo Markdown com carimbo de data/hora.

    Ex.: oferta_20260927_113000.md
    """
    return f"oferta_{agora.strftime('%Y%m%d_%H%M%S')}.md"


def _normalizar_copy(copy: str) -> str:
    """Limpa a copy gerada: remove code fences acidentais (```markdown ... ```).

    Modelos frequentemente envolvem a resposta em blocos de código (linhas
    de abertura e fechamento ```). Sem a limpeza, o arquivo Markdown final
    renderizaria blocos de código dentro da copy. Remove qualquer linha-fence
    em qualquer posição do texto.
    """
    texto = (copy or "").strip()
    if not texto:
        return ""
    linhas_filtradas = [
        linha
        for linha in texto.splitlines()
        if not linha.strip().startswith("```")
    ]
    return "\n".join(linhas_filtradas).strip()


def salvar_copy_markdown(
    copy_comercial: str,
    entrada_bruta: str,
    frente_alvo: str,
    modelo_usado: str,
    agora: datetime.datetime,
) -> str:
    """Salva a copy gerada em 'drafts/ofertas/' em formato Markdown.

    O nome do arquivo carrega o carimbo de data/hora e o conteúdo traz um
    cabeçalho com metadados rastreáveis (agente, frente, data, modelo).
    Retorna o caminho absoluto do arquivo gerado.
    """
    DIR_RAFTS_OFERTAS.mkdir(parents=True, exist_ok=True)
    caminho = DIR_RAFTS_OFERTAS / _nome_arquivo_copy(agora)

    cabecalho = (
        "---\n"
        "titulo: Copy Comercial — RS4 Cortex-Flow V2\n"
        "agente: Redator Comercial (Item 08.2)\n"
        f"frente_alvo: {frente_alvo}\n"
        f"criado_em: {agora.isoformat(timespec='seconds')}\n"
        f"modelo: {modelo_usado}\n"
        "---\n\n"
        "# COPY COMERCIAL / ANÚNCIO\n\n"
        "## Oferta (entrada_bruta)\n\n"
        f"{entrada_bruta}\n\n"
        "## Copy gerada\n\n"
        f"{copy_comercial}\n"
    )
    caminho.write_text(cabecalho, encoding="utf-8")
    return str(caminho)


def nodo_redator(state: CortexState) -> dict:
    """Executa o Agente Redator Comercial sobre o CortexState.

    Fluxo:
      a) RAG no ChromaDB (coleção 'decisoes') — resgata tons/regras do DNA;
      b) prompt do Redator + entrada_bruta + contexto RAG;
      c) Ollama local ('qwen2.5:7b', fallback 'qwen2.5:3b') gera a copy;
      d) copy salva em 'drafts/ofertas/' (Markdown com carimbo de data/hora).

    Retorna a atualização parcial do estado:
        {"copy_comercial": str, "contexto_rag": list,
         "caminho_copy_md": str, "erros": list}
    E registra a telemetria completa em Metrics/metrics_redator_v2.json
    (tempo, status, exit_code).
    """
    inicio_nodo = time.perf_counter()
    estado = dict(state)
    entrada_bruta = str(estado.get("entrada_bruta", "")).strip()
    frente_alvo = str(estado.get("frente_alvo", "COPY_OFFER")).strip()
    if not frente_alvo:
        frente_alvo = "COPY_OFFER"

    agora = _agora()
    reporte: dict = {
        "proyecto": "RS4-cortex-flow v2 (Cortex-Flow V2)",
        "dose": "Dose 2 (Fase 2) - Nó Agente Redator Comercial (Item 08.2)",
        "regla": "Regla CEO RS4 - Telemetria de nó LangGraph",
        "descripcion": (
            "Nó Agente Redator Comercial: RAG no ChromaDB (coleção 'decisoes') "
            "para resgatar tons e regras de ofertas do DNA + prompt do Redator "
            "+ Ollama local (qwen2.5:7b, fallback qwen2.5:3b) + copy salva em "
            "drafts/ofertas/ (Markdown com carimbo de data/hora)."
        ),
        "fecha_hora": agora.strftime("%Y-%m-%d %H:%M:%S"),
        "fecha_hora_iso": agora.isoformat(timespec="seconds"),
        "ambiente": {
            "python": platform.python_version(),
            "chromadb_version": chromadb.__version__,
            "plataforma": platform.platform(),
            "maquina": socket.gethostname(),
            "workdir": str(DIR_RAIZ),
        },
        "entrada": {
            "frente_alvo": frente_alvo,
            "entrada_bruta_caracteres": len(entrada_bruta),
            "entrada_bruta_preview": entrada_bruta[:200],
        },
        "rag_chromadb": {},
        "prompt_redator": {},
        "ollama": {},
        "copy_draft": {},
        "nodo": {},
        "erros": list(estado.get("erros") or []),
        "validacion": {},
    }

    # (a) RAG — tons e regras de ofertas salvos no DNA (coleção 'decisoes')
    rag = recuperar_contexto_rag(entrada_bruta)
    reporte["rag_chromadb"] = rag
    contexto_rag: list = rag.get("hits") or []
    if rag.get("status") != "OK":
        reporte["erros"].append(f"RAG: {rag.get('erro')}")

    # (b) Prompt do Agente Redator Comercial
    prompt = montar_prompt_redator(REGRAS_REDATOR, entrada_bruta, frente_alvo, rag)
    reporte["prompt_redator"] = {
        "fonte_regras": (
            "embutidas no nó (REGRAS_REDATOR) + tons/regras do DNA via RAG"
        ),
        "caracteres_prompt": len(prompt),
        "preview": prompt[:300],
    }

    # (c) Chamada local ao Ollama (qwen2.5:7b com fallback seguro p/ qwen2.5:3b)
    try:
        copy_comercial, tele_ollama = chamar_ollama_com_fallback(prompt)
        copy_comercial = _normalizar_copy(copy_comercial) or "⚠ Vazio"
        tele_ollama = dict(tele_ollama)
        tele_ollama["url_api_generate"] = OLLAMA_API_GENERATE
        tele_ollama["temperatura"] = TEMPERATURA
        tele_ollama["num_predict"] = NUM_PREDICT
        reporte["ollama"] = tele_ollama
        estado_node = "OK"
    except Exception as exc:
        reporte["erros"].append(f"OLLAMA: {type(exc).__name__}: {exc}")
        reporte["ollama"] = {
            "modelo": None,
            "url_api_generate": OLLAMA_API_GENERATE,
            "temperatura": TEMPERATURA,
            "num_predict": NUM_PREDICT,
            "erro": f"{type(exc).__name__}: {exc}",
        }
        copy_comercial = (
            "[ERRO OLLAMA] O Redator Comercial não obteve resposta do modelo "
            f"local — sem copy comercial. Detalhe: {exc}"
        )
        estado_node = "ERRO_OLLAMA"

    # (d) Persistência da copy em drafts/ofertas/ (Markdown + carimbo de hora)
    caminho_copy_md = ""
    try:
        if estado_node == "OK":
            modelo_usado = str(tele_ollama.get("modelo") or MODELO_PRINCIPAL)
        else:
            modelo_usado = MODELO_PRINCIPAL
        caminho_copy_md = salvar_copy_markdown(
            copy_comercial, entrada_bruta, frente_alvo, modelo_usado, agora
        )
        reporte["copy_draft"] = {
            "diretorio": str(DIR_RAFTS_OFERTAS),
            "arquivo_markdown": Path(caminho_copy_md).name,
            "caminho_absoluto": caminho_copy_md,
            "carimbo_data_hora": _nome_arquivo_copy(agora),
            "copy_caracteres": len(copy_comercial),
            "status": "OK",
        }
    except (OSError, TypeError, ValueError) as exc:
        reporte["erros"].append(f"COPY_DRAFT: {type(exc).__name__}: {exc}")
        reporte["copy_draft"] = {
            "diretorio": str(DIR_RAFTS_OFERTAS),
            "status": "ERROR",
            "erro": f"{type(exc).__name__}: {exc}",
        }
        estado_node = "ERRO_DRAFT"

    duracao_nodo_ms = round((time.perf_counter() - inicio_nodo) * 1000, 4)
    reporte["nodo"] = {
        "funcao": "nodo_redator",
        "assinatura": "nodo_redator(state: CortexState) -> dict",
        "duracao_total_ms": duracao_nodo_ms,
        "copy_comercial_caracteres": len(copy_comercial),
        "copy_comercial_preview": copy_comercial[:300],
        "contexto_rag_total": len(contexto_rag),
        "estado": estado_node,
    }

    # Telemetria/validação (Regra CEO RS4)
    try:
        py_compile.compile(__file__, doraise=True)
        ok_sintaxe = True
    except py_compile.PyCompileError as exc:
        ok_sintaxe = False
        reporte["erros"].append(f"PY_COMPILE: {exc}")

    sucesso = estado_node == "OK" and ok_sintaxe
    reporte["validacion"] = {
        "py_compile_redator": "OK" if ok_sintaxe else "ERRO",
        "nodo_estado": estado_node,
        "status": "SUCCESS" if sucesso else "FAILURE",
        "exit_code": 0 if sucesso else 1,
    }

    try:
        RUTA_METRICS_REDATOR.parent.mkdir(parents=True, exist_ok=True)
        RUTA_METRICS_REDATOR.write_text(
            json.dumps(reporte, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except (OSError, TypeError, ValueError) as exc:
        reporte["erros"].append(f"METRICS_WRITE: {exc}")

    return {
        "copy_comercial": copy_comercial,
        "contexto_rag": contexto_rag,
        "caminho_copy_md": caminho_copy_md,
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
            "Ideia: anúncio de Commerce — campanha de email marketing para "
            "lançar uma oferta de R$ 99,00 na assinatura anual da plataforma "
            "de micro-saúde laboratorial, com copywriting persuasivo, landing "
            "page e call to action. Frente Alvo: [ ] LAB | [X] COMMERCE | "
            "[ ] GERAL. Objetivo: converter leads em assinantes com promoção."
        ),
        "frente_alvo": "COPY_OFFER",
        "analise_mapeador": "",
        "analise_techscout": "",
        "analise_critico": "",
        "sintese_final": "",
        "contexto_rag": [],
        "erros": [],
    }
    resultado = nodo_redator(demo)
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    if resultado.get("copy_comercial") and resultado.get("caminho_copy_md"):
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(_main_demo())