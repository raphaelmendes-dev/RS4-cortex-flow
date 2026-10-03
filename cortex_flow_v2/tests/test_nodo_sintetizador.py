# -*- coding: utf-8 -*-
"""Teste Unitário e Telemetria do Nó Sintetizador & Refinador (Item 08.5).

Valida a execução do 'nodo_sintetizador' sobre o CortexState:
  1. Consolidação de:
     - 'entrada_bruta'
     - 'analise_mapeador'
     - 'analise_techscout'
     - 'analise_critico'
  2. Consulta RAG ao DNA da Filosofia RS4 no ChromaDB (coleção 'decisoes').
  3. Geração via Ollama local ('qwen2.5:7b' com fallback p/ 'qwen2.5:3b').
  4. Presença do YAML Front-Matter obrigatório no cabeçalho:
     (PROJETO, DATA_EXECUCAO, MODELO_USADO, FRENTE_ALVO, STATUS).
  5. Persistência física do arquivo Markdown em 'drafts/refinados/'.
  6. Geração de 'Metrics/metrics_sintetizador_v2.json' com status SUCCESS e exit_code 0.
  7. Compilação de sintaxe via py_compile para o nó e para o teste.

Uso:
  python cortex_flow_v2/tests/test_nodo_sintetizador.py
"""

from __future__ import annotations

import json
import py_compile
import re
import sys
from pathlib import Path

# Configura encoding UTF-8 com fallback seguro no stdout
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# Garante que a raiz do projeto esteja no sys.path
RAIZ_PROJETO = Path(__file__).resolve().parents[2]
if str(RAIZ_PROJETO) not in sys.path:
    sys.path.insert(0, str(RAIZ_PROJETO))

from cortex_flow_v2.graph.state import CortexState
from cortex_flow_v2.nodes.sintetizador import (
    DIR_DRAFTS_REFINADOS,
    MODELO_FALLBACKS,
    MODELO_PRINCIPAL,
    RUTA_METRICS_SINTETIZADOR,
    nodo_sintetizador,
)

# Estado simulado realista vindo dos Nós 1, 2 e 3
ENTRADA_BRUTA = (
    "Desenvolver pipeline local de processamento e auditoria de exames clínicos "
    "usando Python, SQLite e IA local (Ollama), sem custos de infraestrutura ou nuvem."
)

ANALISE_MAPEADOR = (
    "ANÁLISE ESTRUTURAL — AGENTE 1 (MAPEADOR)\n"
    "- Fatos: Pipeline de exames clínicos local, SQLite, Python 3.11+, custo zero.\n"
    "- Premissas: Execução 100% offline para privacidade e conformidade com LGPD.\n"
    "- Problema Central: Orquestrar leitura de exames e parecer sem dependência de APIs pagas."
)

ANALISE_TECHSCOUT = (
    "RELATÓRIO TÉCNICO — AGENTE 2 (TECH SCOUT)\n"
    "- Stack Selecionada: Python + FastAPI/CLI, SQLite nativo, Ollama qwen2.5 local.\n"
    "- Custo: R$ 0,00 mensal. Sem Docker ou Kubernetes na v1.\n"
    "- Arquitetura: Módulos desacoplados orientados a dados (ETL local)."
)

ANALISE_CRITICO = (
    "PARECER DE AUDITORIA — AGENTE 3 (CRÍTICO ÁCIDO)\n"
    "- Veredicto: APROVADO COM RESERVAS.\n"
    "- Riscos: Latência de inferência em CPU caso modelos pesados sejam carregados.\n"
    "- Furo de Lógica: Não prever fallback caso o serviço Ollama esteja offline.\n"
    "- Recomendação Obrigatória: Timeout rígido nas chamadas e teste de contingência."
)

ESTADO_TESTE: CortexState = {
    "entrada_bruta": ENTRADA_BRUTA,
    "frente_alvo": "LAB",
    "analise_mapeador": ANALISE_MAPEADOR,
    "analise_techscout": ANALISE_TECHSCOUT,
    "analise_critico": ANALISE_CRITICO,
    "sintese_final": "",
    "contexto_rag": [],
    "erros": [],
}


def testar_sintetizador() -> int:
    """Executa o teste do nó sintetizador e avalia os critérios de sucesso."""
    print("=" * 70)
    print("[INICIO] TESTE UNITARIO: NÓ SINTETIZADOR & REFINADOR (ITEM 08.5)")
    print("=" * 70)

    # 1. Validação de sintaxe prévia (py_compile)
    caminho_nodo = RAIZ_PROJETO / "cortex_flow_v2" / "nodes" / "sintetizador.py"
    caminho_teste = Path(__file__).resolve()

    try:
        py_compile.compile(str(caminho_nodo), doraise=True)
        py_compile.compile(str(caminho_teste), doraise=True)
        print("[OK] Sintaxe validada via py_compile com sucesso para nó e teste.")
    except py_compile.PyCompileError as exc:
        print(f"[ERRO] Erro de compilação de sintaxe: {exc}")
        return 1

    # 2. Execução do nó
    print(f"\n[INFO] Executando nodo_sintetizador com modelo preferido '{MODELO_PRINCIPAL}'...")
    resultado = nodo_sintetizador(ESTADO_TESTE)

    sintese_final = resultado.get("sintese_final", "")
    caminho_md = resultado.get("caminho_sintese_md", "")
    erros = resultado.get("erros", [])
    contexto_rag = resultado.get("contexto_rag", [])

    print(f"\n[INFO] Caracteres gerados na síntese final: {len(sintese_final)}")
    print(f"[INFO] Arquivo salvo em drafts: {caminho_md}")
    print(f"[INFO] Hits de contexto RAG recuperados: {len(contexto_rag)}")

    if erros:
        print(f"[ALERTA] Alertas/erros registrados durante execução: {erros}")

    # 3. Validação do YAML Front-Matter
    print("\n[INFO] Validando YAML Front-Matter no cabeçalho...")
    front_matter_match = re.search(r"^---\s*\n([\s\S]*?)\n---", sintese_final)
    if not front_matter_match:
        print("[ERRO] FALHA: YAML Front-Matter não encontrado no início do documento.")
        return 1

    yaml_conteudo = front_matter_match.group(1)
    chaves_obrigatorias = ["PROJETO", "DATA_EXECUCAO", "MODELO_USADO", "FRENTE_ALVO", "STATUS"]
    chaves_faltantes = [k for k in chaves_obrigatorias if f"{k}:" not in yaml_conteudo]

    if chaves_faltantes:
        print(f"[ERRO] FALHA: Chaves do YAML ausentes: {chaves_faltantes}")
        return 1
    print("[OK] YAML Front-Matter validado com sucesso contendo todas as chaves obrigatórias:")
    for linha in yaml_conteudo.strip().splitlines():
        print(f"   {linha}")

    # 4. Validação da persistência do arquivo Markdown em drafts/refinados/
    print("\n[INFO] Verificando arquivo salvo no disco...")
    if not caminho_md or not Path(caminho_md).exists():
        print(f"[ERRO] FALHA: Arquivo de saída não encontrado em: {caminho_md}")
        return 1

    conteudo_disco = Path(caminho_md).read_text(encoding="utf-8")
    if conteudo_disco != sintese_final:
        print("[ERRO] FALHA: Conteúdo salvo no disco diverge do retornado pelo nó.")
        return 1
    print(f"[OK] Arquivo verificado no disco ({len(conteudo_disco)} bytes).")

    # 5. Validação de telemetria em Metrics/metrics_sintetizador_v2.json
    print("\n[INFO] Validando relatório de telemetria (Regra CEO RS4)...")
    if not RUTA_METRICS_SINTETIZADOR.exists():
        print(f"[ERRO] FALHA: Arquivo de métricas não encontrado: {RUTA_METRICS_SINTETIZADOR}")
        return 1

    try:
        metricas = json.loads(RUTA_METRICS_SINTETIZADOR.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[ERRO] FALHA: Erro ao decodificar JSON de métricas: {exc}")
        return 1

    status_metrics = metricas.get("validacion", {}).get("status")
    exit_code_metrics = metricas.get("validacion", {}).get("exit_code")
    py_compile_status = metricas.get("validacion", {}).get("py_compile_sintetizador")
    nodo_estado = metricas.get("nodo", {}).get("estado")
    modelo_utilizado = metricas.get("ollama", {}).get("modelo")
    duracao_ms = metricas.get("nodo", {}).get("duracao_total_ms")

    print(f"   • status validação     : {status_metrics}")
    print(f"   • exit_code            : {exit_code_metrics}")
    print(f"   • py_compile           : {py_compile_status}")
    print(f"   • nodo_estado          : {nodo_estado}")
    print(f"   • modelo utilizado     : {modelo_utilizado}")
    print(f"   • duração do nó        : {duracao_ms} ms")

    modelos_aceitos = {MODELO_PRINCIPAL, *MODELO_FALLBACKS}
    sucesso = (
        status_metrics == "SUCCESS"
        and exit_code_metrics == 0
        and py_compile_status == "OK"
        and nodo_estado == "OK"
        and modelo_utilizado in modelos_aceitos
        and len(sintese_final) > 200
    )

    if sucesso:
        print("\n" + "=" * 70)
        print("[SUCCESS] Nó Sintetizador & Refinador (Item 08.5) 100% VALIDADO!")
        print(f"   Métricas salvas em: {RUTA_METRICS_SINTETIZADOR}")
        print("=" * 70)
        return 0

    print("\n[ERRO] FALHA: Critérios de aceitação da telemetria não foram satisfeitos.")
    return 1


if __name__ == "__main__":
    raise SystemExit(testar_sintetizador())

