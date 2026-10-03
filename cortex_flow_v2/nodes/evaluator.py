# -*- coding: utf-8 -*-
"""Nó Evaluator / Avaliador (Item 08.7) — Cortex-Flow V2.

Nó LangGraph-ready que fecha o ciclo de produção com um PARECER TÉCNICO
JUSTIFICATIVO e uma NOTA PRELIMINAR de 1 a 5 sobre o entregável final das
duas rotas do grafo:

  * ROTA A — COPY_OFFER ......... rascunho de copy/oferta produzido pelo
                                 Redator Comercial ('copy_comercial' +
                                 'caminho_copy_md').
  * ROTA B — BUILDER_TEMPLATE ... síntese refinada ('sintese_final') e MVP
                                 do Builder ('codigo_mvp' +
                                 'caminho_template_md').

Fluxo do nó (degradação graciosa — nunca aborta o grafo):
  a) Detecta a rota e resgata o entregável do CortexState (com fallback
     declarado para 'analise_techscout' / 'analise_mapeador' /
     'entrada_bruta' quando o entregável esperado está vazio).
  b) Consulta a coleção 'decisoes' no ChromaDB (RAG) para recuperar os
     padrões de qualidade e critérios da Filosofia RS4 (Regra CEO RS4,
     Checklist Vivo, Quádrupla Trava, custo R$ 0,00, LGPD).
  c) Monta o prompt do Evaluator e executa o modelo local 'qwen2.5:7b' no
     Ollama (fallback seguro para 'qwen2.5:3b'), temperature=0.2,
     num_predict=1024.
  d) Extrai a NOTA PRELIMINAR (1 a 5) e a recomendação preliminar de
     governança (APROVAR | REVISAR | REJEITAR) do parecer gerado.
  e) Persiste o artefato de governança HITL em 'drafts/avaliacoes/'
     (Markdown com YAML Front-Matter + bloco de decisão humana).
  f) Atualiza 'parecer_evaluator', 'nota_preliminar', 'recomendacao_hitl' e
     'caminho_avaliacao_md' no CortexState.
  g) Telemetria (Regra CEO RS4): mede a latência exata do ChromaDB e do
     Ollama, tokens/s, nota atribuída, status e grava o relatório completo em
     'Metrics/metrics_evaluator_v2.json'.

A nota é PRELIMINAR por definição: a decisão final é sempre humana
(governança HITL — Human In The Loop).
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
MODELO_PRINCIPAL = "qwen2.5:7b"  # avaliador técnico justo, objetivo e auditável
MODELO_FALLBACK = "qwen2.5:3b"
MODELO_FALLBACKS = (MODELO_FALLBACK,)
TEMPERATURA = 0.2  # avaliação rigorosa: criatividade contida, nota reprodutível
NUM_PREDICT = 1024  # parecer estruturado e ágil na CPU local
TIMEOUT_OLLAMA_S = 240
N_RESULTADOS_RAG = 5  # mais critérios/regras do DNA para uma nota bem ancorada

DIR_RAIZ = Path(__file__).resolve().parents[2]
CHROMA_DATA_DIR_ABSOLUTO = str(DIR_RAIZ / "chroma_db_data")
DIR_DRAFTS_AVALIACOES = DIR_RAIZ / "drafts" / "avaliacoes"
CAMINHO_PROMPT_EVALUATOR = DIR_RAIZ / "agentes" / "agente6_evaluator.txt"
RUTA_METRICS_EVALUATOR = DIR_RAIZ / "Metrics" / "metrics_evaluator_v2.json"
OLLAMA_API_GENERATE = f"{OLLAMA_BASE_URL}/api/generate"

# Rotas de produção avaliadas pelo nó
ROTA_A = "ROTA_A_COPY_OFFER"
ROTA_B = "ROTA_B_BUILDER_TEMPLATE"

# Limites de contexto por componente do entregável (prompt enxuto e barato)
MAX_CARACTERES_COPY = 2500
MAX_CARACTERES_SINTESE = 2500
MAX_CARACTERES_MVP = 4000
MAX_CARACTERES_FALLBACK = 1200

# Faixa da NOTA PRELIMINAR (1 a 5) e corte de recomendação para o HITL.
# 0 = nota não identificada no parecer (evidência ausente nunca vira nota média).
NOTA_MINIMA = 1
NOTA_MAXIMA = 5
NOTA_NAO_IDENTIFICADA = 0
NOTA_MINIMA_APROVACAO = 4

# Regras embutidas (fallback) do Agente Evaluator: usadas caso
# 'agentes/agente6_evaluator.txt' não exista ou não possa ser lido — o fluxo
# degrada graciosamente, sem abortar o grafo.
REGRAS_EVALUATOR_EMBUTIDAS = (
    "Você é o AGENTE EVALUATOR / AVALIADOR DE QUALIDADE do RS4-cortex-flow.\n"
    "Sua função é avaliar o entregável final das rotas de produção (Rota A: "
    "copy/oferta; Rota B: síntese refinada + MVP do Builder) contra os padrões "
    "de qualidade e critérios da Filosofia RS4.\n\n"
    "DIRETRIZES:\n"
    "1. Seja justo, técnico e baseado em evidência: avalie apenas o que está "
    "no entregável, nunca presuma conteúdo que não existe.\n"
    "2. Aplique os critérios da Filosofia RS4 (contexto RAG): utilidade real, "
    "simplicidade radical, custo R$ 0,00, segurança, privacidade/LGPD, "
    "métricas reais, clareza e executabilidade imediata.\n"
    "3. Toda nota precisa de justificativa explícita: aponte pontos fortes, "
    "gaps concretos e o que falta para a entrega ser plena.\n"
    "4. Nunca invente dados, números, testes ou resultados que não estejam no "
    "entregável.\n"
    "5. A nota é PRELIMINAR: a decisão final é humana (governança HITL).\n"
)


def _agora() -> datetime.datetime:
    """Timestamp para telemetria e registros temporais."""
    return datetime.datetime.now()


def _nome_arquivo_avaliacao(agora: datetime.datetime) -> str:
    """Gera nome padronizado de arquivo para drafts/avaliacoes/.

    Ex.: avaliacao_20260930_143015.md
    """
    return f"avaliacao_{agora.strftime('%Y%m%d_%H%M%S')}.md"


def cargar_reglas_evaluator() -> str:
    """Lê as regras do prompt do Agente Evaluator.

    Se o arquivo 'agentes/agente6_evaluator.txt' não existir, devolve as
    regras embutidas (degradação graciosa, sem abortar o grafo).
    """
    if not CAMINHO_PROMPT_EVALUATOR.exists():
        return REGRAS_EVALUATOR_EMBUTIDAS
    texto = CAMINHO_PROMPT_EVALUATOR.read_text(encoding="utf-8").strip()
    return texto or REGRAS_EVALUATOR_EMBUTIDAS


def detectar_rota(estado: dict) -> str:
    """Determina a rota de produção do entregável a avaliar.

    Prioridade por evidência real presente no estado (nunca por suposição):
      1. 'codigo_mvp' preenchido     -> ROTA B (síntese refinada + MVP);
      2. 'copy_comercial' preenchido -> ROTA A (rascunho de copy/oferta);
      3. 'frente_alvo' == COPY_OFFER -> ROTA A (fallback declarado);
      4. caso contrário               -> ROTA B (fallback declarado sobre as
                                        análises do fluxo técnico).
    """
    if str(estado.get("codigo_mvp") or "").strip():
        return ROTA_B
    if str(estado.get("copy_comercial") or "").strip():
        return ROTA_A
    if str(estado.get("frente_alvo") or "").strip().upper() == "COPY_OFFER":
        return ROTA_A
    return ROTA_B


def _formatar_componente(chave: str, origem: str, conteudo: str, limite: int) -> dict:
    """Empacota um componente do entregável (chave, origem, tamanho, conteúdo)."""
    texto = (conteudo or "").strip()
    return {
        "chave": chave,
        "origem": origem,
        "caracteres": len(texto),
        "conteudo": texto[:limite],
    }


def extrair_entregavel(estado: dict) -> dict:
    """Resgata o entregável das duas rotas e mede o que foi realmente entregue.

    Retorna um dicionário com:
        rota               — ROTA_A_COPY_OFFER | ROTA_B_BUILDER_TEMPLATE;
        fonte              — chave(s) de estado usadas como entregável;
        fallback_usado     — True quando o entregável esperado estava vazio;
        componentes        — blocos (chave, origem, caracteres, conteúdo);
        texto              — texto consolidado enviado ao Evaluator;
        caminhos_artefato  — caminhos físicos declarados no estado (evidência);
        entregavel_ausente — True quando nenhum material pôde ser resgatado.
    """
    frente_alvo = str(estado.get("frente_alvo") or "GERAL").strip() or "GERAL"
    rota = detectar_rota(estado)
    componentes: list[dict] = []
    caminhos: list[str] = []
    fallback_usado = False

    if rota == ROTA_A:
        copy_comercial = str(estado.get("copy_comercial") or "").strip()
        if copy_comercial:
            componentes.append(
                _formatar_componente(
                    "copy_comercial",
                    "Rota A — rascunho de copy/oferta (Redator Comercial)",
                    copy_comercial,
                    MAX_CARACTERES_COPY,
                )
            )
        else:
            fallback_usado = True
        caminho_copy = str(estado.get("caminho_copy_md") or "").strip()
        if caminho_copy:
            caminhos.append(caminho_copy)
    else:
        for chave, origem, limite in (
            ("sintese_final", "Rota B — síntese refinada (Sintetizador)", MAX_CARACTERES_SINTESE),
            ("codigo_mvp", "Rota B — MVP/template do Builder (Item 08.6)", MAX_CARACTERES_MVP),
        ):
            valor = str(estado.get(chave) or "").strip()
            if valor:
                componentes.append(
                    _formatar_componente(chave, origem, valor, limite)
                )
        caminho_template = str(estado.get("caminho_template_md") or "").strip()
        if caminho_template:
            caminhos.append(caminho_template)
        if not componentes:
            fallback_usado = True

    # Fallback declarado (porta de entrada quando o entregável da rota veio
    # vazio): análises do fluxo + entrada bruta, em ordem de prioridade.
    if not componentes:
        for chave, origem in (
            ("analise_techscout", "Fallback — análise técnica do Tech Scout"),
            ("analise_mapeador", "Fallback — análise do Mapeador"),
            ("entrada_bruta", "Fallback — entrada bruta original"),
        ):
            valor = str(estado.get(chave) or "").strip()
            if valor:
                componentes.append(
                    _formatar_componente(
                        chave, origem, valor, MAX_CARACTERES_FALLBACK
                    )
                )
                break

    blocos: list[str] = []
    for comp in componentes:
        blocos.append(
            f"--- COMPONENTE: {comp['chave']} | origem: {comp['origem']} "
            f"| caracteres originais: {comp['caracteres']} ---\n{comp['conteudo']}"
        )
    texto = "\n\n".join(blocos).strip()

    return {
        "rota": rota,
        "frente_alvo": frente_alvo,
        "fonte": " + ".join(c["chave"] for c in componentes) or "indisponivel",
        "fallback_usado": fallback_usado,
        "componentes": componentes,
        "texto": texto,
        "caminhos_artefato": caminhos,
        "entregavel_ausente": not componentes,
    }


def recuperar_contexto_rag(
    entregavel: str, n_resultados: int = N_RESULTADOS_RAG
) -> dict:
    """Consulta a coleção 'decisoes' no ChromaDB e mede a latência exata.

    A query combina o entregável com um reforço de intenção para resgatar os
    PADRÕES DE QUALIDADE E CRITÉRIOS da Filosofia RS4 (Regra CEO RS4 de
    métricas/evidência, Checklist Vivo, Quádrupla Trava, custo R$ 0,00,
    privacidade/LGPD) como régua de avaliação. Em caso de falha não levanta
    exceção: devolve status 'ERROR' para que o nó continue com contexto RAG
    vazio (degradação graciosa, sem abortar o grafo).
    """
    query = (
        f"{entregavel[:400]}\nPadrões de qualidade e critérios de avaliação da "
        "Filosofia RS4: resgatar do DNA as regras de governo, Regra CEO RS4 "
        "(métricas reais, evidência de execução), Checklist Vivo, Quádrupla "
        "Trava (Segurança, Escalabilidade, Métricas, Privacidade/LGPD), "
        "critérios de êxito, custo R$ 0,00 e proteções para atribuir nota "
        "preliminar de qualidade a este entregável."
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


def montar_prompt_evaluator(regras: str, entregavel_info: dict, rag: dict) -> str:
    """Monta o prompt do Evaluator: regras + entregável da rota + DNA RS4 (RAG)."""
    hits = rag.get("hits") or []
    if hits:
        linhas = []
        for i, hit in enumerate(hits, 1):
            dist = hit.get("distancia")
            dist_str = f" (distância={dist})" if dist is not None else ""
            texto_doc = str(hit.get("documento") or "")[:450]
            linhas.append(f"  [{i}] {texto_doc}{dist_str}")
        contexto_rag = "\n".join(linhas)
    else:
        contexto_rag = (
            "  Nenhum padrão de qualidade recuperado do DNA no ChromaDB para "
            "esta avaliação. Aplique os critérios gerais da Filosofia RS4."
        )

    rota = entregavel_info.get("rota")
    descricao_rota = (
        "ROTA A — rascunho de copy/oferta (Redator Comercial)"
        if rota == ROTA_A
        else "ROTA B — síntese refinada + MVP do Builder"
    )

    return (
        "SYSTEM — AGENTE EVALUATOR / AVALIADOR DE QUALIDADE (RS4 CORTEX-FLOW):\n"
        f"{regras}\n\n"
        "--- ROTA E ENTREGÁVEL SOB AVALIAÇÃO ---\n"
        f"ROTA: {rota} ({descricao_rota})\n"
        f"FRENTE ALVO: {entregavel_info.get('frente_alvo')}\n"
        f"FONTE NO ESTADO: {entregavel_info.get('fonte')}\n"
        f"FALLBACK USADO: {entregavel_info.get('fallback_usado')}\n\n"
        "--- ENTREGÁVEL (EVIDÊNCIA REAL, SEM PRESSUPOSIÇÕES) ---\n"
        f"{entregavel_info.get('texto') or '[ENTREGÁVEL AUSENTE]'}\n\n"
        "--- CONTEXTO RAG — PADRÕES DE QUALIDADE E CRITÉRIOS DA FILOSOFIA RS4 "
        "(CHROMADB) ---\n"
        f"{contexto_rag}\n\n"
        "--- INSTRUÇÕES DE SAÍDA (OBRIGATÓRIAS) ---\n"
        "A PRIMEIRA linha da resposta deve ser exatamente:\n"
        "NOTA_PRELIMINAR: <inteiro de 1 a 5>\n\n"
        "Escala da nota (justa, dura, baseada apenas na evidência do entregável):\n"
        "  5 = entregável completo, executável, alinhado 100% ao DNA RS4.\n"
        "  4 = bom e utilizável, com ajustes menores apontados.\n"
        "  3 = parcial: falta um pilar essencial (ex.: smoke test, CTA, métricas).\n"
        "  2 = insuficiente: estrutura fraca, genérica ou não executável.\n"
        "  1 = reprovado: fora do escopo, com risco, vazio ou inventado.\n\n"
        "Depois da nota, estruture o parecer justificativo em Markdown:\n"
        "## 1. VEREDICTO PRELIMINAR\n"
        "- Uma frase objetiva justificando a nota atribuída.\n\n"
        "## 2. CRITÉRIOS AVALIADOS (EVIDÊNCIA)\n"
        "- Checklist com [x] ou [ ] para: utilidade real, simplicidade radical, "
        "custo R$ 0,00, segurança, privacidade/LGPD, métricas/evidência, "
        "clareza e executabilidade imediata.\n\n"
        "## 3. PONTOS FORTES\n"
        "- Só o que está comprovadamente presente no entregável.\n\n"
        "## 4. GAPS E DESVIOS DO DNA RS4\n"
        "- Cada gap com o impacto real e o trecho ausente/fraco.\n\n"
        "## 5. RECOMENDAÇÕES PARA A GOVERNANÇA HITL\n"
        "- Ações concretas (máximo 3) para elevar a nota na próxima rodada.\n\n"
        "Regra final: não repita o entregável, avalie-o. Não invente resultados "
        "de teste, números ou depoimentos que não estejam no material."
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

        eval_count = resposta_raw.get("eval_count") or 0
        eval_duration_ns = resposta_raw.get("eval_duration") or 0
        eval_duration_ms = (
            round(eval_duration_ns / 1e6, 2) if eval_duration_ns else None
        )
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
    raise RuntimeError(f"Todos os modelos Ollama falharam no Evaluator. {erros}")


# Padrões aceitos para extrair a NOTA PRELIMINAR do parecer (ordem de confiança).
# O primeiro padrão é o formato exigido no prompt; os demais são tolerância a
# variações comuns do modelo (ex.: "Nota: 4/5"), sem inventar nota inexistente.
PADROES_NOTA = (
    ("rotulo_preliminar", r"NOTA[_\s]*PRELIMINAR\s*[:\-=]?\s*([1-5])\b"),
    ("rotulo_nota_com_escala", r"NOTA\s*[:\-=]?\s*([1-5])\s*(?:/\s*5|de\s*5)"),
    ("escala_x_de_5", r"([1-5])\s*/\s*5\b"),
    ("rotulo_nota", r"NOTA[^\d\n]{0,30}?([1-5])\b"),
)


def extrair_nota_preliminar(parecer: str) -> tuple[int, str]:
    """Extrai a NOTA PRELIMINAR (1 a 5) do parecer do Evaluator.

    Retorna ``(nota, origem)``:
        nota   — inteiro de 1 a 5, ou ``NOTA_NAO_IDENTIFICADA`` (0) quando o
                 parecer não traz nenhuma nota reconhecível (evidência ausente
                 nunca vira nota média: fica registrada como não identificada);
        origem — nome do padrão que casou, ou 'NAO_IDENTIFICADA'.
    """
    texto = (parecer or "").strip()
    if not texto:
        return NOTA_NAO_IDENTIFICADA, "NAO_IDENTIFICADA"

    for nome_padrao, padrao in PADROES_NOTA:
        casamento = re.search(padrao, texto, flags=re.IGNORECASE)
        if casamento:
            try:
                nota = int(casamento.group(1))
            except (TypeError, ValueError):
                continue
            if NOTA_MINIMA <= nota <= NOTA_MAXIMA:
                return nota, nome_padrao

    return NOTA_NAO_IDENTIFICADA, "NAO_IDENTIFICADA"


def classificar_recomendacao_hitl(nota: int) -> str:
    """Traduz a nota preliminar em recomendação para a governança HITL.

    A recomendação é apenas um sinal de apoio: a decisão final (APROVAR /
    REVISAR / REJEITAR) é sempre humana.
    """
    if nota >= NOTA_MINIMA_APROVACAO:
        return "APROVAR"
    if nota == NOTA_MINIMA_APROVACAO - 1:
        return "REVISAR"
    return "REJEITAR"


def salvar_avaliacao_markdown(
    parecer: str,
    entregavel_info: dict,
    nota: int,
    origem_nota: str,
    recomendacao: str,
    modelo_usado: str,
    agora: datetime.datetime,
) -> str:
    """Persiste o artefato de governança HITL em 'drafts/avaliacoes/'.

    O documento Markdown traz YAML Front-Matter rastreável, a evidência
    avaliada (rota, fonte e componentes com tamanho real) e o bloco final de
    decisão humana. Retorna o caminho absoluto do arquivo gerado.
    """
    DIR_DRAFTS_AVALIACOES.mkdir(parents=True, exist_ok=True)
    caminho = DIR_DRAFTS_AVALIACOES / _nome_arquivo_avaliacao(agora)

    componentes = entregavel_info.get("componentes") or []
    linhas_componentes = "\n".join(
        f"- `{c['chave']}` ({c['caracteres']} caracteres) — {c['origem']}"
        for c in componentes
    ) or "- Nenhum componente resgatado do estado (entregável ausente)."

    caminhos = entregavel_info.get("caminhos_artefato") or []
    linhas_caminhos = "\n".join(f"- `{c}`" for c in caminhos) or (
        "- Nenhum caminho físico declarado no estado."
    )

    codigo_atual = __file__
    cabecalho = (
        "---\n"
        "titulo: Parecer do Evaluator — RS4 Cortex-Flow V2\n"
        "agente: Evaluator / Avaliador (Item 08.7)\n"
        f"rota: {entregavel_info.get('rota')}\n"
        f"frente_alvo: {entregavel_info.get('frente_alvo')}\n"
        f"fonte_avaliada: {entregavel_info.get('fonte')}\n"
        f"fallback_usado: {str(bool(entregavel_info.get('fallback_usado'))).lower()}\n"
        f"nota_preliminar: {nota}\n"
        f"origem_nota: {origem_nota}\n"
        f"recomendacao_hitl: {recomendacao}\n"
        f"modelo_avaliador: {modelo_usado}\n"
        f"criado_em: '{agora.strftime('%Y-%m-%d %H:%M:%S')}'\n"
        f"codigo_avaliador: {codigo_atual}\n"
        "status: AGUARDANDO_DECISAO_HUMANA\n"
        "---\n\n"
        "# PARECER DO EVALUATOR (AVALIADOR DE QUALIDADE)\n\n"
        f"**NOTA PRELIMINAR: {nota}/5** — recomendação preliminar: "
        f"**{recomendacao}** (a decisão final é humana).\n\n"
        "## Evidência avaliada\n\n"
        f"- Rota: `{entregavel_info.get('rota')}`\n"
        f"- Fonte no CortexState: `{entregavel_info.get('fonte')}`\n"
        f"- Fallback acionado: {bool(entregavel_info.get('fallback_usado'))}\n"
        f"- Componentes:\n{linhas_componentes}\n"
        f"- Artefatos físicos das rotas:\n{linhas_caminhos}\n\n"
        "## Parecer justificativo (modelo local)\n\n"
        f"{parecer.strip()}\n\n"
        "## Governança HITL — Decisão Humana Obrigatória\n\n"
        "- [ ] APROVAR\n"
        "- [ ] REVISAR\n"
        "- [ ] REJEITAR\n\n"
        "Aprovador: ______________________  Data: ____/____/______\n\n"
        "Observações da decisão humana:\n\n"
        "> \n"
    )

    caminho.write_text(cabecalho, encoding="utf-8")
    return str(caminho)


def nodo_evaluator(state: CortexState) -> dict:
    """Executa o Nó Evaluator / Avaliador (Item 08.7) sobre o CortexState.

    Fluxo:
      a) Detecta a rota (A: copy/oferta | B: síntese + MVP) e resgata o
         entregável do estado (com fallback declarado);
      b) Consulta RAG no ChromaDB (coleção 'decisoes') — padrões de qualidade
         e critérios da Filosofia RS4;
      c) Monta o prompt do Evaluator;
      d) Executa o modelo local 'qwen2.5:7b' no Ollama (fallback 'qwen2.5:3b');
      e) Extrai a NOTA PRELIMINAR (1 a 5) e a recomendação para o HITL;
      f) Salva o artefato de governança em 'drafts/avaliacoes/';
      g) Atualiza 'parecer_evaluator', 'nota_preliminar', 'recomendacao_hitl'
         e 'caminho_avaliacao_md' no CortexState;
      h) Grava telemetria completa em 'Metrics/metrics_evaluator_v2.json'.
    """
    inicio_nodo = time.perf_counter()
    estado = dict(state)

    # (a) Entregável das duas rotas (Rota A: copy/oferta | Rota B: síntese + MVP)
    entregavel_info = extrair_entregavel(estado)
    rota = str(entregavel_info.get("rota"))
    frente_alvo = str(entregavel_info.get("frente_alvo"))
    entregavel = str(entregavel_info.get("texto") or "")

    agora = _agora()
    reporte: dict = {
        "proyecto": "RS4-cortex-flow v2 (Cortex-Flow V2)",
        "dose": "Item 08.7 - Nó Evaluator / Avaliador",
        "regla": "Regla CEO RS4 - Telemetria de nó LangGraph",
        "descripcion": (
            "Nó Evaluator: avaliação do entregável das duas rotas (Rota A: "
            "rascunho de copy/oferta; Rota B: síntese refinada + MVP do "
            "Builder) contra os padrões de qualidade e critérios da Filosofia "
            "RS4 + RAG no ChromaDB (coleção 'decisoes') + Ollama local "
            "('qwen2.5:7b', fallback 'qwen2.5:3b') + NOTA PRELIMINAR (1 a 5) + "
            "artefato de governança HITL em drafts/avaliacoes/."
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
            "rota_detectada": rota,
            "fonte_entregavel": entregavel_info.get("fonte"),
            "fallback_usado": entregavel_info.get("fallback_usado"),
            "entregavel_ausente": entregavel_info.get("entregavel_ausente"),
            "tamanho_entregavel": len(entregavel),
            "componentes": [
                {"chave": c["chave"], "caracteres": c["caracteres"]}
                for c in (entregavel_info.get("componentes") or [])
            ],
            "caminhos_artefato": entregavel_info.get("caminhos_artefato"),
            "chaves_presentes": [k for k, v in estado.items() if str(v or "").strip()],
        },
        "rag_chromadb": {},
        "prompt_evaluator": {},
        "ollama": {},
        "avaliacao": {},
        "artefato_hitl": {},
        "nodo": {},
        "erros": list(estado.get("erros") or []),
        "validacion": {},
    }

    # (b) RAG — padrões de qualidade e critérios da Filosofia RS4
    rag = recuperar_contexto_rag(entregavel)
    reporte["rag_chromadb"] = rag
    contexto_rag: list = rag.get("hits") or []
    if rag.get("status") != "OK":
        reporte["erros"].append(f"RAG: {rag.get('erro')}")

    # (c) Prompt do Evaluator (regras do agente + entregável + DNA RS4)
    try:
        regras = cargar_reglas_evaluator()
    except (OSError, UnicodeDecodeError) as exc:
        regras = REGRAS_EVALUATOR_EMBUTIDAS
        reporte["erros"].append(f"PROMPT_RULES: {type(exc).__name__}: {exc}")
    prompt = montar_prompt_evaluator(regras, entregavel_info, rag)
    reporte["prompt_evaluator"] = {
        "fonte_regras": str(CAMINHO_PROMPT_EVALUATOR),
        "caracteres_prompt": len(prompt),
        "preview": prompt[:300],
    }

    # (d) Chamada local ao Ollama ('qwen2.5:7b' com fallback seguro)
    try:
        parecer_evaluator, tele_ollama = chamar_ollama_com_fallback(prompt)
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
        parecer_evaluator = (
            "[ERRO OLLAMA] O Nó Evaluator não obteve resposta do modelo local — "
            f"sem parecer e sem nota preliminar. Detalhe: {exc}"
        )
        modelo_usado = MODELO_PRINCIPAL
        estado_nodo = "ERRO_OLLAMA"

    # (e) NOTA PRELIMINAR (1 a 5) + recomendação para a governança HITL
    nota_preliminar, origem_nota = extrair_nota_preliminar(parecer_evaluator)
    nota_identificada = nota_preliminar != NOTA_NAO_IDENTIFICADA
    if estado_nodo == "OK" and not nota_identificada:
        estado_nodo = "ERRO_NOTA"
        reporte["erros"].append(
            "NOTA: nenhuma NOTA_PRELIMINAR (1 a 5) reconhecível no parecer gerado."
        )
    recomendacao_hitl = classificar_recomendacao_hitl(nota_preliminar)
    reporte["avaliacao"] = {
        "nota_preliminar": nota_preliminar,
        "nota_identificada": nota_identificada,
        "origem_nota": origem_nota,
        "nota_minima_aprovacao": NOTA_MINIMA_APROVACAO,
        "recomendacao_hitl": recomendacao_hitl,
        "decisao_final": "PENDENTE_HUMANO (governança HITL)",
        "parecer_caracteres": len(parecer_evaluator),
        "parecer_preview": parecer_evaluator[:400],
    }

    # (f) Artefato de governança HITL em drafts/avaliacoes/ (Markdown + carimbo)
    caminho_avaliacao_md = ""
    try:
        caminho_avaliacao_md = salvar_avaliacao_markdown(
            parecer_evaluator,
            entregavel_info,
            nota_preliminar,
            origem_nota,
            recomendacao_hitl,
            modelo_usado,
            agora,
        )
        reporte["artefato_hitl"] = {
            "diretorio": str(DIR_DRAFTS_AVALIACOES),
            "arquivo_markdown": Path(caminho_avaliacao_md).name,
            "caminho_absoluto": caminho_avaliacao_md,
            "carimbo_data_hora": _nome_arquivo_avaliacao(agora),
            "status_decisao": "AGUARDANDO_DECISAO_HUMANA",
            "nota_preliminar": nota_preliminar,
            "recomendacao_hitl": recomendacao_hitl,
            "status": "OK",
        }
    except (OSError, TypeError, ValueError) as exc:
        reporte["erros"].append(f"ARTEFATO_HITL: {type(exc).__name__}: {exc}")
        reporte["artefato_hitl"] = {
            "diretorio": str(DIR_DRAFTS_AVALIACOES),
            "status": "ERROR",
            "erro": f"{type(exc).__name__}: {exc}",
        }
        estado_nodo = "ERRO_ARTEFATO"

    duracao_nodo_ms = round((time.perf_counter() - inicio_nodo) * 1000, 4)
    reporte["nodo"] = {
        "funcao": "nodo_evaluator",
        "assinatura": "nodo_evaluator(state: CortexState) -> dict",
        "duracao_total_ms": duracao_nodo_ms,
        "rota": rota,
        "fonte_entregavel": entregavel_info.get("fonte"),
        "nota_preliminar": nota_preliminar,
        "recomendacao_hitl": recomendacao_hitl,
        "parecer_caracteres": len(parecer_evaluator),
        "parecer_preview": parecer_evaluator[:300],
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

    sucesso = (
        estado_nodo == "OK"
        and ok_sintaxe
        and bool(parecer_evaluator.strip())
        and NOTA_MINIMA <= nota_preliminar <= NOTA_MAXIMA
    )
    reporte["validacion"] = {
        "py_compile_evaluator": "OK" if ok_sintaxe else "ERRO",
        "nodo_estado": estado_nodo,
        "nota_preliminar": nota_preliminar,
        "recomendacao_hitl": recomendacao_hitl,
        "status": "SUCCESS" if sucesso else "FAILURE",
        "exit_code": 0 if sucesso else 1,
    }

    try:
        RUTA_METRICS_EVALUATOR.parent.mkdir(parents=True, exist_ok=True)
        RUTA_METRICS_EVALUATOR.write_text(
            json.dumps(reporte, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except (OSError, TypeError, ValueError) as exc:
        reporte["erros"].append(f"METRICS_WRITE: {exc}")

    return {
        "parecer_evaluator": parecer_evaluator,
        "nota_preliminar": nota_preliminar,
        "recomendacao_hitl": recomendacao_hitl,
        "caminho_avaliacao_md": caminho_avaliacao_md,
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
            "Pipeline local de processamento e auditoria de exames clínicos."
        ),
        "frente_alvo": "LAB",
        "analise_mapeador": "Mapeamento estrutural aprovado.",
        "analise_techscout": "Stack Python + SQLite + FastAPI selecionada.",
        "analise_critico": "Aprovado com reservas: timeout obrigatório no serviço local.",
        "sintese_final": (
            "# SÍNTESE FINAL E PLANO DE AÇÃO EXECUTIVO\n\n"
            "## 1. Decisão Técnica Final & Síntese Integrada\n"
            "Pipeline local (offline) em Python 3.11+ com FastAPI e SQLite.\n\n"
            "## 2. Arquitetura e Stack Selecionada (R$ 0,00)\n"
            "- Python 3.11+, FastAPI, Uvicorn, SQLite, Ollama local.\n\n"
            "## 3. MENOR PRÓXIMO PASSO (Ação Concreta <= 45 Minutos)\n"
            "Criar 'app.py' com CRUD mínimo em SQLite e endpoint de status.\n\n"
            "## 4. Checklist Vivo de Execução (Governança RS4)\n"
            "- [ ] Inicializar banco SQLite com tabela 'exames'\n"
            "- [ ] Implementar endpoint de auditoria com validação básica\n"
            "- [ ] Criar smoke test de verificação\n"
        ),
        "codigo_mvp": (
            "# TEMPLATE E CÓDIGO MVP — RS4 CORTEX-FLOW\n\n"
            "## 1. Visão Geral e Estrutura de Arquivos\n"
            "```\nrs4-auditor/\n  app.py\n  requirements.txt\n```\n\n"
            "## 2. Dependências (`requirements.txt`)\n"
            "```\nfastapi\nuvicorn\n```\n\n"
            "## 3. Código Fonte Principal (`app.py`)\n"
            "```python\ndef auditar(exame_id: int) -> dict:\n"
            "    \"\"\"Audita um exame e devolve o status consolidado.\"\"\"\n"
            "    return {\"exame_id\": exame_id, \"status\": \"pendente\"}\n```\n"
        ),
        "contexto_rag": [],
        "erros": [],
    }

    resultado = nodo_evaluator(demo)
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    nota = resultado.get("nota_preliminar")
    if (
        resultado.get("parecer_evaluator")
        and resultado.get("caminho_avaliacao_md")
        and isinstance(nota, int)
        and NOTA_MINIMA <= nota <= NOTA_MAXIMA
    ):
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(_main_demo())
