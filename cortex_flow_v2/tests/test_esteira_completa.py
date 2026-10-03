# -*- coding: utf-8 -*-
"""Teste Integrado End-to-End da Esteira Completa — Item 13 (Fase 3).

Valida o wiring completo do Grafo V2 (Itens 09/12) executando as DUAS rotas
a partir da carga do Commerce (Item 11):

    Rota A (COPY_OFFER):        triagem -> redator -> critico -> evaluator -> END
    Rota B (BUILDER_TEMPLATE):  triagem -> mapeador -> techscout -> critico
                                -> sintetizador -> builder -> evaluator -> END

Critérios de sucesso:
  1. py_compile de todos os arquivos modificados na Fase 3 (+ orquestrador).
  2. Travas do orquestrador (Item 10): num_predict=1024 e timeout=240s.
  3. Carga do Commerce: oportunidades 'PENDENTE' disponíveis no payload.
  4. Execução real de cada rota via app.invoke(...) com Ollama local.
  5. Sequência de nós da rota comprovada pela atualização dos Metrics/*.json
     individuais de cada nó (latência por nó extraída de lá).
  6. Entregáveis preenchidos (copy/síntese/código/parecer/nota 1..5).
  7. Relatório consolidado gravado em Metrics/metrics_integracao_v2.json
     (latências por nó, tempo total e status — Regra CEO RS4).

Uso:
    python cortex_flow_v2/tests/test_esteira_completa.py [A|B|ambas]
    (padrão: ambas — cada execução preserva/mescla as rotas já concluídas
     no mesmo arquivo de métricas, permitindo rodar rota a rota)
"""

from __future__ import annotations

import datetime
import json
import os
import platform
import py_compile
import sys
import time
import urllib.request
from pathlib import Path

# Configura encoding UTF-8 com fallback seguro no stdout para Windows
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# Garante que a raiz do projeto esteja no sys.path
RAIZ_PROJETO = Path(__file__).resolve().parents[2]
if str(RAIZ_PROJETO) not in sys.path:
    sys.path.insert(0, str(RAIZ_PROJETO))

from cortex_flow_v2.graph import PAUSA_HARDWARE_S, app
from cortex_flow_v2.inbox.conector_commerce import (
    PAYLOAD_PADRAO,
    carregar_estado_commerce,
    carregar_oportunidades_pendentes,
)
from cortex_flow_v2.nodes.builder import RUTA_METRICS_BUILDER
from cortex_flow_v2.nodes.critico import RUTA_METRICS_CRITICO
from cortex_flow_v2.nodes.evaluator import RUTA_METRICS_EVALUATOR
from cortex_flow_v2.nodes.mapeador import RUTA_METRICS_AGENTE1
from cortex_flow_v2.nodes.redator import RUTA_METRICS_REDATOR
from cortex_flow_v2.nodes.sintetizador import RUTA_METRICS_SINTETIZADOR
from cortex_flow_v2.nodes.techscout import RUTA_METRICS_TECHSCOUT
from cortex_flow_v2.nodes.triagem import RUTA_METRICS_TRIAGEM

# ---------------- Constantes ----------------
DIR_RAIZ = RAIZ_PROJETO
RUTA_METRICS_INTEGRACAO = DIR_RAIZ / "Metrics" / "metrics_integracao_v2.json"
CAMINHO_PNG_GRAFO = DIR_RAIZ / "assets" / "cortex_flow_v2_graph.png"
OLLAMA_URL = os.environ.get(
    "OLLAMA_URL", "http://localhost:11434/api/generate"
)

# Arquivos modificados/criados na Fase 3 (validação de sintaxe — Item 13)
ARQUIVOS_MODIFICADOS = (
    DIR_RAIZ / "cortex_flow_v2" / "graph" / "__init__.py",
    DIR_RAIZ / "cortex_flow_v2" / "inbox" / "__init__.py",
    DIR_RAIZ / "cortex_flow_v2" / "inbox" / "conector_commerce.py",
    DIR_RAIZ / "cortex_flow_v2" / "tests" / "test_esteira_completa.py",
    DIR_RAIZ / "orquestrador_claudio.py",
)

# Definição das rotas integradas (ordem de execução + telemetria por nó)
ROTAS = {
    "A": {
        "nome": "ROTA_A_COPY_OFFER",
        "oportunidade_id": "COM-2026-001",
        "frente_esperada": "COPY_OFFER",
        "sequencia": ("triagem", "redator", "critico", "evaluator"),
        "metrics_nos": (
            ("triagem", RUTA_METRICS_TRIAGEM),
            ("redator", RUTA_METRICS_REDATOR),
            ("critico", RUTA_METRICS_CRITICO),
            ("evaluator", RUTA_METRICS_EVALUATOR),
        ),
        "chaves_obrigatorias": (
            "copy_comercial",
            "caminho_copy_md",
            "analise_critico",
            "parecer_evaluator",
            "caminho_avaliacao_md",
        ),
    },
    "B": {
        "nome": "ROTA_B_BUILDER_TEMPLATE",
        "oportunidade_id": "COM-2026-002",
        "frente_esperada": "BUILDER_TEMPLATE",
        "sequencia": (
            "triagem",
            "mapeador",
            "techscout",
            "critico",
            "sintetizador",
            "builder",
            "evaluator",
        ),
        "metrics_nos": (
            ("triagem", RUTA_METRICS_TRIAGEM),
            ("mapeador", RUTA_METRICS_AGENTE1),
            ("techscout", RUTA_METRICS_TECHSCOUT),
            ("critico", RUTA_METRICS_CRITICO),
            ("sintetizador", RUTA_METRICS_SINTETIZADOR),
            ("builder", RUTA_METRICS_BUILDER),
            ("evaluator", RUTA_METRICS_EVALUATOR),
        ),
        "chaves_obrigatorias": (
            "analise_mapeador",
            "analise_techscout",
            "analise_critico",
            "sintese_final",
            "codigo_mvp",
            "caminho_template_md",
            "parecer_evaluator",
            "caminho_avaliacao_md",
        ),
    },
}

# Limiares mínimos de conteúdo por entregável (bytes de texto real)
LIMIARES = {
    "copy_comercial": 300,
    "analise_mapeador": 200,
    "analise_techscout": 200,
    "analise_critico": 200,
    "sintese_final": 500,
    "codigo_mvp": 500,
    "parecer_evaluator": 200,
    "caminho_avaliacao_md": 10,
}
RECOMENDACOES_HITL = {"APROVAR", "REVISAR", "REJEITAR"}


# ---------------- Funções auxiliares ----------------
def _agora_iso() -> str:
    """Timestamp ISO/legível para telemetria."""
    return datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def validar_sintaxe_modificados() -> dict:
    """py_compile de todos os arquivos modificados na Fase 3 (Item 13)."""
    resultados = {}
    for arquivo in ARQUIVOS_MODIFICADOS:
        try:
            py_compile.compile(str(arquivo), doraise=True)
            resultados[str(arquivo.relative_to(DIR_RAIZ))] = "OK"
        except py_compile.PyCompileError as exc:
            resultados[str(arquivo.relative_to(DIR_RAIZ))] = f"ERRO: {exc}"
    # Sintaxe adicional: o payload do commerce precisa ser JSON válido.
    try:
        json.loads(PAYLOAD_PADRAO.read_text(encoding="utf-8"))
        resultados[str(PAYLOAD_PADRAO.relative_to(DIR_RAIZ))] = "OK"
    except (OSError, ValueError) as exc:
        resultados[str(PAYLOAD_PADRAO.relative_to(DIR_RAIZ))] = f"ERRO: {exc}"
    return resultados


def validar_travas_orquestrador() -> dict:
    """Confere as travas determinísticas do orquestrador (Item 10).

    Cap máximo de 1024 tokens (``MAX_TOKENS_POR_CHUNK``) e timeout de 240s
    (``TIMEOUT_SEGUNDOS``) por requisição ao Ollama.
    """
    # Import tardio: depende do bootstrap de sys.path feito acima.
    import orquestrador_claudio

    max_tokens = getattr(orquestrador_claudio, "MAX_TOKENS_POR_CHUNK", None)
    timeout_s = getattr(orquestrador_claudio, "TIMEOUT_SEGUNDOS", None)
    ok = max_tokens == 1024 and timeout_s == 240
    return {
        "max_tokens_por_requisicao": max_tokens,
        "timeout_s_por_requisicao": timeout_s,
        "esperado": {"max_tokens": 1024, "timeout_s": 240},
        "status": "OK" if ok else "FALHA",
    }


def health_check_ollama() -> dict:
    """Mede a API REST local do Ollama antes de executar as rotas."""
    url_versao = OLLAMA_URL.rsplit("/api/generate", 1)[0] + "/api/version"
    inicio = time.perf_counter()
    try:
        with urllib.request.urlopen(url_versao, timeout=10) as resp:
            dados = json.loads(resp.read().decode("utf-8"))
            status = resp.status
        return {
            "status_http": status,
            "versao": dados.get("version"),
            "latencia_s": round(time.perf_counter() - inicio, 4),
            "online": True,
        }
    except Exception as exc:  # noqa: BLE001 — telemetria de diagnóstico
        return {
            "status_http": None,
            "versao": None,
            "latencia_s": round(time.perf_counter() - inicio, 4),
            "online": False,
            "erro": f"{type(exc).__name__}: {exc}",
        }


def coletar_latencias_nos(metrics_nos, inicio_epoch: float) -> list[dict]:
    """Lê a latência de cada nó nos seus Metrics/*.json individuais.

    Confere também que cada arquivo foi REESCRITO durante esta execução
    (mtime >= início), comprovando que o nó realmente rodou na malha.
    """
    latencias = []
    for nome, ruta in metrics_nos:
        item = {"no": nome, "arquivo": ruta.name}
        try:
            dados = json.loads(Path(ruta).read_text(encoding="utf-8"))
            nodo = dados.get("nodo", {})
            valid = dados.get("validacion", {})
            mtime = Path(ruta).stat().st_mtime
            item.update(
                {
                    "duracao_no_ms": nodo.get("duracao_total_ms"),
                    "estado": nodo.get("estado"),
                    "exit_code": valid.get("exit_code"),
                    "fecha_hora": dados.get("fecha_hora"),
                    "atualizado_nesta_execucao": bool(mtime >= inicio_epoch - 2),
                }
            )
        except (OSError, ValueError) as exc:
            item["erro"] = f"{type(exc).__name__}: {exc}"
            item["atualizado_nesta_execucao"] = False
        latencias.append(item)
    return latencias


def validar_entregaveis(rota_key: str, resultado: dict) -> list[str]:
    """Aplica os critérios de conteúdo da rota e devolve a lista de falhas."""
    definicao = ROTAS[rota_key]
    falhas: list[str] = []

    frente = str(resultado.get("frente_alvo") or "").strip()
    if frente != definicao["frente_esperada"]:
        falhas.append(
            f"frente_alvo esperada '{definicao['frente_esperada']}' != '{frente}'"
        )

    for chave in definicao["chaves_obrigatorias"]:
        valor = str(resultado.get(chave) or "").strip()
        minimo = LIMIARES.get(chave, 1)
        if len(valor) < minimo:
            falhas.append(
                f"'{chave}' com {len(valor)} caracteres (mínimo {minimo})"
            )

    # Artefatos físicos gerados pelas rotas (rastreabilidade)
    for chave in ("caminho_copy_md", "caminho_template_md", "caminho_avaliacao_md"):
        caminho = str(resultado.get(chave) or "").strip()
        if caminho and not Path(caminho).exists():
            falhas.append(f"artefato '{chave}' não encontrado: {caminho}")

    # Governança HITL do Evaluator (nota 1..5 + recomendação válida)
    nota = resultado.get("nota_preliminar")
    if not isinstance(nota, int) or not 1 <= nota <= 5:
        falhas.append(f"nota_preliminar inválida: {nota!r}")
    recomendacao = str(resultado.get("recomendacao_hitl") or "").strip().upper()
    if recomendacao not in RECOMENDACOES_HITL:
        falhas.append(f"recomendacao_hitl inválida: {recomendacao!r}")

    return falhas


def executar_rota(rota_key: str) -> dict:
    """Executa uma rota completa do grafo a partir do Commerce e mede tudo.

    Args:
        rota_key: ``"A"`` (COPY_OFFER) ou ``"B"`` (BUILDER_TEMPLATE).

    Returns:
        dict: relatório da rota (status, latências por nó, total, falhas).
    """
    definicao = ROTAS[rota_key]
    print("-" * 78)
    print(
        f"[INFO] Executando {definicao['nome']} a partir da oportunidade "
        f"{definicao['oportunidade_id']} do payload_commerce.json"
    )
    print(f"[INFO] Sequência esperada: {' -> '.join(definicao['sequencia'])} -> END")

    estado, oportunidade = carregar_estado_commerce(
        oportunidade_id=definicao["oportunidade_id"]
    )
    entrada_bruta = estado["entrada_bruta"]
    print(f"[INFO] entrada_bruta carregada: {len(entrada_bruta)} caracteres")

    inicio_epoch = time.time()
    inicio_iso = _agora_iso()
    t0 = time.perf_counter()
    resultado = app.invoke(estado)
    duracao_total_s = round(time.perf_counter() - t0, 4)
    fim_iso = _agora_iso()

    # Latência por nó + comprovação de execução (arquivo reescrito no run)
    latencias = coletar_latencias_nos(definicao["metrics_nos"], inicio_epoch)
    nos_executados = [
        item["no"] for item in latencias if item.get("atualizado_nesta_execucao")
    ]
    sequencia_esperada = list(definicao["sequencia"])

    falhas: list[str] = []
    if nos_executados != sequencia_esperada:
        falhas.append(
            f"sequência de nós {nos_executados} != esperada {sequencia_esperada}"
        )
    falhas.extend(validar_entregaveis(rota_key, resultado))

    # Trava de hardware (Item 09): pausa de 2.0s em cada transição da rota
    pausa_total_s = round(PAUSA_HARDWARE_S * len(sequencia_esperada), 4)

    status = "SUCCESS" if not falhas else "FAILURE"
    relatorio = {
        "rota": definicao["nome"],
        "oportunidade_id": definicao["oportunidade_id"],
        "oportunidade_titulo": str(oportunidade.get("titulo") or ""),
        "frente_alvo": resultado.get("frente_alvo"),
        "inicio_iso": inicio_iso,
        "fim_iso": fim_iso,
        "duracao_total_s": duracao_total_s,
        "pausa_hardware_por_transicao_s": PAUSA_HARDWARE_S,
        "pausa_hardware_total_s": pausa_total_s,
        "sequencia_esperada": sequencia_esperada,
        "sequencia_executada": nos_executados,
        "latencias_por_no_ms": latencias,
        "entregaveis": {
            chave: len(str(resultado.get(chave) or ""))
            for chave in definicao["chaves_obrigatorias"]
        },
        "nota_preliminar": resultado.get("nota_preliminar"),
        "recomendacao_hitl": resultado.get("recomendacao_hitl"),
        "caminho_avaliacao_md": resultado.get("caminho_avaliacao_md"),
        "artefato_hitl": {
            "caminho": resultado.get("caminho_avaliacao_md"),
            "existe": bool(
                resultado.get("caminho_avaliacao_md")
                and Path(str(resultado.get("caminho_avaliacao_md"))).exists()
            ),
        },
        "erros_estado": list(resultado.get("erros") or []),
        "falhas": falhas,
        "status": status,
        "exit_code": 0 if status == "SUCCESS" else 1,
    }

    print(f"[INFO] Duração total da rota: {duracao_total_s}s "
          f"(pausas de hardware: {pausa_total_s}s)")
    if resultado.get("caminho_avaliacao_md"):
        print(f"[INFO] Artefato HITL gerado: {resultado.get('caminho_avaliacao_md')}")
    for item in latencias:
        print(
            f"   • {item['no']:<14} {item.get('duracao_no_ms')} ms "
            f"| estado={item.get('estado')} | atualizado={item.get('atualizado_nesta_execucao')}"
        )
    if falhas:
        for falha in falhas:
            print(f"[ERRO] {falha}")
    else:
        print(f"[OK] {definicao['nome']} validada com sucesso "
              f"(nota {resultado.get('nota_preliminar')}, "
              f"{resultado.get('recomendacao_hitl')})")
    return relatorio


def carregar_metricas_existentes() -> dict:
    """Carrega metrics_integracao_v2.json anterior (merge por rota)."""
    if not RUTA_METRICS_INTEGRACAO.exists():
        return {}
    try:
        dados = json.loads(RUTA_METRICS_INTEGRACAO.read_text(encoding="utf-8"))
        return dados if isinstance(dados, dict) else {}
    except (OSError, ValueError):
        return {}


def gravar_metricas_integracao(relatorio: dict) -> Path:
    """Grava o relatório consolidado em Metrics/ (Regra CEO RS4)."""
    RUTA_METRICS_INTEGRACAO.parent.mkdir(parents=True, exist_ok=True)
    RUTA_METRICS_INTEGRACAO.write_text(
        json.dumps(relatorio, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return RUTA_METRICS_INTEGRACAO


def montar_resumo(rotas_executadas: dict) -> dict:
    """Consolida latências, tempo total e status de todas as rotas registradas."""
    tempo_total = round(
        sum(r.get("duracao_total_s") or 0 for r in rotas_executadas.values()), 4
    )
    rotas_ok = sum(
        1 for r in rotas_executadas.values() if r.get("status") == "SUCCESS"
    )
    todas_ok = rotas_ok == len(rotas_executadas) and len(rotas_executadas) > 0
    return {
        "rotas_executadas": sorted(rotas_executadas),
        "rotas_com_sucesso": rotas_ok,
        "rotas_total": len(rotas_executadas),
        "tempo_total_s": tempo_total,
        "status": "SUCESSO" if todas_ok else "FALHA",
        "exit_code": 0 if todas_ok else 1,
    }


def _rotas_selecionadas(rotas: str) -> list[str]:
    """Interpreta o argumento CLI: 'A', 'B' ou 'ambas' (padrão)."""
    opcao = (rotas or "ambas").strip().upper()
    if opcao in ("A", "ROTA_A"):
        return ["A"]
    if opcao in ("B", "ROTA_B"):
        return ["B"]
    return ["A", "B"]


def testar_esteira_completa(rotas: str = "ambas") -> int:
    """Executa o teste integrado end-to-end (Item 13) e grava a telemetria.

    Args:
        rotas: ``"A"``, ``"B"`` ou ``"ambas"`` (padrão). Cada execução
            preserva/mescla as rotas já concluídas no arquivo de métricas.

    Returns:
        int: 0 quando todas as rotas executadas passam; 1 caso contrário.
    """
    print("=" * 78)
    print("[INICIO] TESTE INTEGRADO END-TO-END — FASE 3 (ITEM 13)")
    print("=" * 78)

    inicio_t0 = time.perf_counter()
    relatorio = carregar_metricas_existentes()  # merge com runs anteriores
    relatorio.update(
        {
            "proyecto": "RS4-cortex-flow v2 (Cortex-Flow V2)",
            "dose": "Fase 3 — Item 13 — Teste Integrado End-to-End",
            "regla": "Regla CEO RS4 - Medición Holística",
            "fecha_hora_execucao": _agora_iso(),
            "sistema": {
                "python": sys.version.split()[0],
                "plataforma": platform.platform(),
                "workdir": str(DIR_RAIZ),
            },
        }
    )

    # 1. py_compile de todos os arquivos modificados (Item 13)
    print("\n[INFO] Validando sintaxe (py_compile) dos arquivos modificados...")
    sintaxe = validar_sintaxe_modificados()
    for arquivo, status in sintaxe.items():
        print(f"   • {arquivo}: {status}")
    sintaxe_ok = all(v == "OK" for v in sintaxe.values())
    relatorio["validacion_py_compile"] = {
        "arquivos": sintaxe,
        "status": "OK" if sintaxe_ok else "ERRO",
    }
    if not sintaxe_ok:
        print("[ERRO] Falha de sintaxe — abortando antes de invocar o grafo.")
        relatorio["resumo"] = {"status": "FALHA_SINTAXE", "exit_code": 1}
        gravar_metricas_integracao(relatorio)
        return 1

    # 2. Travas determinísticas do orquestrador (Item 10)
    print("\n[INFO] Validando travas do orquestrador (1024 tokens / 240s)...")
    travas = validar_travas_orquestrador()
    relatorio["travas_hardware"] = {
        "pausa_entre_transicoes_s": PAUSA_HARDWARE_S,
        "orquestrador": travas,
    }
    print(
        f"   • max_tokens={travas['max_tokens_por_requisicao']} | "
        f"timeout={travas['timeout_s_por_requisicao']}s | "
        f"status={travas['status']}"
    )
    if travas["status"] != "OK":
        print("[ERRO] Travas do orquestrador fora do padrão da Fase 3.")
        relatorio["resumo"] = {"status": "FALHA_TRAVAS", "exit_code": 1}
        gravar_metricas_integracao(relatorio)
        return 1

    # 3. Carga do Commerce (Item 11)
    print("\n[INFO] Carregando oportunidades PENDENTE do payload_commerce.json...")
    pendentes = carregar_oportunidades_pendentes()
    relatorio["conector_commerce"] = {
        "payload": str(PAYLOAD_PADRAO.relative_to(DIR_RAIZ)),
        "oportunidades_pendentes": len(pendentes),
        "ids_pendentes": [str(o.get("id")) for o in pendentes],
    }
    print(f"   • pendentes: {[str(o.get('id')) for o in pendentes]}")
    selecionadas = _rotas_selecionadas(rotas)
    ids_necessarios = {ROTAS[k]["oportunidade_id"] for k in selecionadas}
    ids_disponiveis = {str(o.get("id")) for o in pendentes}
    if not ids_necessarios.issubset(ids_disponiveis):
        print(f"[ERRO] Payload sem as oportunidades {sorted(ids_necessarios)}.")
        relatorio["resumo"] = {"status": "FALHA_PAYLOAD", "exit_code": 1}
        gravar_metricas_integracao(relatorio)
        return 1

    # 4. Health check do Ollama (gate: sem LLM não há E2E real)
    saude = health_check_ollama()
    relatorio["ollama"] = saude
    print(
        f"\n[INFO] Ollama: online={saude['online']} "
        f"v{saude.get('versao')} ({saude['latencia_s']}s)"
    )
    if not saude["online"]:
        print("[ERRO] Ollama offline — teste E2E real impossível.")
        relatorio["resumo"] = {"status": "FALHA_OLLAMA_OFFLINE", "exit_code": 1}
        gravar_metricas_integracao(relatorio)
        return 1

    # 5. Execução das rotas selecionadas
    rotas_executadas = relatorio.get("rotas") or {}
    for chave in selecionadas:
        rotas_executadas[chave] = executar_rota(chave)

    # 6. Consolidação e gravação (latências, tempo total, status)
    relatorio["rotas"] = rotas_executadas
    relatorio["artefatos_hitl"] = {
        chave: rotas_executadas[chave].get("caminho_avaliacao_md")
        for chave in rotas_executadas
        if rotas_executadas[chave].get("caminho_avaliacao_md")
    }
    relatorio["resumo"] = montar_resumo(rotas_executadas)
    relatorio["resumo"]["tempo_total_esta_execucao_s"] = round(
        time.perf_counter() - inicio_t0, 4
    )
    relatorio["png_grafo"] = {
        "caminho": str(CAMINHO_PNG_GRAFO.relative_to(DIR_RAIZ)),
        "existe": CAMINHO_PNG_GRAFO.exists(),
    }
    ruta = gravar_metricas_integracao(relatorio)

    resumo = relatorio["resumo"]
    print("\n" + "=" * 78)
    print(
        "[INFO] Tempo total desta execução: "
        f"{resumo['tempo_total_esta_execucao_s']}s"
    )
    print(f"[INFO] Tempo total acumulado das rotas: {resumo['tempo_total_s']}s")
    print(
        f"[INFO] Rotas: {resumo['rotas_com_sucesso']}/{resumo['rotas_total']} OK"
    )
    print(f"[INFO] Métricas consolidadas: {ruta}")
    print("[INFO] Artefatos HITL gerados (drafts/avaliacoes/):")
    for r_chave, r_dados in rotas_executadas.items():
        print(f"   • Rota {r_chave}: {r_dados.get('caminho_avaliacao_md')}")
    if resumo["status"] == "SUCESSO":
        print("[SUCCESS] ESTEIRA COMPLETA (FASE 3) 100% VALIDADA!")
    else:
        print(
            "[ERRO] FALHA na esteira — consulte 'falhas' em "
            "Metrics/metrics_integracao_v2.json"
        )
    print("=" * 78)
    return int(resumo["exit_code"])


if __name__ == "__main__":
    argumento = sys.argv[1] if len(sys.argv) > 1 else "ambas"
    raise SystemExit(testar_esteira_completa(argumento))

