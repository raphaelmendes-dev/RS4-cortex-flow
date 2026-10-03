# -*- coding: utf-8 -*-
"""Nó Agente 2 (Tech Scout & Search Engine) — Cortex-Flow V2 (Dose 2 / Fase 2 — Item 08.3).

Nó LangGraph-ready que produz a análise técnica (stack R$ 0.00) a partir do
CortexState produzido pelo Mapeador:

  a) Consulta a coleção 'decisoes' no ChromaDB com base na 'analise_mapeador'
     e recupera antecedentes/decisões técnicas similares (RAG).
  b) Se o retorno do ChromaDB for insuficiente (nenhum hit ou menor que o
     limiar de semelhança), aciona uma busca leve na web via 'duckduckgo-search'
     (DDGS) por tecnologias open-source atuais.
  c) Executa a chamada local ao Ollama ('qwen2.5:7b' com fallback seguro para
     'qwen2.5:3b'), temperature=0.2, num_predict=1024 — sintetiza as fontes em
     um relatório técnico enxuto.
  d) Grava o novo relatório de volta no ChromaDB como uma nova memória/decisão
     (coleção 'decisoes', tipo 'dec_techscout', id determinístico por consulta)
     para evitar buscas futuras repetidas.
  e) Atualiza o estado retornando o texto em 'analise_techscout'.

Telemetria (Regra CEO RS4): mede a latência exata do ChromaDB, da busca web e
do Ollama e grava o resultado completo da execução em
Metrics/metrics_techscout_v2.json (incluindo se a busca web foi acionada).
"""

from __future__ import annotations

import datetime
import hashlib
import json
import platform
import py_compile
import re
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
TEMPERATURA = 0.2  # relatório técnico: criatividade contida
NUM_PREDICT = 1024  # relatório enxuto, porém técnico e completo
TIMEOUT_OLLAMA_S = 240
N_RESULTADOS_RAG = 3
N_RESULTADOS_WEB = 5
LIMIAR_SEMELHANCA = 0.5  # distância cosseno (nomic): acima => retorno insuficiente
REGIAO_WEB = "br-pt"
LIMITE_WEB_Y = "y"  # conteúdo do último ano (tendências atuais)

DIR_RAIZ = Path(__file__).resolve().parents[2]
CHROMA_DATA_DIR_ABSOLUTO = str(DIR_RAIZ / "chroma_db_data")
CAMINHO_PROMPT_AGENTE2 = DIR_RAIZ / "agentes" / "agente2_techscout.txt"
RUTA_METRICS_TECHSCOUT = DIR_RAIZ / "Metrics" / "metrics_techscout_v2.json"
OLLAMA_API_GENERATE = f"{OLLAMA_BASE_URL}/api/generate"

# Regras embutidas (fallback) caso o prompt de 'agentes/agente2_techscout.txt'
# não possa ser lido — o fluxo degrada graciosamente sem abortar o grafo.
REGRAS_TECHSCOUT = (
    "Você é o AGENTE 2 — Tech Scout e Especialista em Arquitetura do "
    "RS4-cortex-flow. Sua função é avaliar a viabilidade técnica e sugerir a "
    "melhor stack e boas práticas.\n"
    "DIRETRIZES:\n"
    "1. Com base na análise do Agente 1, mapeie as tecnologias mais adequadas "
    "(priorizando Python, SQLite, ferramentas locais e custo R$ 0,00).\n"
    "2. Avalie padrões de desenvolvimento e arquiteturas modernas "
    "(tendências e práticas de 2026).\n"
    "3. Mantenha a simplicidade: evite arquiteturas supercomplexas ou "
    "dependências desnecessárias para a v1.\n"
    "4. Apresente opções claras de implementação focando em eficiência local."
)


def _agora() -> datetime.datetime:
    """Timestamp ISO/legível para a telemetria."""
    return datetime.datetime.now()


def _versao_duckduckgo_search() -> str:
    """Versão instalada da biblioteca 'duckduckgo-search' (ou 'não instalada')."""
    try:
        from importlib import metadata

        return metadata.version("duckduckgo-search")
    except Exception:
        return "não instalada"


def cargar_reglas_agente2() -> str:
    """Lê e retorna as regras do prompt do Agente 2 (Tech Scout)."""
    if not CAMINHO_PROMPT_AGENTE2.exists():
        raise FileNotFoundError(
            f"Prompt do Agente 2 não encontrado: {CAMINHO_PROMPT_AGENTE2}"
        )
    return CAMINHO_PROMPT_AGENTE2.read_text(encoding="utf-8").strip()

def recuperar_contexto_rag(
    analise_mapeador: str, n_resultados: int = N_RESULTADOS_RAG
) -> dict:
    """Consulta a coleção 'decisoes' no ChromaDB e mede a latência exata.

    A query combina a análise do Mapeador com um reforço de intenção técnica
    para resgatar decisões sobre stack, ferramentas e arquitetura. Em caso de
    falha não levanta exceção: devolve status 'ERROR' para que o nó continue
    com RAG vazio e acione a busca web (degradação graciosa).
    """
    query = (
        f"{analise_mapeador}\nStack e tecnologias open-source R$ 0.00: resgatar "
        "decisões técnicas anteriores sobre ferramentas, arquitetura e boas "
        "práticas para avaliar a viabilidade do projeto."
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



def _eh_decisao_relevante(hit: dict) -> bool:
    """Indica se um hit do RAG é uma decisão técnica relevante p/ o Tech Scout.

    A coleção 'decisoes' mistura o DNA da filosofia (metadados tipo
    'dna_filosofia') com decisões técnicas reais (memórias 'dec_techscout',
    antecedentes 'decisao_*' ou documentos sem tipo). Apenas decisões técnicas
    relevantes devem evitar a busca web; filosofia não substitui stack.
    """
    meta = hit.get("metadata") or {}
    tipo = str(meta.get("tipo") or "")
    if not tipo:
        return True
    return "dna_" not in tipo


def rag_insuficiente(rag: dict) -> bool:
    """Heurística de suficiência do RAG.

    Retorna True (e portanto aciona a busca web) quando:
      1) a consulta ao ChromaDB falhou (status != 'OK');
      2) nenhum resultado foi devolvido;
      3) nenhum hit é uma 'decisão técnica relevante' (ex.: só filosofia do DNA);
      4) o hit relevante mais similar está acima do limiar (LIMIAR_SEMELHANCA).
    """
    if rag.get("status") != "OK":
        return True
    hits = rag.get("hits") or []
    if not hits:
        return True
    relevantes = [h for h in hits if _eh_decisao_relevante(h)]
    if not relevantes:
        return True
    distancias = [
        h.get("distancia")
        for h in relevantes
        if h.get("distancia") is not None
    ]
    if not distancias:
        return True
    return min(distancias) > LIMIAR_SEMELHANCA


def _limpar_consulta_web(texto: str, max_caracteres: int = 400) -> str:
    """Compacta a análise do Mapeador para usar como keywords da busca web.

    Remove artefatos de Markdown (**, #, -, colchetes) e colapsa espaços,
    mantendo um trecho curto e pesquisável.
    """
    if not texto:
        return ""
    limpo = texto.replace("*", " ").replace("#", " ")
    limpo = re.sub(r"[\[\]()_]", " ", limpo)
    limpo = re.sub(r"\s+", " ", limpo).strip()
    return limpo[:max_caracteres]


def buscar_web_duckduckgo(
    analise_mapeador: str,
    entrada_bruta: str = "",
    max_resultados: int = N_RESULTADOS_WEB,
) -> tuple[bool, list[dict], dict]:
    """Busca leve na web usando 'duckduckgo-search' (DDGS) e mede a latência.

    Prefere a 'entrada_bruta' como consulta (frase curta e pesquisável) e, se
    ausente, usa a análise do Mapeador compactada. Faz fallback de backend
    ('auto' -> 'html') quando o DDGS devolve vazio. Retorna
    (acionada, resultados, telemetria). Nunca levanta exceção: em caso de
    biblioteca ausente, rede fora ou rate-limit, devolve 'acionada=True' com
    'total_resultados=0' e o erro registrado na telemetria — o nó continua com
    contexto web vazio e degrada graciosamente.
    """
    base = (entrada_bruta or analise_mapeador).strip()
    consulta_web = _limpar_consulta_web(base)
    inicio = time.perf_counter()
    try:
        try:
            from duckduckgo_search import DDGS
        except ImportError:
            from ddgs import DDGS

        # Busca leve com fallback de backend: 'auto' primeiro; se o DDGS
        # devolver vazio (rate-limit/flakiness), tenta 'html' uma vez.
        registro_raw: list[dict] = []
        for backend in ("auto", "html"):
            with DDGS() as ddgs:
                tentativa = ddgs.text(
                    keywords=consulta_web,
                    region=REGIAO_WEB,
                    safesearch="moderate",
                    timelimit=LIMITE_WEB_Y,
                    backend=backend,
                    max_results=max_resultados,
                )
            if tentativa:
                registro_raw = tentativa
                break

        latencia_ms = round((time.perf_counter() - inicio) * 1000, 4)
        resultados: list[dict] = []
        for item in registro_raw or []:
            if not isinstance(item, dict):
                continue
            resultados.append(
                {
                    "titulo": str(item.get("title", ""))[:160],
                    "href": str(item.get("href", "")),
                    "corpo": str(item.get("body", ""))[:240],
                }
            )
        return True, resultados, {
            "acionada": True,
            "biblioteca": "duckduckgo-search",
            "consulta_web_preview": consulta_web[:160],
            "max_resultados_requeridos": max_resultados,
            "total_resultados": len(resultados),
            "resultados": resultados,
            "latencia_ms": latencia_ms,
            "status": "OK" if resultados else "SEM_RESULTADOS",
            "erro": None,
        }
    except Exception as exc:
        latencia_ms = round((time.perf_counter() - inicio) * 1000, 4)
        return True, [], {
            "acionada": True,
            "biblioteca": "duckduckgo-search",
            "consulta_web_preview": consulta_web[:160],
            "max_resultados_requeridos": max_resultados,
            "total_resultados": 0,
            "resultados": [],
            "latencia_ms": latencia_ms,
            "status": "ERROR",
            "erro": f"{type(exc).__name__}: {exc}",
        }


def gerar_id_memoria(analise_mapeador: str) -> str:
    """Id determinístico da memória do Tech Scout para uma dada análise.

    Mesma consulta => mesmo id => o upsert sobrescreve, evitando duplicatas e
    buscas futuras repetidas (idempotência).
    """
    chave = f"techscout:{analise_mapeador.strip()}"
    digest = hashlib.sha256(chave.encode("utf-8")).hexdigest()[:16]
    return f"techscout_{digest}"


def salvar_memoria_chromadb(
    relatorio: str,
    analise_mapeador: str,
    frente_alvo: str,
    origem: str,
    modelo_usado: str,
) -> dict:
    """Grava o relatório gerado de volta na coleção 'decisoes' (nova decisão).

    A memória usa id determinístico (gerar_id_memoria) e metadados rastreáveis
    (tipo 'dec_techscout', frente, origem, modelo). Em falha devolve
    status 'ERROR' — não-fatal para o nó.
    """
    memoria_id = gerar_id_memoria(analise_mapeador)
    documento = (
        "DECISÃO DO TECH SCOUT (memória gerada automaticamente):\n"
        f"Frente alvo: {frente_alvo}\n"
        f"Origem das buscas: {origem}\n"
        "Relatório técnico:\n"
        f"{relatorio}"
    )
    metadata = {
        "tipo": "dec_techscout",
        "frente_alvo": frente_alvo,
        "origem": origem,
        "modelo": modelo_usado,
        "salvo_em": datetime.datetime.now().isoformat(timespec="seconds"),
    }
    inicio = time.perf_counter()
    try:
        cliente = crear_cliente_chroma(CHROMA_DATA_DIR_ABSOLUTO)
        coleccion = garantizar_coleccion_decisoes(cliente)
        coleccion.upsert(
            ids=[memoria_id], documents=[documento], metadatas=[metadata]
        )
        latencia_ms = round((time.perf_counter() - inicio) * 1000, 4)
        return {
            "coleccion": COLLECTION_DECISOES,
            "id_memoria": memoria_id,
            "documento_caracteres": len(documento),
            "origem": origem,
            "modelo": modelo_usado,
            "latencia_ms": latencia_ms,
            "status": "OK",
            "erro": None,
        }
    except Exception as exc:
        latencia_ms = round((time.perf_counter() - inicio) * 1000, 4)
        return {
            "coleccion": COLLECTION_DECISOES,
            "id_memoria": memoria_id,
            "documento_caracteres": len(documento),
            "origem": origem,
            "modelo": modelo_usado,
            "latencia_ms": latencia_ms,
            "status": "ERROR",
            "erro": f"{type(exc).__name__}: {exc}",
        }


def montar_prompt_techscout(
    regras: str,
    analise_mapeador: str,
    rag: dict,
    resultados_web: list[dict],
) -> str:
    """Monta o prompt do Agente 2: regras + análise do Mapeador + RAG + web."""
    hits = rag.get("hits") or []
    if hits:
        linhas = []
        for i, hit in enumerate(hits, 1):
            dist = hit.get("distancia")
            dist_str = f" (distância={dist})" if dist is not None else ""
            linhas.append(
                f"  [{i}] {str(hit.get('documento') or '')[:400]}{dist_str}"
            )
        contexto_rag = "\n".join(linhas)
    else:
        contexto_rag = (
            "  Nenhuma decisão técnica similar encontrada na base ChromaDB "
            "para esta análise."
        )

    if resultados_web:
        linhas_web = []
        for i, item in enumerate(resultados_web, 1):
            linhas_web.append(
                f"  [{i}] {item.get('titulo', '')} — {item.get('href', '')}\n"
                f"      {item.get('corpo', '')}"
            )
        contexto_web = "\n".join(linhas_web)
    else:
        contexto_web = (
            "  Nenhum resultado web disponível (busca indisponível ou sem "
            "retorno). Use apenas o contexto acima."
        )

    return (
        "SYSTEM — AGENTE 2 (TECH SCOUT & SEARCH ENGINE):\n"
        f"{regras}\n\n"
        "ANÁLISE DO AGENTE 1 (MAPEADOR ESTRUTURAL) A AVALIAR:\n"
        f"{analise_mapeador}\n\n"
        "ANTECEDENTES / DECISÕES SIMILARES (CHROMADB — COLEÇÃO 'DECISOES'):\n"
        f"{contexto_rag}\n\n"
        "RESULTADOS DE BUSCA WEB (TECNOLOGIAS OPEN-SOURCE ATUAIS):\n"
        f"{contexto_web}\n\n"
        "INSTRUÇÃO DE SAÍDA:\n"
        "Apresente um RELATÓRIO TÉCNICO ENXUTO do Tech Scout: stack sugerida "
        "com ferramentas R$ 0.00, alternativas viáveis, arquitetura/boas "
        "práticas e próximos passos para a v1. Priorize Python, SQLite e "
        "ferramentas locais. Seja direto e objetivo."
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


def nodo_techscout(state: CortexState) -> dict:
    """Executa o Agente 2 (Tech Scout & Search Engine) sobre o CortexState.

    Retorna a atualização parcial do estado:
        {
            "analise_techscout": str,
            "contexto_rag": list,
            "busca_web_acionada": bool,
            "erros": list,
        }
    E registra a telemetria completa em Metrics/metrics_techscout_v2.json.
    """
    inicio_nodo = time.perf_counter()
    estado = dict(state)
    entrada_bruta = str(estado.get("entrada_bruta", "")).strip()
    frente_alvo = str(estado.get("frente_alvo", "GERAL")).strip() or "GERAL"
    analise_mapeador = str(estado.get("analise_mapeador", "")).strip()

    # Base de consulta: análise do Mapeador (com fallback para entrada_bruta).
    consulta = analise_mapeador or entrada_bruta

    agora = _agora()
    reporte: dict = {
        "proyecto": "RS4-cortex-flow v2 (Cortex-Flow V2)",
        "dose": "Dose 2 (Fase 2) - Nó Agente 2 (Tech Scout & Search Engine) "
        "— Item 08.3",
        "regla": "Regla CEO RS4 - Telemetria de nó LangGraph",
        "descripcion": (
            "Nó Agente 2: RAG no ChromaDB (coleção 'decisoes') + se insuficiente, "
            "busca web leve via duckduckgo-search + Ollama local (qwen2.5:7b, "
            "fallback qwen2.5:3b) + nova memória/decisão gravada de volta no "
            "ChromaDB."
        ),
        "fecha_hora": agora.strftime("%Y-%m-%d %H:%M:%S"),
        "fecha_hora_iso": agora.isoformat(timespec="seconds"),
        "ambiente": {
            "python": platform.python_version(),
            "chromadb_version": chromadb.__version__,
            "duckduckgo_search": _versao_duckduckgo_search(),
            "plataforma": platform.platform(),
            "workdir": str(DIR_RAIZ),
        },
        "entrada": {
            "frente_alvo": frente_alvo,
            "entrada_bruta_caracteres": len(entrada_bruta),
            "entrada_bruta_preview": entrada_bruta[:200],
            "analise_mapeador_caracteres": len(analise_mapeador),
            "analise_mapeador_preview": analise_mapeador[:200],
        },
        "rag_chromadb": {},
        "busca_web": {},
        "prompt_techscout": {},
        "ollama": {},
        "memoria_chromadb": {},
        "nodo": {},
        "erros": list(estado.get("erros") or []),
        "validacion": {},
    }

    contexto_rag: list = []
    busca_web_acionada = False
    resultados_web: list[dict] = []

    # (a) RAG — antecedentes/decisões técnicas na coleção 'decisoes' do ChromaDB
    rag = recuperar_contexto_rag(consulta)
    reporte["rag_chromadb"] = rag
    contexto_rag = rag.get("hits") or []
    if rag.get("status") != "OK":
        reporte["erros"].append(f"RAG: {rag.get('erro')}")

    # (b) Insuficiência do retorno => busca leve na web (duckduckgo-search)
    if rag_insuficiente(rag):
        busca_web_acionada, resultados_web, tele_web = buscar_web_duckduckgo(
            consulta, entrada_bruta=entrada_bruta
        )
        reporte["busca_web"] = tele_web
        if tele_web.get("status") in ("ERROR", "SEM_RESULTADOS") and tele_web.get(
            "erro"
        ):
            reporte["erros"].append(f"WEB: {tele_web.get('erro')}")
    else:
        reporte["busca_web"] = {
            "acionada": False,
            "motivo": "RAG suficiente (hit(s) com distância <= limiar "
            f"{LIMIAR_SEMELHANCA}) — memória prévia evita nova busca web.",
            "total_resultados": 0,
            "status": "SKIPPED",
            "erro": None,
        }


    # (c) Prompt do Agente 2 + chamada local ao Ollama (7b com fallback 3b)
    try:
        regras = cargar_reglas_agente2()
    except Exception as exc:
        regras = REGRAS_TECHSCOUT
        reporte["erros"].append(f"PROMPT_RULES: {type(exc).__name__}: {exc}")
    prompt = montar_prompt_techscout(regras, consulta, rag, resultados_web)
    reporte["prompt_techscout"] = {
        "fonte_regras": str(CAMINHO_PROMPT_AGENTE2),
        "caracteres_prompt": len(prompt),
        "preview": prompt[:300],
    }

    try:
        analise_techscout, tele_ollama = chamar_ollama_com_fallback(prompt)
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
        analise_techscout = (
            "[ERRO OLLAMA] O Agente 2 não obteve resposta do modelo local — "
            f"sem relatório técnico. Detalhe: {exc}"
        )
        estado_nodo = "ERRO_OLLAMA"

    # (d) Memória — grava o relatório de volta no ChromaDB (nova decisão)
    origem = "chroma+web" if busca_web_acionada else "chroma"
    if estado_nodo == "OK":
        modelo_usado = str(tele_ollama.get("modelo") or MODELO_PRINCIPAL)
    else:
        modelo_usado = MODELO_PRINCIPAL
    memoria = salvar_memoria_chromadb(
        analise_techscout, consulta, frente_alvo, origem, modelo_usado
    )
    reporte["memoria_chromadb"] = memoria
    if memoria.get("status") == "ERROR" and memoria.get("erro"):
        # Persistência da memória é desejável mas não fatal para o relatório.
        reporte["erros"].append(f"MEMORIA: {memoria.get('erro')}")

    duracao_nodo_ms = round((time.perf_counter() - inicio_nodo) * 1000, 4)
    reporte["nodo"] = {
        "funcao": "nodo_techscout",
        "assinatura": "nodo_techscout(state: CortexState) -> dict",
        "duracao_total_ms": duracao_nodo_ms,
        "analise_techscout_caracteres": len(analise_techscout),
        "analise_techscout_preview": analise_techscout[:300],
        "contexto_rag_total": len(contexto_rag),
        "busca_web_acionada": busca_web_acionada,
        "resultados_web_total": len(resultados_web),
        "memoria_salva": memoria.get("status") == "OK",
        "estado": estado_nodo,
    }

    # Telemetria/validação (Regra CEO RS4)
    try:
        py_compile.compile(__file__, doraise=True)
        ok_sintaxe = True
    except py_compile.PyCompileError as exc:
        ok_sintaxe = False
        reporte["erros"].append(f"PY_COMPILE: {exc}")

    sucesso = (
        estado_nodo == "OK"
        and ok_sintaxe
        and bool(analise_techscout.strip())
    )
    reporte["validacion"] = {
        "py_compile_techscout": "OK" if ok_sintaxe else "ERRO",
        "nodo_estado": estado_nodo,
        "status": "SUCCESS" if sucesso else "FAILURE",
        "exit_code": 0 if sucesso else 1,
    }

    try:
        RUTA_METRICS_TECHSCOUT.parent.mkdir(parents=True, exist_ok=True)
        RUTA_METRICS_TECHSCOUT.write_text(
            json.dumps(reporte, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except (OSError, TypeError, ValueError) as exc:
        reporte["erros"].append(f"METRICS_WRITE: {exc}")

    return {
        "analise_techscout": analise_techscout,
        "contexto_rag": contexto_rag,
        "busca_web_acionada": busca_web_acionada,
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
            "Ideia: criar uma API Python simples — CRUD de tarefas com SQLite, "
            "sem custo de hospedagem, usando apenas ferramentas open-source."
        ),
        "frente_alvo": "GERAL",
        "analise_mapeador": (
            "ANÁLISE DO AGENTE 1 — Mapeador e Analista Estrutural\n\n"
            "**FATOS:**\n- O usuário quer criar uma API Python simples do tipo CRUD.\n"
            "- O ambiente alvo é local/desktop, com custo R$ 0,00.\n"
            "- O banco de dados será SQLite (arquivo local, sem servidor).\n"
            "- A ferramenta principal é código aberto e roda sem nuvem paga.\n\n"
            "**PROBLEMA CENTRAL:**\n- Escolher a menor stack confiável e gratuita "
            "para entregar uma API Python CRUD com SQLite em ambiente local."
        ),
        "analise_techscout": "",
        "analise_critico": "",
        "sintese_final": "",
        "contexto_rag": [],
        "erros": [],
    }
    resultado = nodo_techscout(demo)
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    return 0 if resultado.get("analise_techscout") else 1


if __name__ == "__main__":
    raise SystemExit(_main_demo())

