# -*- coding: utf-8 -*-
"""Nó Construtor / Builder (Item 08.6) — Cortex-Flow V2.

Nó LangGraph-ready que transforma a 'sintese_final' (gerada pelo Sintetizador)
em um template / MVP inicial de código executável:

  1. Resgata 'sintese_final' do CortexState (com fallback gracioso para
     'analise_techscout' ou 'entrada_bruta').
  2. Consulta a coleção 'decisoes' no ChromaDB (RAG) para incorporar boas
     práticas de engenharia e governança do DNA RS4 (segurança, custo R$ 0,00,
     código limpo e modular).
  3. Executa a chamada local ao Ollama com o modelo especialista em código:
     'qwen2.5-coder:7b' (com fallback de segurança para 'qwen2.5:7b').
  4. Salva fisicamente o template/MVP em 'drafts/templates/' com carimbo de data/hora.
  5. Atualiza 'codigo_mvp' e 'caminho_template_md' no CortexState.
  6. Telemetria (Regra CEO RS4): mede latência exata, tokens por segundo (tokens/s),
     modelo utilizado, status e persistência em 'Metrics/metrics_builder_v2.json'.
"""

from __future__ import annotations

import datetime
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
MODELO_PRINCIPAL = "qwen2.5-coder:7b"
MODELO_FALLBACK = "qwen2.5:7b"
MODELO_FALLBACKS = (MODELO_FALLBACK,)
TEMPERATURA = 0.2  # Baixa temperatura para geração de código determinístico e preciso
NUM_PREDICT = 2048  # Capacidade ampla para estrutura completa de MVP e código
TIMEOUT_OLLAMA_S = 300
N_RESULTADOS_RAG = 3

DIR_RAIZ = Path(__file__).resolve().parents[2]
CHROMA_DATA_DIR_ABSOLUTO = str(DIR_RAIZ / "chroma_db_data")
DIR_DRAFTS_TEMPLATES = DIR_RAIZ / "drafts" / "templates"
CAMINHO_PROMPT_BUILDER = DIR_RAIZ / "agentes" / "agente5_builder.txt"
RUTA_METRICS_BUILDER = DIR_RAIZ / "Metrics" / "metrics_builder_v2.json"
OLLAMA_API_GENERATE = f"{OLLAMA_BASE_URL}/api/generate"

REGRAS_BUILDER_EMBUTIDAS = (
    "Você é o AGENTE BUILDER / CONSTRUTOR de Soluções do RS4-cortex-flow.\n"
    "Sua função é transformar as diretrizes e o menor próximo passo definidos "
    "na Síntese Final em um template/MVP de código funcional, limpo e executável.\n\n"
    "DIRETRIZES:\n"
    "1. Especialista em Engenharia de Software e Código Limpo (Python 3.11+).\n"
    "2. Construa código executável real, não apenas pseudocódigo ou placeholders vazios.\n"
    "3. Respeite a arquitetura e stack selecionada na Síntese (custo R$ 0,00, simplicidade radical).\n"
    "4. Forneça:\n"
    "   - Estrutura de arquivos do projeto recomendada.\n"
    "   - Código fonte principal completo, tipado e documentado.\n"
    "   - Como executar em 3 passos simples (Instalação, Configuração, Execução).\n"
    "   - Teste básico de fumaça (smoke test).\n"
    "5. Mantenha o formato Markdown com blocos de código com destaque de sintaxe adequado.\n"
)


def _agora() -> datetime.datetime:
    """Timestamp para telemetria e registros temporais."""
    return datetime.datetime.now()


def _nome_arquivo_template(agora: datetime.datetime) -> str:
    """Gera nome padronizado de arquivo para drafts/templates/."""
    return f"template_mvp_{agora.strftime('%Y%m%d_%H%M%S')}.md"


def cargar_reglas_builder() -> str:
    """Lê e retorna as regras do prompt do Agente Builder."""
    if not CAMINHO_PROMPT_BUILDER.exists():
        return REGRAS_BUILDER_EMBUTIDAS
    return CAMINHO_PROMPT_BUILDER.read_text(encoding="utf-8").strip()


def recuperar_contexto_rag(
    texto_especificacao: str, n_resultados: int = N_RESULTADOS_RAG
) -> dict:
    """Consulta a coleção 'decisoes' no ChromaDB para resgatar diretrizes de arquitetura limpa.

    Degrada graciosamente em caso de erro sem interromper o fluxo do grafo.
    """
    query = (
        f"{texto_especificacao[:300]}\n"
        "Diretrizes de código, padrões de projeto, segurança e boas práticas de desenvolvimento RS4."
    )
    inicio = time.perf_counter()
    try:
        cliente = crear_cliente_chroma(CHROMA_DATA_DIR_ABSOLUTO)
        coleccion = garantizar_coleccion_decisoes(cliente)
        resultado = coleccion.query(query_texts=[query], n_results=n_resultados)
        latencia_ms = round((time.perf_counter() - inicio) * 1000, 4)

        if isinstance(resultado, dict):
            ids = resultado.get("ids") or [[]]
            docs = resultado.get("documents") or [[]]
            metas = resultado.get("metadatas") or [[]]
            dists = resultado.get("distances") or [[]]
        else:
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


def montar_prompt_builder(
    regras: str,
    sintese_final: str,
    frente_alvo: str,
    rag: dict,
) -> str:
    """Monta o prompt para o modelo especialista em código gerar o template/MVP."""
    hits = rag.get("hits") or []
    if hits:
        linhas = []
        for i, hit in enumerate(hits, 1):
            texto_doc = str(hit.get("documento") or "")[:300]
            linhas.append(f"  [{i}] {texto_doc}")
        contexto_rag = "\n".join(linhas)
    else:
        contexto_rag = "  Nenhuma diretriz adicional recuperada do ChromaDB."

    return (
        "SYSTEM — AGENTE BUILDER (ESPECIALISTA EM CÓDIGO E ARQUITETURA):\n"
        f"{regras}\n\n"
        f"FRENTE ALVO: {frente_alvo}\n\n"
        "--- ESPECIFICAÇÃO TÉCNICA E SÍNTESE FINAL (PLANO DE AÇÃO) ---\n"
        f"{sintese_final.strip()}\n\n"
        "--- DIRETRIZES DE ENGENHARIA RS4 (RAG) ---\n"
        f"{contexto_rag}\n\n"
        "--- INSTRUÇÕES ESPECÍFICAS DE SAÍDA ---\n"
        "Gere o documento Markdown contendo o Template e Código MVP completo, pronto para execução imediata.\n"
        "Estruture a resposta com clareza:\n"
        "# TEMPLATE E CÓDIGO MVP — RS4 CORTEX-FLOW\n\n"
        "## 1. Visão Geral e Estrutura de Arquivos\n"
        "- Apresente a árvore de diretórios recomendada para o projeto.\n\n"
        "## 2. Dependências e Configuração (`requirements.txt` / setup)\n"
        "- Dependências estritas com custo R$ 0,00 e bibliotecas leves.\n\n"
        "## 3. Código Fonte Principal (Implementação Concreta)\n"
        "- Código Python 3.11+ completo, tipado, com docstrings e tratamento de exceções.\n"
        "- Implemente a lógica necessária para o Menor Próximo Passo indicado na Síntese.\n\n"
        "## 4. Como Executar (Guia Rápido em 3 Passos)\n"
        "- Comandos exatos para instalação, execução e validação.\n\n"
        "## 5. Teste de Fumaça (Smoke Test / Verificação)\n"
        "- Script simples ou comando de teste para verificar se o MVP está operando.\n"
    )


def _chamar_modelo(modelo: str, prompt: str) -> tuple[str | None, dict]:
    """Chama a API local do Ollama (/api/generate) medindo latência exata e métricas."""
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

        eval_count = resposta_raw.get("eval_count") or 0
        eval_duration_ns = resposta_raw.get("eval_duration") or 0
        eval_duration_ms = round(eval_duration_ns / 1e6, 2) if eval_duration_ns else None

        tokens_por_segundo = None
        if eval_duration_ms and eval_duration_ms > 0 and eval_count > 0:
            tokens_por_segundo = round(eval_count / (eval_duration_ms / 1000.0), 2)

        return texto, {
            "modelo": modelo,
            "status_http": resp.status,
            "latencia_ms": latencia_ms,
            "tokens_prompt": resposta_raw.get("prompt_eval_count"),
            "tokens_resposta": eval_count,
            "eval_duration_ms": eval_duration_ms,
            "tokens_por_segundo": tokens_por_segundo,
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
            "tokens_por_segundo": None,
            "done_reason": None,
            "erro": f"{type(exc).__name__}: {exc}",
        }


def chamar_ollama_com_fallback(prompt: str) -> tuple[str, dict]:
    """Executa 'qwen2.5-coder:7b' com fallback de segurança para 'qwen2.5:7b'."""
    tentativas: list[dict] = []
    for modelo in (MODELO_PRINCIPAL, *MODELO_FALLBACKS):
        texto, telemetria = _chamar_modelo(modelo, prompt)
        telemetria = dict(telemetria)
        telemetria["fallback_usado"] = modelo != MODELO_PRINCIPAL
        tentativas.append(telemetria)
        if texto:
            telemetria["tentativas"] = [dict(t) for t in tentativas]
            return texto, telemetria

    erros = "; ".join(
        f"{t['modelo']}: {t['erro']}" for t in tentativas if t.get("erro")
    )
    raise RuntimeError(f"Todos os modelos Ollama falharam no Builder. {erros}")


def salvar_template_markdown(
    codigo_markdown: str,
    frente_alvo: str,
    modelo_usado: str,
    agora: datetime.datetime,
) -> str:
    """Salva fisicamente o template/MVP em 'drafts/templates/'.

    Retorna o caminho absoluto do arquivo salvo.
    """
    DIR_DRAFTS_TEMPLATES.mkdir(parents=True, exist_ok=True)
    nome_arquivo = _nome_arquivo_template(agora)
    caminho = DIR_DRAFTS_TEMPLATES / nome_arquivo

    cabecalho = (
        "---\n"
        "PROJETO: RS4-cortex-flow v2\n"
        "AGENTE: Builder / Construtor de Soluções (Item 08.6)\n"
        f"DATA_EXECUCAO: '{agora.strftime('%Y-%m-%d %H:%M:%S')}'\n"
        f"MODELO_USADO: '{modelo_usado}'\n"
        f"FRENTE_ALVO: '{frente_alvo}'\n"
        "STATUS: 'CONCLUIDO'\n"
        "---\n\n"
    )

    documento_completo = cabecalho + codigo_markdown.strip() + "\n"
    caminho.write_text(documento_completo, encoding="utf-8")
    return str(caminho)


def nodo_builder(state: CortexState) -> dict:
    """Executa o Nó Construtor / Builder (Item 08.6) sobre o CortexState.

    Fluxo:
      a) Lê a 'sintese_final' (ou fallback para analise_techscout / entrada_bruta);
      b) Consulta o DNA da Filosofia RS4 via RAG no ChromaDB (coleção 'decisoes');
      c) Monta o prompt com diretrizes para o modelo especialista em código;
      d) Executa chamada local ao Ollama ('qwen2.5-coder:7b', fallback 'qwen2.5:7b');
      e) Salva a saída em 'drafts/templates/';
      f) Atualiza 'codigo_mvp' e 'caminho_template_md' no CortexState;
      g) Registra telemetria completa em 'Metrics/metrics_builder_v2.json'.
    """
    inicio_nodo = time.perf_counter()
    estado = dict(state)

    frente_alvo = str(estado.get("frente_alvo", "GERAL")).strip() or "GERAL"
    sintese_final = str(estado.get("sintese_final") or "").strip()

    # Fallback caso a síntese final esteja vazia
    if not sintese_final:
        partes_fallback = []
        if estado.get("analise_techscout"):
            partes_fallback.append(f"TECH SCOUT:\n{estado['analise_techscout']}")
        if estado.get("analise_mapeador"):
            partes_fallback.append(f"MAPEADOR:\n{estado['analise_mapeador']}")
        if estado.get("entrada_bruta"):
            partes_fallback.append(f"ENTRADA BRUTA:\n{estado['entrada_bruta']}")
        sintese_final = "\n\n".join(partes_fallback) or "Sem especificações fornecidas."

    agora = _agora()
    reporte: dict = {
        "proyecto": "RS4-cortex-flow v2 (Cortex-Flow V2)",
        "dose": "Item 08.6 - Nó Construtor / Builder",
        "regla": "Regla CEO RS4 - Telemetria de nó LangGraph",
        "descripcion": (
            "Nó Builder: transformação da síntese técnica em template/MVP inicial "
            "+ RAG no ChromaDB (coleção 'decisoes') + "
            "Ollama local especialista ('qwen2.5-coder:7b', fallback 'qwen2.5:7b') "
            "+ salvamento físico em drafts/templates/."
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
            "tamanho_sintese_recebida": len(sintese_final),
            "chaves_presentes": [k for k, v in estado.items() if str(v or "").strip()],
        },
        "rag_chromadb": {},
        "prompt_builder": {},
        "ollama": {},
        "template_draft": {},
        "nodo": {},
        "erros": list(estado.get("erros") or []),
        "validacion": {},
    }

    # (b) Consulta RAG ao ChromaDB
    rag = recuperar_contexto_rag(sintese_final)
    reporte["rag_chromadb"] = rag
    contexto_rag: list = rag.get("hits") or []
    if rag.get("status") != "OK":
        reporte["erros"].append(f"RAG: {rag.get('erro')}")

    # (c) Prompt do Builder
    regras = cargar_reglas_builder()
    prompt = montar_prompt_builder(regras, sintese_final, frente_alvo, rag)
    reporte["prompt_builder"] = {
        "fonte_regras": str(CAMINHO_PROMPT_BUILDER),
        "caracteres_prompt": len(prompt),
        "preview": prompt[:300],
    }

    # (d) Execução Ollama com especialista em código
    try:
        codigo_mvp, tele_ollama = chamar_ollama_com_fallback(prompt)
        tele_ollama = dict(tele_ollama)
        tele_ollama["url_api_generate"] = OLLAMA_API_GENERATE
        tele_ollama["temperatura"] = TEMPERATURA
        tele_ollama["num_predict"] = NUM_PREDICT
        reporte["ollama"] = tele_ollama
        modelo_usado = str(tele_ollama.get("modelo") or MODELO_PRINCIPAL)
        estado_nodo = "OK"
    except Exception as exc:
        reporte["erros"].append(f"OLLAMA: {type(exc).__name__}: {exc}")
        reporte["ollama"] = {
            "modelo": None,
            "url_api_generate": OLLAMA_API_GENERATE,
            "temperatura": TEMPERATURA,
            "num_predict": NUM_PREDICT,
            "tokens_por_segundo": None,
            "erro": f"{type(exc).__name__}: {exc}",
        }
        codigo_mvp = (
            "# ERRO NA GERAÇÃO DO TEMPLATE/MVP\n\n"
            f"[ERRO OLLAMA] O Agente Builder não obteve resposta do modelo local. Detalhe: {exc}"
        )
        modelo_usado = MODELO_PRINCIPAL
        estado_nodo = "ERRO_OLLAMA"

    # (e) Salvar saída física em drafts/templates/
    caminho_template_md = ""
    try:
        caminho_template_md = salvar_template_markdown(
            codigo_mvp, frente_alvo, modelo_usado, agora
        )
        reporte["template_draft"] = {
            "diretorio": str(DIR_DRAFTS_TEMPLATES),
            "arquivo_markdown": Path(caminho_template_md).name,
            "caminho_absoluto": caminho_template_md,
            "carimbo_data_hora": _nome_arquivo_template(agora),
            "codigo_caracteres": len(codigo_mvp),
            "status": "OK",
        }
    except Exception as exc:
        reporte["erros"].append(f"TEMPLATE_DRAFT: {type(exc).__name__}: {exc}")
        reporte["template_draft"] = {
            "diretorio": str(DIR_DRAFTS_TEMPLATES),
            "status": "ERROR",
            "erro": f"{type(exc).__name__}: {exc}",
        }
        estado_nodo = "ERRO_DRAFT"

    duracao_nodo_ms = round((time.perf_counter() - inicio_nodo) * 1000, 4)
    reporte["nodo"] = {
        "funcao": "nodo_builder",
        "assinatura": "nodo_builder(state: CortexState) -> dict",
        "duracao_total_ms": duracao_nodo_ms,
        "codigo_caracteres": len(codigo_mvp),
        "codigo_preview": codigo_mvp[:300],
        "contexto_rag_total": len(contexto_rag),
        "estado": estado_nodo,
    }

    # Validação e Telemetria (Regra CEO RS4)
    try:
        py_compile.compile(__file__, doraise=True)
        ok_sintaxe = True
    except py_compile.PyCompileError as exc:
        ok_sintaxe = False
        reporte["erros"].append(f"PY_COMPILE: {exc}")

    sucesso = estado_nodo == "OK" and ok_sintaxe
    reporte["validacion"] = {
        "py_compile_builder": "OK" if ok_sintaxe else "ERRO",
        "nodo_estado": estado_nodo,
        "status": "SUCCESS" if sucesso else "FAILURE",
        "exit_code": 0 if sucesso else 1,
    }

    try:
        RUTA_METRICS_BUILDER.parent.mkdir(parents=True, exist_ok=True)
        RUTA_METRICS_BUILDER.write_text(
            json.dumps(reporte, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except Exception as exc:
        reporte["erros"].append(f"METRICS_WRITE: {exc}")

    return {
        "codigo_mvp": codigo_mvp,
        "caminho_template_md": caminho_template_md,
        "contexto_rag": contexto_rag,
        "erros": reporte["erros"],
    }
