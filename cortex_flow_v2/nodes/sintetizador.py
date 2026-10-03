# -*- coding: utf-8 -*-
"""Nó Agente 4 (Sintetizador & Refinador) — Cortex-Flow V2 (Item 08.5).

Nó LangGraph-ready que consolida as análises dos agentes anteriores:
  - Agente 1: Mapeador Estrutural (analise_mapeador)
  - Agente 2: Tech Scout (analise_techscout)
  - Agente 3: Crítico Ácido (analise_critico)
  - Entrada original (entrada_bruta)

Responsabilidades:
  1. Consolidar as análises em um documento Markdown padronizado com
     YAML Front-Matter no cabeçalho contendo:
     PROJETO, DATA_EXECUCAO, MODELO_USADO, FRENTE_ALVO, STATUS.
  2. Resumir a decisão técnica final alinhando os 3 pareceres.
  3. Definir o "MENOR PRÓXIMO PASSO" (ação concreta e imediata de no máximo 45 minutos).
  4. Consultar o DNA da Filosofia RS4 via RAG no ChromaDB (coleção 'decisoes').
  5. Atualizar 'sintese_final' no CortexState.
  6. Salvar o documento final em 'drafts/refinados/' com carimbo de data/hora.
  7. Telemetria (Regra CEO RS4): registrar latências, modelo, status e métricas
     em 'Metrics/metrics_sintetizador_v2.json' com status SUCCESS e exit_code 0.
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
MODELO_PRINCIPAL = "qwen2.5:7b"
MODELO_FALLBACK = "qwen2.5:3b"
MODELO_FALLBACKS = (MODELO_FALLBACK,)
TEMPERATURA = 0.3  # Síntese balanceada: precisa, estruturada e executiva
NUM_PREDICT = 1536  # Capacidade ampla para consolidação rica em Markdown
TIMEOUT_OLLAMA_S = 240
N_RESULTADOS_RAG = 3

DIR_RAIZ = Path(__file__).resolve().parents[2]
CHROMA_DATA_DIR_ABSOLUTO = str(DIR_RAIZ / "chroma_db_data")
DIR_DRAFTS_REFINADOS = DIR_RAIZ / "drafts" / "refinados"
CAMINHO_PROMPT_AGENTE4 = DIR_RAIZ / "agentes" / "agente4_sintetizador.txt"
RUTA_METRICS_SINTETIZADOR = DIR_RAIZ / "Metrics" / "metrics_sintetizador_v2.json"
OLLAMA_API_GENERATE = f"{OLLAMA_BASE_URL}/api/generate"

# Regras embutidas de fallback para o Agente 4 caso o arquivo prompt não exista
REGRAS_SINTETIZADOR = (
    "Você é o AGENTE 4 — Sintetizador e Diretor de Entrega do RS4-cortex-flow.\n"
    "Sua função é consolidar as análises dos Agentes 1, 2 e 3 e gerar o plano de ação final.\n\n"
    "DIRETRIZES:\n"
    "1. Sinta o parecer dos 3 agentes anteriores e resuma a decisão técnica final.\n"
    "2. Defina o 'MENOR PRÓXIMO PASSO' (uma ação concreta e imediata de no máximo 45 minutos).\n"
    "3. Formate a saída em Markdown limpo, pronto para ser arquivado na Biblioteca Pessoal de Conhecimento.\n"
    "4. Respeite os princípios do DNA da Filosofia RS4: pragmatismo, custo R$ 0,00, sem complexidade desnecessária.\n"
)


def _agora() -> datetime.datetime:
    """Timestamp para telemetria e registro temporal."""
    return datetime.datetime.now()


def _nome_arquivo_refinado(agora: datetime.datetime) -> str:
    """Gera nome padronizado de arquivo para drafts/refinados/."""
    return f"sintese_refinada_{agora.strftime('%Y%m%d_%H%M%S')}.md"


def cargar_reglas_agente4() -> str:
    """Lê e retorna as regras do prompt do Agente 4 (Sintetizador)."""
    if not CAMINHO_PROMPT_AGENTE4.exists():
        raise FileNotFoundError(
            f"Prompt do Agente 4 não encontrado: {CAMINHO_PROMPT_AGENTE4}"
        )
    return CAMINHO_PROMPT_AGENTE4.read_text(encoding="utf-8").strip()


def recuperar_contexto_rag(
    texto_base: str, n_resultados: int = N_RESULTADOS_RAG
) -> dict:
    """Consulta a coleção 'decisoes' no ChromaDB para resgatar diretrizes de síntese e entrega.

    Em caso de falha não levanta exceção: devolve status 'ERROR' para degradação graciosa.
    """
    query = (
        f"{texto_base}\nFilosofia RS4 - Síntese, Diretor de Entrega, menor próximo passo "
        "e critérios de conclusão responsável."
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


def montar_prompt_sintetizador(
    reglas: str,
    entrada_bruta: str,
    frente_alvo: str,
    analise_mapeador: str,
    analise_techscout: str,
    analise_critico: str,
    rag: dict,
) -> str:
    """Monta o prompt para o Agente 4 consolidar as análises dos nós anteriores."""
    hits = rag.get("hits") or []
    if hits:
        linhas = []
        for i, hit in enumerate(hits, 1):
            texto_doc = str(hit.get("documento") or "")[:350]
            linhas.append(f"  [{i}] {texto_doc}")
        contexto_rag = "\n".join(linhas)
    else:
        contexto_rag = "  Nenhum antecedente adicional recuperado no ChromaDB."

    return (
        "SYSTEM — AGENTE 4 (SINTETIZADOR E DIRETOR DE ENTREGA):\n"
        f"{reglas}\n\n"
        "--- ENTRADAS DO GRAFO CORTEX-FLOW ---\n"
        f"FRENTE ALVO: {frente_alvo}\n\n"
        f"ENTRADA BRUTA (Objetivo Original):\n{entrada_bruta.strip()}\n\n"
        f"ANÁLISE DO AGENTE 1 (MAPEADOR ESTRUTURAL):\n{analise_mapeador.strip()}\n\n"
        f"ANÁLISE DO AGENTE 2 (TECH SCOUT):\n{analise_techscout.strip()}\n\n"
        f"ANÁLISE DO AGENTE 3 (CRÍTICO ÁCIDO):\n{analise_critico.strip()}\n\n"
        "CONTEXTO RAG — DNA DA FILOSOFIA RS4:\n"
        f"{contexto_rag}\n\n"
        "--- INSTRUÇÕES ESPECÍFICAS DE SAÍDA ---\n"
        "Consolide tudo em um documento Markdown completo, objetivo e altamente prático.\n"
        "Estruture o documento nas seguintes seções:\n"
        "# SÍNTESE FINAL E PLANO DE AÇÃO EXECUTIVO\n\n"
        "## 1. Decisão Técnica Final & Síntese Integrada\n"
        "- Resumo convergente das diretrizes do Mapeador, Tech Scout e Crítico.\n"
        "- Como os alertas e riscos levantados pelo Crítico Ácido foram endereçados.\n\n"
        "## 2. Arquitetura e Stack Selecionada (R$ 0,00)\n"
        "- Componentes essenciais definidos pelo Tech Scout e blindados pelo Crítico.\n\n"
        "## 3. MENOR PRÓXIMO PASSO (Ação Concreta <= 45 Minutos)\n"
        "- O que fazer agora mesmo de forma prática e mensurável, sem dispersão.\n\n"
        "## 4. Checklist Vivo de Execução (Governança RS4)\n"
        "- Passos sequenciais de implementação (com caixas de checagem [ ]).\n\n"
        "Importante: NÃO inclua o bloco YAML Front-Matter no corpo gerado, pois ele será inserido "
        "programaticamente no cabeçalho pelo sistema."
    )


def _chamar_modelo(modelo: str, prompt: str) -> tuple[str | None, dict]:
    """Chama a API local do Ollama (/api/generate) medindo a latência exata."""
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
    """Executa 'qwen2.5:7b' com fallback seguro para 'qwen2.5:3b'."""
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
    raise RuntimeError(f"Todos os modelos Ollama falharam no Sintetizador. {erros}")


def estruturar_documento_com_frontmatter(
    conteudo_markdown: str,
    frente_alvo: str,
    modelo_usado: str,
    agora: datetime.datetime,
    status: str = "CONCLUIDO",
) -> str:
    """Padroniza o documento Markdown com YAML Front-Matter no cabeçalho.

    Campos obrigatórios:
      PROJETO, DATA_EXECUCAO, MODELO_USADO, FRENTE_ALVO, STATUS.
    """
    # Remove YAML Front-Matter pré-existente se a LLM tiver inserido inadvertidamente
    texto_limpo = re.sub(r"^---[\s\S]*?---\s*", "", conteudo_markdown.strip())

    front_matter = (
        "---\n"
        "PROJETO: RS4-cortex-flow v2\n"
        f"DATA_EXECUCAO: '{agora.strftime('%Y-%m-%d %H:%M:%S')}'\n"
        f"MODELO_USADO: '{modelo_usado}'\n"
        f"FRENTE_ALVO: '{frente_alvo}'\n"
        f"STATUS: '{status}'\n"
        "---\n\n"
    )
    return front_matter + texto_limpo + "\n"


def salvar_sintese_markdown(
    documento_markdown: str,
    agora: datetime.datetime,
) -> str:
    """Salva a síntese final formatada em 'drafts/refinados/'.

    Retorna o caminho absoluto do arquivo salvo.
    """
    DIR_DRAFTS_REFINADOS.mkdir(parents=True, exist_ok=True)
    nome_arquivo = _nome_arquivo_refinado(agora)
    caminho = DIR_DRAFTS_REFINADOS / nome_arquivo
    caminho.write_text(documento_markdown, encoding="utf-8")
    return str(caminho)


def nodo_sintetizador(state: CortexState) -> dict:
    """Executa o Nó Sintetizador & Refinador (Agente 4) sobre o CortexState.

    Fluxo:
      a) Lê 'entrada_bruta', 'frente_alvo', 'analise_mapeador',
         'analise_techscout' e 'analise_critico' do CortexState;
      b) Consulta o DNA da Filosofia RS4 via RAG no ChromaDB (coleção 'decisoes');
      c) Monta o prompt do Agente 4 (agentes/agente4_sintetizador.txt);
      d) Executa chamada local ao Ollama ('qwen2.5:7b', fallback 'qwen2.5:3b');
      e) Estrutura o documento com YAML Front-Matter (PROJETO, DATA_EXECUCAO,
         MODELO_USADO, FRENTE_ALVO, STATUS);
      f) Salva o arquivo em 'drafts/refinados/';
      g) Atualiza 'sintese_final' no CortexState;
      h) Grava telemetria completa em 'Metrics/metrics_sintetizador_v2.json'.
    """
    inicio_nodo = time.perf_counter()
    estado = dict(state)

    entrada_bruta = str(estado.get("entrada_bruta") or "").strip()
    frente_alvo = str(estado.get("frente_alvo", "GERAL")).strip() or "GERAL"
    analise_mapeador = str(estado.get("analise_mapeador") or "").strip()
    analise_techscout = str(estado.get("analise_techscout") or "").strip()
    analise_critico = str(estado.get("analise_critico") or "").strip()

    agora = _agora()
    reporte: dict = {
        "proyecto": "RS4-cortex-flow v2 (Cortex-Flow V2)",
        "dose": "Item 08.5 - Nó Agente 4 (Sintetizador & Refinador)",
        "regla": "Regla CEO RS4 - Telemetria de nó LangGraph",
        "descripcion": (
            "Nó Agente 4: consolidação das análises do Mapeador, Tech Scout e Crítico "
            "+ RAG no ChromaDB (coleção 'decisoes' → DNA da Filosofia RS4) + "
            "Ollama local (qwen2.5:7b, fallback qwen2.5:3b) + "
            "YAML Front-Matter + salvamento em drafts/refinados/."
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
            "tamanho_entrada_bruta": len(entrada_bruta),
            "tamanho_analise_mapeador": len(analise_mapeador),
            "tamanho_analise_techscout": len(analise_techscout),
            "tamanho_analise_critico": len(analise_critico),
            "chaves_presentes": [k for k, v in estado.items() if str(v or "").strip()],
        },
        "rag_chromadb": {},
        "prompt_sintetizador": {},
        "ollama": {},
        "sintese_draft": {},
        "nodo": {},
        "erros": list(estado.get("erros") or []),
        "validacion": {},
    }

    # (b) RAG no ChromaDB
    texto_busca_rag = f"{entrada_bruta}\n{analise_mapeador[:200]}\n{analise_techscout[:200]}"
    rag = recuperar_contexto_rag(texto_busca_rag)
    reporte["rag_chromadb"] = rag
    contexto_rag: list = rag.get("hits") or []
    if rag.get("status") != "OK":
        reporte["erros"].append(f"RAG: {rag.get('erro')}")

    # (c) Prompt do Sintetizador
    try:
        regras = cargar_reglas_agente4()
    except Exception as exc:
        regras = REGRAS_SINTETIZADOR
        reporte["erros"].append(f"PROMPT_RULES: {type(exc).__name__}: {exc}")

    prompt = montar_prompt_sintetizador(
        regras,
        entrada_bruta,
        frente_alvo,
        analise_mapeador,
        analise_techscout,
        analise_critico,
        rag,
    )
    reporte["prompt_sintetizador"] = {
        "fonte_regras": str(CAMINHO_PROMPT_AGENTE4),
        "caracteres_prompt": len(prompt),
        "preview": prompt[:300],
    }

    # (d) Chamada local ao Ollama
    try:
        resposta_ollama, tele_ollama = chamar_ollama_com_fallback(prompt)
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
            "erro": f"{type(exc).__name__}: {exc}",
        }
        resposta_ollama = (
            "# ERRO NA SÍNTESE FINAL\n\n"
            f"[ERRO OLLAMA] O Agente 4 não obteve resposta do modelo local. Detalhe: {exc}"
        )
        modelo_usado = MODELO_PRINCIPAL
        estado_nodo = "ERRO_OLLAMA"

    # (e) Estruturação com YAML Front-Matter
    status_doc = "CONCLUIDO" if estado_nodo == "OK" else "FALHA_EXECUCAO"
    documento_final = estruturar_documento_com_frontmatter(
        resposta_ollama,
        frente_alvo=frente_alvo,
        modelo_usado=modelo_usado,
        agora=agora,
        status=status_doc,
    )

    # (f) Salva o documento final em drafts/refinados/
    caminho_sintese_md = ""
    try:
        caminho_sintese_md = salvar_sintese_markdown(documento_final, agora)
        reporte["sintese_draft"] = {
            "diretorio": str(DIR_DRAFTS_REFINADOS),
            "arquivo_markdown": Path(caminho_sintese_md).name,
            "caminho_absoluto": caminho_sintese_md,
            "carimbo_data_hora": _nome_arquivo_refinado(agora),
            "sintese_caracteres": len(documento_final),
            "status": "OK",
        }
    except Exception as exc:
        reporte["erros"].append(f"DRAFT_SAVE: {type(exc).__name__}: {exc}")
        reporte["sintese_draft"] = {
            "diretorio": str(DIR_DRAFTS_REFINADOS),
            "status": "ERROR",
            "erro": f"{type(exc).__name__}: {exc}",
        }
        estado_nodo = "ERRO_DRAFT"

    duracao_nodo_ms = round((time.perf_counter() - inicio_nodo) * 1000, 4)
    reporte["nodo"] = {
        "funcao": "nodo_sintetizador",
        "assinatura": "nodo_sintetizador(state: CortexState) -> dict",
        "duracao_total_ms": duracao_nodo_ms,
        "sintese_caracteres": len(documento_final),
        "sintese_preview": documento_final[:300],
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
        "py_compile_sintetizador": "OK" if ok_sintaxe else "ERRO",
        "nodo_estado": estado_nodo,
        "status": "SUCCESS" if sucesso else "FAILURE",
        "exit_code": 0 if sucesso else 1,
    }

    try:
        RUTA_METRICS_SINTETIZADOR.parent.mkdir(parents=True, exist_ok=True)
        RUTA_METRICS_SINTETIZADOR.write_text(
            json.dumps(reporte, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except Exception as exc:
        reporte["erros"].append(f"METRICS_WRITE: {exc}")

    return {
        "sintese_final": documento_final,
        "contexto_rag": contexto_rag,
        "caminho_sintese_md": caminho_sintese_md,
        "erros": reporte["erros"],
    }
