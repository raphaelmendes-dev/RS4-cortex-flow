# -*- coding: utf-8 -*-
"""Nó Agente 3 (Crítico Ácido de Engenharia) — Cortex-Flow V2 (Dose 2 / Fase 2 — Item 08.4).

Nó LangGraph-ready que produz um parecer de auditoria cética, fria e cirúrgica
a partir do CortexState produzido pelos nós anteriores:

  a) Rescata o material a auditar do estado ('analise_mapeador',
     'analise_techscout' o 'copy_comercial' — prioridade à entrega mais recente
     disponível no fluxo: copy_comercial > analise_techscout > analise_mapeador).
  b) Consulta a coleção 'decisoes' no ChromaDB com base nesse material e
     recupera o DNA da Filosofia RS4 (reglas de governo, checklist vivos,
     criterios de éxito, proteções) como marco de auditoria (RAG).
  c) Monta o prompt do Crítico Ácido (agentes/agente3_critico.txt): análise
     cética, fria e cirúrgica sobre riscos, furos de lógica e complexidade
     desnecessária.
  d) Executa a chamada local ao Ollama ('qwen2.5:7b' com fallback seguro
     para 'qwen2.5:3b'), temperature=0.2, num_predict=1024.
  e) Retorna o parecer na chave 'analise_critico' do estado.

Telemetria (Regla CEO RS4): mede a latência exata do ChromaDB e do Ollama e
grava o resultado completo da execução em Metrics/metrics_critico_v2.json
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
MODELO_PRINCIPAL = "qwen2.5:7b"  # preferido: crítico ácido rápido e direto
MODELO_FALLBACK = "qwen2.5:3b"
MODELO_FALLBACKS = (MODELO_FALLBACK,)
TEMPERATURA = 0.2  # análise fria/cirúrgica: criatividade contida
NUM_PREDICT = 1024  # parecer estruturado e ágil na CPU local
TIMEOUT_OLLAMA_S = 240
N_RESULTADOS_RAG = 3

DIR_RAIZ = Path(__file__).resolve().parents[2]
CHROMA_DATA_DIR_ABSOLUTO = str(DIR_RAIZ / "chroma_db_data")
CAMINHO_PROMPT_AGENTE3 = DIR_RAIZ / "agentes" / "agente3_critico.txt"
RUTA_METRICS_CRITICO = DIR_RAIZ / "Metrics" / "metrics_critico_v2.json"
OLLAMA_API_GENERATE = f"{OLLAMA_BASE_URL}/api/generate"

# Chaves de estado consultadas pelo nó, na ordem de prioridade do material
# a auditar (a entrega mais recente do fluxo define o objeto da auditoria).
CHAVES_MATERIAL: tuple[str, ...] = ("copy_comercial", "analise_techscout", "analise_mapeador")

# Reglas embutidas (fallback) caso o prompt de 'agentes/agente3_critico.txt'
# não possa ser lido — o fluxo degrada graciosamente sem abortar o grafo.
REGRAS_CRITICO = (
    "Você é o AGENTE 3 — O Crítico Ácido de Engenharia do RS4-cortex-flow.\n"
    "Sua função é atuar como um revisor implacável para encontrar furos de lógica e riscos.\n"
    "DIRETRIZES:\n"
    "1. Esqueça elogios ou polidez. Seja direto, técnico e rigoroso.\n"
    "2. Identifique onde há complexidade prematura, gargalos de performance, "
    "riscos de execução ou premissas falsas.\n"
    "3. Aponte onde o operador humano está sendo otimista demais ou onde o "
    "projeto pode falhar no uso diário.\n"
    "4. Pergunte: 'Isso realmente resolve o problema da forma mais simples "
    "possível ou é perfumaria?'.\n"
    "5. Alinhe cada achado com o DNA da Filosofia RS4 (contexto RAG): reglas "
    "de governo, checklist vivos, critérios de éxito y protecciones.\n"
    "6. Conclua com um VEREDICTO final: APROVADO, APROVADO CON RESERVAS ou "
    "RECHAZADO.\n"
)


def _agora() -> datetime.datetime:
    """Timestamp ISO/legível para la telemetria."""
    return datetime.datetime.now()


def cargar_reglas_agente3() -> str:
    """Lê e retorna as reglas do prompt do Agente 3 (Crítico Ácido)."""
    if not CAMINHO_PROMPT_AGENTE3.exists():
        raise FileNotFoundError(
            f"Prompt do Agente 3 não encontrado: {CAMINHO_PROMPT_AGENTE3}"
        )
    return CAMINHO_PROMPT_AGENTE3.read_text(encoding="utf-8").strip()


def extraer_material_critica(
    state: dict, max_caracteres: int = 5000
) -> tuple[str, str]:
    """Rescata do CortexState o material a auditar e a chave de origem.

    Prioridad da entrega (a mais recente do fluxo):
      copy_comercial > analise_techscout > analise_mapeador.
    Se nenhuna está presente, usa 'entrada_bruta'. Antepone, quando
    disponíveis e não duplicadas, a 'entrada_bruta' e a 'analise_mapeador'
    como contexto, para que a auditoria tenha o quadro completo.

    Retorna (material, fuente). La fuente é a chave que aporta a proposta
    a auditar.
    """
    entrada_bruta = str(state.get("entrada_bruta") or "").strip()
    analise_mapeador = str(state.get("analise_mapeador") or "").strip()

    fuente = ""
    material_entrega = ""
    for chave in CHAVES_MATERIAL:
        valor = str(state.get(chave) or "").strip()
        if valor:
            fuente = chave
            material_entrega = valor
            break
    if not material_entrega:
        fuente = "entrada_bruta"
        material_entrega = entrada_bruta

    partes: list[str] = []
    # Contexto: pedido original (si no es el propio material a auditar).
    if entrada_bruta and fuente != "entrada_bruta":
        partes.append(f"ENTRADA BRUTA (pedido original):\n{entrada_bruta}")
    # Contexto: análise estrutural do Mapeador (si no es el propio material).
    if (
        analise_mapeador
        and fuente != "analise_mapeador"
        and analise_mapeador not in material_entrega
    ):
        partes.append(
            f"ANÁLISE DO MAPEADOR (contexto estrutural):\n{analise_mapeador}"
        )
    partes.append(f"PROPUESTA A AUDITAR (fuente: {fuente}):\n{material_entrega}")

    material = "\n\n".join(partes).strip()
    if len(material) > max_caracteres:
        material = material[:max_caracteres]
    return material, fuente
def recuperar_contexto_rag(
    material: str, n_resultados: int = N_RESULTADOS_RAG
) -> dict:
    """Consulta a coleção 'decisoes' no ChromaDB e mede a latência exata.

    La query combina o material com um reforço de intenção para resgatar o DNA
    da Filosofia RS4 (reglas de governo, checklist vivos, critérios de éxito,
    proteções) como marco de auditoria. Em caso de falha não levanta exceção:
    devolve status 'ERROR' para que o nó continue com contexto RAG vazio
    (degradação graciosa, sem abortar o grafo).
    """
    query = (
        f"{material}\nFilosofía RS4 e reglas de gobierno: resgatar do DNA "
        "filosófico as reglas do CEO RS4MACHINE, checklist vivos, pilares de "
        "segurança, escalabilidade, critérios de éxito e proteções para "
        "auditar críticamente esta proposta."
    )
    inicio = time.perf_counter()
    try:
        cliente = crear_cliente_chroma(CHROMA_DATA_DIR_ABSOLUTO)
        coleccion = garantizar_coleccion_decisoes(cliente)
        resultado = coleccion.query(query_texts=[query], n_results=n_resultados)
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


def montar_prompt_critico(
    reglas: str, material: str, fuente: str, rag: dict
) -> str:
    """Monta o prompt do Crítico Ácido: reglas + material + DNA RS4 (RAG)."""
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
            "  Nenhum antecedente/decisão do DNA encontrado na base ChromaDB "
            "para esta auditoria."
        )

    return (
        "SYSTEM — AGENTE 3 (CRÍTICO ÁCIDO DE ENGENHARIA):\n"
        f"{reglas}\n\n"
        "MATERIAL A AUDITAR:\n"
        f"{material}\n\n"
        "CONTEXTO RAG — DNA DA FILOSOFÍA RS4 (MARCO DE AUDITORIA — CHROMADB):\n"
        f"{contexto_rag}\n\n"
        "INSTRUÇÕES DE SAÍDA:\n"
        "1. Seja cético, frio e cirúrgico: vaya ao que dói, sem cortesía.\n"
        "2. Estruture o parecer em seções claras:\n"
        "   [1] VEREDICTO\n"
        "   [2] RISCOS (cada uno com severidade ALTA/MEDIA/BAJA)\n"
        "   [3] FUROS DE LÓGICA / PREMISAS FALSAS\n"
        "   [4] COMPLEXIDADE DESNECESARIA / PERFUMERÍA\n"
        "   [5] ALINEAMIENTO COM EL DNA RS4 (RAG)\n"
        "   [6] RECOMENDACIONES (solo o imprescindible para aprobar)\n"
        "3. Não repita o texto entrado: analice y critique.\n"
        "4. Conclua com VEREDICTO final: APROVADO | APROVADO CON RESERVAS | "
        "RECHAZADO."
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
    """Executa 'qwen2.5:7b' com fallback seguro para 'qwen2.5:3b'.

    Retorna (texto_gerado, telemetria_agregada). Se todos falharem, levanta
    RuntimeError — o nó captura a exceção e degrada graciosamente.
    """
    tentativas: list[dict] = []
    for modelo in (MODELO_PRINCIPAL, *MODELO_FALLBACKS):
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


def nodo_critico(state: CortexState) -> dict:
    """Executa o Agente 3 (Crítico Ácido) sobre o CortexState.

    Fluxo:
      a) extrae o material a auditar do estado ('analise_mapeador',
         'analise_techscout' o 'copy_comercial');
      b) RAG no ChromaDB (coleção 'decisoes') — DNA da Filosofia RS4;
      c) prompt do Crítico Ácido + material + contexto RAG;
      d) Ollama local ('qwen2.5:7b', fallback 'qwen2.5:3b')
         genera o parecer cético/frio/cirúrgico;
      e) estado atualizado com 'analise_critico' e 'contexto_rag'.

    Retorna a atualização parcial do estado:
        {"analise_critico": str, "contexto_rag": list, "erros": list}
    E registra a telemetria completa em Metrics/metrics_critico_v2.json
    (tempo, status, exit_code).
    """
    inicio_nodo = time.perf_counter()
    estado = dict(state)
    frente_alvo = str(estado.get("frente_alvo", "GERAL")).strip() or "GERAL"

    agora = _agora()
    reporte: dict = {
        "proyecto": "RS4-cortex-flow v2 (Cortex-Flow V2)",
        "dose": "Dose 2 (Fase 2) - Nó Agente 3 (Crítico Ácido) — Item 08.4",
        "regla": "Regla CEO RS4 - Telemetria de nó LangGraph",
        "descripcion": (
            "Nó Agente 3: auditoria cética/fria/cirúrgica sobre o material do "
            "estado (analise_mapeador, analise_techscout ou copy_comercial) "
            "+ RAG no ChromaDB (coleção 'decisoes' → DNA da Filosofia RS4) + "
            "Ollama local (qwen2.5:7b, fallback qwen2.5:3b)."
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
            "estado_caracteres": sum(
                len(str(v or "")) for k, v in estado.items() if k != "erros"
            ),
            "chaves_disponibles": [k for k, v in estado.items() if str(v or "").strip()],
        },
        "rag_chromadb": {},
        "prompt_critico": {},
        "ollama": {},
        "nodo": {},
        "erros": list(estado.get("erros") or []),
        "validacion": {},
    }

    # (a) Material a auditar — a entrega mais recente do estado
    material, fuente = extraer_material_critica(estado)
    reporte["entrada"]["material_caracteres"] = len(material)
    reporte["entrada"]["material_preview"] = material[:300]
    reporte["entrada"]["fuente_material"] = fuente

    # (b) RAG — DNA da Filosofia RS4 (coleção 'decisoes')
    rag = recuperar_contexto_rag(material)
    reporte["rag_chromadb"] = rag
    contexto_rag: list = rag.get("hits") or []
    if rag.get("status") != "OK":
        reporte["erros"].append(f"RAG: {rag.get('erro')}")

    # (c) Prompt do Agente 3 (Crítico Ácido)
    try:
        reglas = cargar_reglas_agente3()
    except Exception as exc:
        reglas = REGRAS_CRITICO
        reporte["erros"].append(f"PROMPT_RULES: {type(exc).__name__}: {exc}")
    prompt = montar_prompt_critico(reglas, material, fuente, rag)
    reporte["prompt_critico"] = {
        "fonte_regras": str(CAMINHO_PROMPT_AGENTE3),
        "caracteres_prompt": len(prompt),
        "preview": prompt[:300],
    }

    # (d) Chamada local ao Ollama (qwen2.5:7b com fallback seguro)
    try:
        analise_critico, tele_ollama = chamar_ollama_com_fallback(prompt)
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
        analise_critico = (
            "[ERRO OLLAMA] O Agente 3 não obtuvo resposta do modelo local — "
            f"sem parecer crítico. Detalhe: {exc}"
        )
        estado_nodo = "ERRO_OLLAMA"

    duracao_nodo_ms = round((time.perf_counter() - inicio_nodo) * 1000, 4)
    reporte["nodo"] = {
        "funcao": "nodo_critico",
        "assinatura": "nodo_critico(state: CortexState) -> dict",
        "duracao_total_ms": duracao_nodo_ms,
        "fuente_material": fuente,
        "analise_critico_caracteres": len(analise_critico),
        "analise_critico_preview": analise_critico[:300],
        "contexto_rag_total": len(contexto_rag),
        "estado": estado_nodo,
    }

    # Telemetria/validação (Regla CEO RS4)
    try:
        py_compile.compile(__file__, doraise=True)
        ok_sintaxe = True
    except py_compile.PyCompileError as exc:
        ok_sintaxe = False
        reporte["erros"].append(f"PY_COMPILE: {exc}")

    sucesso = (
        estado_nodo == "OK"
        and ok_sintaxe
        and bool(analise_critico.strip())
    )
    reporte["validacion"] = {
        "py_compile_critico": "OK" if ok_sintaxe else "ERRO",
        "nodo_estado": estado_nodo,
        "status": "SUCCESS" if sucesso else "FAILURE",
        "exit_code": 0 if sucesso else 1,
    }

    try:
        RUTA_METRICS_CRITICO.parent.mkdir(parents=True, exist_ok=True)
        RUTA_METRICS_CRITICO.write_text(
            json.dumps(reporte, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except (OSError, TypeError, ValueError) as exc:
        reporte["erros"].append(f"METRICS_WRITE: {exc}")

    return {
        "analise_critico": analise_critico,
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
            "Ideia: API Python simples — CRUD de tarefas com SQLite, sem custo "
            "de hospedagem, usando apenas ferramentas open-source."
        ),
        "frente_alvo": "GERAL",
        "analise_mapeador": (
            "ANÁLISE DO AGENTE 1 — Mapeador e Analista Estrutural\n\n"
            "**FATOS:**\n- O usuário quer criar uma API Python simples do tipo CRUD.\n"
            "- O ambiente alvo é local/desktop, com custo R$ 0,00.\n"
            "- O banco de dados será SQLite (arquivo local, sem servidor).\n\n"
            "**PROBLEMA CENTRAL:**\n- Escolher a menor stack confiável e gratuita "
            "para entregar uma API Python CRUD com SQLite em ambiente local."
        ),
        "analise_techscout": (
            "**RELATÓRIO TÉCNICO ENXUTO — AGENTE 2 (TECH SCOUT)**\n\n"
            "Stack recomendada: Python 3.11+ com FastAPI + Uvicorn, SQLite, "
            "pytest e documentação com docstrings. Alternativas: Flask e "
            "sqlite3 nativo. Arquitectura monolítica simples para a v1."
        ),
        "analise_critico": "",
        "sintese_final": "",
        "contexto_rag": [],
        "erros": [],
    }
    resultado = nodo_critico(demo)
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    return 0 if resultado.get("analise_critico") else 1


if __name__ == "__main__":
    raise SystemExit(_main_demo())