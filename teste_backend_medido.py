# -*- coding: utf-8 -*-
"""
================================================================================
teste_backend_medido.py — TESTE DE BACKEND MEDIDO (Nova Regra CEO RS4)
================================================================================
Executa o pipeline multiagente completo do Qwen 2.5:7b (Ollama local) usando
'bruto/teste_backend.txt' e grava as medições holísticas em Metrics/:

    Metrics/metrics_teste_backend_<TIMESTAMP>.md
    Metrics/metrics_teste_backend_<TIMESTAMP>.json

Dimensões obrigatórias (Filosofia CEO RS4):
    (a) CÓDIGO/SISTEMA  -> py_compile, taxa de erro, status das saídas.
    (b) OLLAMA/MODELO   -> latência da API REST local, tempo por agente,
                           consumo/estimativa de tokens e status HTTP.
    (c) AGENTE/CLINE    -> desempenho da execução, assertividade dos testes e
                           confirmação dos artefatos gerados.

Uso:
    python teste_backend_medido.py
================================================================================
"""
import json
import os
import platform
import py_compile
import subprocess
import sys
import time
import urllib.request
from datetime import datetime

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass


RAIZ = os.path.dirname(os.path.abspath(__file__))
ARQUIVO_TESTE = "teste_backend.txt"
CAMINHO_BRUTO = os.path.join(RAIZ, "bruto", ARQUIVO_TESTE)
CAMINHO_ORQUESTRADOR = os.path.join(RAIZ, "orquestrador_claudio.py")
PASTA_METRICAS = os.path.join(RAIZ, "Metrics")
PASTA_BIBLIOTECA = os.path.join(RAIZ, "biblioteca")
OLLAMA_URL_VERSIONE = "http://localhost:11434/api/version"
BASELINE_TOTAL_S = 219.7  # Baseline v1.0.0 do pipeline completo

T0 = time.monotonic()


def log(mensagem):
    print(f"🔬 [teste_backend_medido] {mensagem}", flush=True)


def validar_sintaxe(caminho):
    try:
        py_compile.compile(caminho, doraise=True)
        return "OK"
    except py_compile.PyCompileError as erro:
        return f"ERRO: {erro}"


def medir_api_rest_ollama():
    inicio = time.monotonic()
    try:
        with urllib.request.urlopen(OLLAMA_URL_VERSIONE, timeout=10) as r:
            payload = json.loads(r.read().decode("utf-8"))
            status = r.status
            versao = payload.get("version")
        return {
            "versao_api": versao,
            "status_health_check": status,
            "latencia_api_rest_s": round(time.monotonic() - inicio, 4),
        }
    except Exception as err:
        return {
            "versao_api": None,
            "status_health_check": f"ERRO: {err}",
            "latencia_api_rest_s": round(time.monotonic() - inicio, 4),
        }


def localizar_arquivo_recente(prefixo, sufixo, pasta, criado_apos=None):
    """Localiza o arquivo 'prefixo*...sufixo' mais recente de uma pasta."""
    if not os.path.isdir(pasta):
        return None
    candidatos = [f for f in os.listdir(pasta) if f.startswith(prefixo) and f.endswith(sufixo)]
    if not candidatos:
        return None
    candidatos.sort(
        key=lambda f: os.path.getmtime(os.path.join(pasta, f)),
        reverse=True,
    )
    for nome in candidatos:
        caminho = os.path.join(pasta, nome)
        if criado_apos is None or os.path.getmtime(caminho) >= criado_apos:
            return caminho
    return None


def carregar_metricas_orquestrador():
    """Carrega o JSON de métricas que o orquestrador acabou de gravar em Metrics/."""
    caminho = localizar_arquivo_recente(
        "metrics_orquestrador_teste_backend_", ".json", PASTA_METRICAS, criado_apos=T0
    )
    if not caminho:
        return None, None
    with open(caminho, "r", encoding="utf-8") as f:
        return json.load(f), caminho


def gerar_relatorio_md(final):
    a = final["a_codigo_sistema"]
    b = final["b_ollama_modelo"]
    c = final["c_agente_cline"]
    L = []
    L.append("---")
    L.append(f"PROJETO: {final['projeto']}")
    L.append(f"REGRA: {final['regra']}")
    L.append(f"GERADO_EM: {final['gerado_em']}")
    L.append(f"TESTE: {final['teste']}")
    L.append("TAGS: #rs4machine #claudio-project #metricas-backend #ceo-rs4 #qwen2.5 #ollama")
    L.append("---")
    L.append("")
    L.append("# 📊 METRICS — TESTE BACKEND MEDIDO (Qwen 2.5:7b / Ollama)")
    L.append("")
    L.append(
        f"**Status geral:** `{c['status_geral']}` — **Pipeline:** {b['duracao_pipeline_total_s']:.2f}s "
        f"— **Agentes OK:** {a['agentes_ok']}/{a['agentes_total']}"
    )
    L.append("")

    L.append("## 1) CÓDIGO / SISTEMA")
    L.append("")
    L.append("| Métrica | Valor |")
    L.append("|---|---|")
    L.append(f"| Python | {a['python']} |")
    L.append(f"| Plataforma | {a['plataforma']} |")
    L.append(f"| Arquivo de entrada | `{a['arquivo_teste']}` |")
    L.append(f"| Entrada detectada em bruto/ | {'✅ Sim' if a['arquivo_bruto_existe'] else '❌ Não'} |")
    L.append(f"| Validação de sintaxe (py_compile) — orquestrador | {a['validacao_sintaxe_orquestrador_py_compile']} |")
    L.append(f"| Validação de sintaxe (py_compile) — runner | {a['validacao_sintaxe_runner_py_compile']} |")
    L.append(f"| Exit code do pipeline | {a['exit_code_pipeline']} |")
    L.append(f"| Status das saídas | {a['status_saida']} |")
    L.append(f"| Taxa de erro (agentes) | {a['taxa_erro_agentes']} |")
    L.append(f"| Agentes OK / total | {a['agentes_ok']} / {a['agentes_total']} |")
    L.append(f"| Artefato refinado | `{a['artefato_refinado']}` ({a['artefato_refinado_bytes']} bytes) |")
    if a.get("erro_final"):
        L.append(f"| Erro final | `{a['erro_final']}` |")
    L.append("")

    L.append("## 2) OLLAMA / MODELO")
    L.append("")
    L.append("| Métrica | Valor |")
    L.append("|---|---|")
    L.append(f"| Modelo | {b['modelo']} |")
    L.append(f"| Versão da API Ollama | {b['versao_api']} |")
    L.append(f"| Health check REST (GET /api/version) | {b['status_health_check']} |")
    L.append(f"| Latência da API REST local | {b['latencia_api_rest_s']:.4f}s |")
    L.append(f"| num_predict | {b['num_predict']} |")
    L.append(f"| Total tokens de prompt | {b['total_tokens_prompt']} |")
    L.append(f"| Total tokens de resposta | {b['total_tokens_resposta']} |")
    L.append(f"| Total duração das chamadas | {b['total_duracao_agentes_s']:.2f}s |")
    L.append(f"| Duração total do pipeline | {b['duracao_pipeline_total_s']:.2f}s |")
    L.append("")
    L.append("### Agentes — tempo de resposta, latência HTTP, tokens e status")
    L.append("")
    L.append("| Agente | Estado | Status HTTP | Latência HTTP | Duração total | Tokens prompt | Tokens resposta |")
    L.append("|---|---|---|---|---|---|---|")
    for ag in final["d_detalhe_agentes"]:
        L.append(
            f"| {ag.get('agente', 'N/D')} | {ag.get('estado', 'N/D')} "
            f"| {ag.get('status_http', 'N/D')} | {ag.get('latencia_http_s', 'N/D')} "
            f"| {ag.get('duracao_total_s', 'N/D')} "
            f"| {ag.get('tokens_prompt', 'N/D')} | {ag.get('tokens_resposta', 'N/D')} |"
        )
    L.append("")

    L.append("## 3) AGENTE / CLINE — AVALIAÇÃO HOLÍSTICA")
    L.append("")
    L.append("| Critério | Resultado |")
    L.append("|---|---|")
    L.append(f"| Desempenho da execução | {c['checklist']['desempenho']} |")
    L.append(f"| Assertividade dos testes | {c['checklist']['assertividade']} |")
    L.append(f"| Confirmação dos artefatos | {c['checklist']['artefatos']} |")
    L.append("")
    L.append("### Check-list detalhado")
    for chave, valor in c["checklist_detalhado"].items():
        L.append(f"- {chave}: {valor}")
    L.append("")
    L.append("### Avaliação qualitativa do agente executor (CLINE)")
    L.append("")
    L.append("> *(Consolidada após a revisão dos artefatos pelo agente executor.)*")
    L.append("")

    L.append("### Saída do pipeline (cauda)")
    L.append("")
    L.append("```")
    L.append(final.get("saida_pipeline_tail", "N/D"))
    L.append("```")
    if final.get("saida_pipeline_erros"):
        L.append("")
        L.append("### Erros capturados (stderr)")
        L.append("")
        L.append("```")
        L.append(final["saida_pipeline_erros"])
        L.append("```")
    return "\n".join(L)


def montar_json_final(final):
    return final


def main():
    log(f"Iniciando teste de backend medido — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # ---------- PRÉ-CONDIÇÃO (Item 03 da Regra CEO RS4) ----------
    if not os.path.exists(CAMINHO_BRUTO):
        log(f"❌ 'bruto/{ARQUIVO_TESTE}' NÃO encontrado. Abortando.")
        sys.exit(1)
    log(f"✅ '{ARQUIVO_TESTE}' presente em bruto/ ({os.path.getsize(CAMINHO_BRUTO)} bytes).")

    # ---------- (a) CÓDIGO/SISTEMA: validação de sintaxe ----------
    sintaxe_orq = validar_sintaxe(CAMINHO_ORQUESTRADOR)
    sintaxe_runner = validar_sintaxe(__file__)
    log(f"py_compile orquestrador_claudio.py -> {sintaxe_orq}")
    log(f"py_compile teste_backend_medido.py -> {sintaxe_runner}")

    # ---------- (b) OLLAMA/MODELO: latência da API REST local ----------
    rest = medir_api_rest_ollama()
    log(f"Ollama REST API {rest['versao_api']} | latência REST {rest['latencia_api_rest_s']}s")

    # ---------- EXECUÇÃO DO PIPELINE (ciclo Qwen 2.5:7b completo) ----------
    log("▶️ Executando: python orquestrador_claudio.py teste_backend.txt")
    inicio_pipeline = time.monotonic()
    try:
        proc = subprocess.run(
            [sys.executable, CAMINHO_ORQUESTRADOR, ARQUIVO_TESTE],
            cwd=RAIZ,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=1500,
        )
    except subprocess.TimeoutExpired:
        log("❌ TIMEOUT do pipeline (limite de 1500s). Abortando teste.")
        sys.exit(1)
    duracao_pipeline_s = time.monotonic() - inicio_pipeline
    log(f"🔄 Pipeline em {duracao_pipeline_s:.2f}s (exit code {proc.returncode}).")

    stdout_tail = (proc.stdout or "")[-2500:]
    stderr = (proc.stderr or "")[-1500:]

    # ---------- MÉTRICAS GRAVADAS PELO ORQUESTRADOR ----------
    dados_orq, cam_orq = carregar_metricas_orquestrador()
    if cam_orq:
        log(f"✅ JSON de métricas do orquestrador: {os.path.basename(cam_orq)}")
    else:
        log("⚠️ Nenhum JSON de métricas do orquestrador encontrado em Metrics/.")

    sec_a = (dados_orq or {}).get("a_codigo_sistema", {})
    sec_b = (dados_orq or {}).get("b_ollama_modelo", {})
    agentes = (dados_orq or {}).get("d_detalhe_agentes", [])

    agentes_ok = sum(1 for x in agentes if x.get("estado") == "OK")
    agentes_total = len(agentes)
    taxa_erro = round((agentes_total - agentes_ok) / agentes_total, 4) if agentes_total else 1.0
    status_saida = "SUCESSO" if proc.returncode == 0 else "FALHA"
    if status_saida == "SUCESSO" and agentes_total and agentes_ok < agentes_total:
        status_saida = "FALHA_PARCIAL"

    artefato_ref = localizar_arquivo_recente("Refinado_", ".md", PASTA_BIBLIOTECA, criado_apos=T0)
    artefato_ref_bytes = os.path.getsize(artefato_ref) if artefato_ref else 0

    # ---------- (c) AGENTE/CLINE: avaliação objetiva ----------
    excesso_vs_baseline = ((duracao_pipeline_s - BASELINE_TOTAL_S) / BASELINE_TOTAL_S) * 100
    desempenho = (
        "✅ DENTRO DO ESPERADO"
        if duracao_pipeline_s <= BASELINE_TOTAL_S * 1.5
        else "⚠️ ACIMA DO ESPERADO"
    )
    assertividade_itens = {
        "Pipeline encerrado com exit code 0":
            "✅ PASS" if proc.returncode == 0 else "❌ FALHOU",
        "Todos os 4 agentes responderam (estado OK)":
            "✅ PASS" if agentes_total == 4 and agentes_ok == 4 else "❌ FALHOU",
        "Saída do pipeline contém 'Concluído com Sucesso'":
            "✅ PASS" if "Concluído com Sucesso" in (proc.stdout or "") else "❌ FALHOU",
    }
    artefatos_itens = {
        "Artefato Refinado_*.md gerado em biblioteca/":
            "✅ PASS" if artefato_ref else "❌ FALHOU",
        "Artefato refinado não vazio (>0 bytes)":
            "✅ PASS" if artefato_ref_bytes > 0 else "❌ FALHOU",
        "Relatório holístico do orquestrador gravado em Metrics/":
            "✅ PASS" if cam_orq else "❌ FALHOU",
        "Latência da API REST local medida (health check)":
            "✅ PASS" if rest.get("status_health_check") == 200 else "❌ FALHOU",
    }
    assertividade = (
        "✅ ASSERTIVO" if all(v == "✅ PASS" for v in assertividade_itens.values())
        else "❌ NÃO ASSERTIVO"
    )
    artefatos_ok = (
        "✅ CONFIRMADOS" if all(v == "✅ PASS" for v in artefatos_itens.values())
        else "❌ PENDENTES"
    )

    # ---------- MONTAGEM DO RELATÓRIO FINAL ----------
    final = {
        "projeto": "RS4-cortex-flow (Claudio Project) v1.0.1",
        "regra": "Nova Regra de Filosofia CEO RS4 — Medição Holística",
        "gerado_em": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "teste": f"bruto/{ARQUIVO_TESTE}",
        "a_codigo_sistema": {
            "python": sys.version.split()[0],
            "plataforma": platform.platform(),
            "arquivo_teste": ARQUIVO_TESTE,
            "arquivo_bruto_existe": True,
            "validacao_sintaxe_orquestrador_py_compile": sintaxe_orq,
            "validacao_sintaxe_runner_py_compile": sintaxe_runner,
            "exit_code_pipeline": proc.returncode,
            "status_saida": status_saida,
            "taxa_erro_agentes": taxa_erro,
            "agentes_ok": agentes_ok,
            "agentes_total": agentes_total,
            "erros_agentes": [x.get("erro") for x in agentes if x.get("estado") != "OK"],
            "inicio_iso": sec_a.get("inicio_iso"),
            "fim_iso": sec_a.get("fim_iso"),
            "artefato_refinado": artefato_ref,
            "artefato_refinado_bytes": artefato_ref_bytes,
            "erro_final": sec_a.get("erro_final"),
        },
        "b_ollama_modelo": {
            "modelo": sec_b.get("modelo") or "qwen2.5:7b",
            "url_api_generate": sec_b.get("url_api_generate") or "http://localhost:11434/api/generate",
            "versao_api": rest["versao_api"],
            "status_health_check": rest["status_health_check"],
            "latencia_api_rest_s": rest["latencia_api_rest_s"],
            "num_predict": sec_b.get("num_predict") or 1024,
            "temperatura": 0.2,
            "total_tokens_prompt": sec_b.get("total_tokens_prompt"),
            "total_tokens_resposta": sec_b.get("total_tokens_resposta"),
            "total_duracao_agentes_s": sec_b.get("total_duracao_agentes_s") or 0.0,
            "duracao_pipeline_total_s": round(duracao_pipeline_s, 4),
            "baseline_referencia_s": BASELINE_TOTAL_S,
            "variacao_vs_baseline_pct": round(excesso_vs_baseline, 2),
        },
        "c_agente_cline": {
            "status_geral": status_saida,
            "checklist": {
                "desempenho": desempenho,
                "assertividade": assertividade,
                "artefatos": artefatos_ok,
            },
            "checklist_detalhado": {**assertividade_itens, **artefatos_itens},
        },
        "d_detalhe_agentes": agentes,
        "saida_pipeline_tail": stdout_tail,
        "saida_pipeline_erros": stderr,
    }

    # ---------- GRAVAÇÃO: Metrics/metrics_teste_backend_<TS>.md + .json ----------
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    nome_base = f"metrics_teste_backend_{ts}"
    os.makedirs(PASTA_METRICAS, exist_ok=True)
    cam_md = os.path.join(PASTA_METRICAS, nome_base + ".md")
    cam_json = os.path.join(PASTA_METRICAS, nome_base + ".json")
    with open(cam_md, "w", encoding="utf-8") as f:
        f.write(gerar_relatorio_md(final))
    with open(cam_json, "w", encoding="utf-8") as f:
        json.dump(montar_json_final(final), f, ensure_ascii=False, indent=2)

    print("=" * 78)
    print("📊 RESUMO DO TESTE BACKEND MEDIDO (CEO RS4)")
    print("=" * 78)
    print(f"  Status geral      : {status_saida}")
    print(f"  Duração pipeline  : {duracao_pipeline_s:.2f}s (baseline {BASELINE_TOTAL_S:.1f}s)")
    print(f"  Agentes OK/total  : {agentes_ok}/{agentes_total}")
    print(f"  Tokens de resposta: {sec_b.get('total_tokens_resposta')}")
    print(f"  Desempenho        : {desempenho}")
    print(f"  Assertividade     : {assertividade}")
    print(f"  Artefatos         : {artefatos_ok}")
    print(f"  Relatório         : {os.path.basename(cam_md)}")
    print("=" * 78)


if __name__ == "__main__":
    main()