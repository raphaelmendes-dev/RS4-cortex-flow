# -*- coding: utf-8 -*-
"""Teste Unitário e Telemetria do Nó Construtor / Builder (Item 08.6).

Valida a execução do 'nodo_builder' sobre o CortexState:
  1. Leitura de 'sintese_final' (especificação técnica consolidada).
  2. Consulta RAG ao DNA da Filosofia RS4 no ChromaDB (coleção 'decisoes').
  3. Geração via modelo especialista em código: 'qwen2.5-coder:7b' (fallback: 'qwen2.5:7b').
  4. Persistência física do template/MVP em 'drafts/templates/'.
  5. Atualização das chaves 'codigo_mvp' e 'caminho_template_md'.
  6. Medição holística de telemetria: latência, tokens/s, modelo e gravação
     em 'Metrics/metrics_builder_v2.json' com status SUCCESS e exit_code 0.
  7. Compilação de sintaxe via py_compile para o nó e para o teste.

Uso:
  python cortex_flow_v2/tests/test_nodo_builder.py
"""

from __future__ import annotations

import json
import py_compile
import sys
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

from cortex_flow_v2.graph.state import CortexState
from cortex_flow_v2.nodes.builder import (
    DIR_DRAFTS_TEMPLATES,
    MODELO_FALLBACKS,
    MODELO_PRINCIPAL,
    RUTA_METRICS_BUILDER,
    nodo_builder,
)

# Síntese refinada realista vinda do Nó Sintetizador (Item 08.5)
SINTESE_SIMULADA = (
    "# SÍNTESE FINAL E PLANO DE AÇÃO EXECUTIVO\n\n"
    "## 1. Decisão Técnica Final & Síntese Integrada\n"
    "Construir um pipeline local de processamento e auditoria de exames clínicos "
    "usando Python 3.11+, FastAPI e SQLite, com execução 100% offline para privacidade e conformidade com LGPD.\n\n"
    "## 2. Arquitetura e Stack Selecionada (R$ 0,00)\n"
    "- Python 3.11+\n"
    "- FastAPI e Uvicorn para interface CLI/API rápida\n"
    "- SQLite nativo para persistência de exames e laudos\n"
    "- Ollama qwen2.5 local com timeout rígido de segurança\n\n"
    "## 3. MENOR PRÓXIMO PASSO (Ação Concreta <= 45 Minutos)\n"
    "Criar módulo 'app.py' com CRUD mínimo em SQLite e endpoint de status de auditoria de exames.\n\n"
    "## 4. Checklist Vivo de Execução (Governança RS4)\n"
    "- [ ] Inicializar banco SQLite com tabela 'exames'\n"
    "- [ ] Implementar endpoint/função de auditoria com validação básica\n"
    "- [ ] Criar smoke test de verificação\n"
)

ESTADO_TESTE_BUILDER: CortexState = {
    "entrada_bruta": "Pipeline local de processamento e auditoria de exames clínicos.",
    "frente_alvo": "LAB",
    "analise_mapeador": "Mapeamento estrutural aprovado.",
    "analise_techscout": "Stack Python + SQLite + FastAPI selecionada.",
    "analise_critico": "Aprovado com reservas: timeout obrigatório no serviço local.",
    "sintese_final": SINTESE_SIMULADA,
    "contexto_rag": [],
    "erros": [],
}


def testar_builder() -> int:
    """Executa o teste do nó builder e avalia os critérios de sucesso."""
    print("=" * 70)
    print("[INICIO] TESTE UNITARIO: NÓ CONSTRUTOR / BUILDER (ITEM 08.6)")
    print("=" * 70)

    # 1. Validação de sintaxe prévia (py_compile)
    caminho_nodo = RAIZ_PROJETO / "cortex_flow_v2" / "nodes" / "builder.py"
    caminho_teste = Path(__file__).resolve()

    try:
        py_compile.compile(str(caminho_nodo), doraise=True)
        py_compile.compile(str(caminho_teste), doraise=True)
        print("[OK] Sintaxe validada via py_compile com sucesso para nó e teste.")
    except py_compile.PyCompileError as exc:
        print(f"[ERRO] Erro de compilação de sintaxe: {exc}")
        return 1

    # 2. Execução do nó com especialista em código
    print(f"\n[INFO] Executando nodo_builder com modelo '{MODELO_PRINCIPAL}'...")
    resultado = nodo_builder(ESTADO_TESTE_BUILDER)

    codigo_mvp = resultado.get("codigo_mvp", "")
    caminho_md = resultado.get("caminho_template_md", "")
    erros = resultado.get("erros", [])
    contexto_rag = resultado.get("contexto_rag", [])

    print(f"\n[INFO] Caracteres gerados no Template/MVP: {len(codigo_mvp)}")
    print(f"[INFO] Arquivo salvo em drafts/templates: {caminho_md}")
    print(f"[INFO] Hits de contexto RAG recuperados: {len(contexto_rag)}")

    if erros:
        print(f"[ALERTA] Alertas/erros registrados durante execução: {erros}")

    # 3. Validação do arquivo persistido no disco
    print("\n[INFO] Verificando arquivo salvo no disco...")
    if not caminho_md or not Path(caminho_md).exists():
        print(f"[ERRO] FALHA: Arquivo de saída não encontrado em: {caminho_md}")
        return 1

    conteudo_disco = Path(caminho_md).read_text(encoding="utf-8")
    if len(conteudo_disco) < 200:
        print("[ERRO] FALHA: Conteúdo salvo no disco está excessivamente curto ou vazio.")
        return 1
    print(f"[OK] Arquivo verificado no disco ({len(conteudo_disco)} bytes).")

    # 4. Validação de telemetria em Metrics/metrics_builder_v2.json
    print("\n[INFO] Validando relatório de telemetria (Regra CEO RS4)...")
    if not RUTA_METRICS_BUILDER.exists():
        print(f"[ERRO] FALHA: Arquivo de métricas não encontrado: {RUTA_METRICS_BUILDER}")
        return 1

    try:
        metricas = json.loads(RUTA_METRICS_BUILDER.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[ERRO] FALHA: Erro ao decodificar JSON de métricas: {exc}")
        return 1

    status_metrics = metricas.get("validacion", {}).get("status")
    exit_code_metrics = metricas.get("validacion", {}).get("exit_code")
    py_compile_status = metricas.get("validacion", {}).get("py_compile_builder")
    nodo_estado = metricas.get("nodo", {}).get("estado")
    modelo_utilizado = metricas.get("ollama", {}).get("modelo")
    duracao_ms = metricas.get("nodo", {}).get("duracao_total_ms")
    tokens_segundo = metricas.get("ollama", {}).get("tokens_por_segundo")
    tokens_resposta = metricas.get("ollama", {}).get("tokens_resposta")

    print(f"   • status validação     : {status_metrics}")
    print(f"   • exit_code            : {exit_code_metrics}")
    print(f"   • py_compile           : {py_compile_status}")
    print(f"   • nodo_estado          : {nodo_estado}")
    print(f"   • modelo utilizado     : {modelo_utilizado}")
    print(f"   • tokens gerados       : {tokens_resposta}")
    print(f"   • tokens por segundo   : {tokens_segundo} tokens/s")
    print(f"   • duração do nó        : {duracao_ms} ms")

    modelos_aceitos = {MODELO_PRINCIPAL, *MODELO_FALLBACKS}
    sucesso = (
        status_metrics == "SUCCESS"
        and exit_code_metrics == 0
        and py_compile_status == "OK"
        and nodo_estado == "OK"
        and modelo_utilizado in modelos_aceitos
        and len(codigo_mvp) > 200
    )

    if sucesso:
        print("\n" + "=" * 70)
        print("[SUCCESS] Nó Construtor / Builder (Item 08.6) 100% VALIDADO!")
        print(f"   Métricas salvas em: {RUTA_METRICS_BUILDER}")
        print("=" * 70)
        return 0

    print("\n[ERRO] FALHA: Critérios de aceitação da telemetria não foram satisfeitos.")
    return 1


if __name__ == "__main__":
    raise SystemExit(testar_builder())
