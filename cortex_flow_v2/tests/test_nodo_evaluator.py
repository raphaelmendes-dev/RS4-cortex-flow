# -*- coding: utf-8 -*-
"""Teste Unitário e Telemetria do Nó Evaluator / Avaliador (Item 08.7).

Valida a execução do 'nodo_evaluator' sobre o CortexState nos dois entregáveis
das rotas de produção:

  * ROTA A (COPY_OFFER) — rascunho de copy/oferta ('copy_comercial' +
    'caminho_copy_md' produzidos pelo Redator);
  * ROTA B (BUILDER_TEMPLATE) — síntese refinada ('sintese_final') + MVP do
    Builder ('codigo_mvp' + 'caminho_template_md').

E ainda valida:
  - consulta RAG na coleção 'decisoes' (padrões de qualidade/critérios da
    Filosofia RS4 — hits com metadata tipo 'dna_filosofia');
  - chamada ao Ollama no modelo preferido 'qwen2.5:7b' com fallback
    'qwen2.5:3b';
  - NOTA PRELIMINAR de 1 a 5 extraída do parecer justificativo;
  - artefato de governança HITL persistido em 'drafts/avaliacoes/' com a nota,
    a recomendação preliminar e o bloco de decisão humana;
  - atualização de 'Metrics/metrics_evaluator_v2.json' com status SUCCESS,
    exit_code 0, py_compile OK, latência, nota e rota avaliada (Regra CEO RS4);
  - parser da nota ('extrair_nota_preliminar') contra amostras sintéticas.

Uso:
  python cortex_flow_v2/tests/test_nodo_evaluator.py
"""

from __future__ import annotations

import json
import py_compile
import sys
import time
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
from cortex_flow_v2.nodes.evaluator import (
    DIR_DRAFTS_AVALIACOES,
    MODELO_FALLBACKS,
    MODELO_PRINCIPAL,
    NOTA_NAO_IDENTIFICADA,
    ROTA_A,
    ROTA_B,
    RUTA_METRICS_EVALUATOR,
    extrair_nota_preliminar,
    nodo_evaluator,
)

# ---------------- Cenário 1: ROTA A (rascunho de copy/oferta) ----------------
COPY_COMERCIAL = (
    "# COPY COMERCIAL / ANÚNCIO\n\n"
    "**Headline:** Análises de laboratório a R$ 99/ano para a sua clínica.\n\n"
    "**Subheadline:** Menos papel, menos retrabalho, mais exames entregues.\n\n"
    "**Corpo:**\n"
    "1. Agendamento digital de pedidos de exames de rotina.\n"
    "2. Lembretes automáticos por WhatsApp para reduzir faltas.\n"
    "3. Laudos organizados em um único painel, sem planilhas paralelas.\n"
    "4. Implantação assistida em 24h, sem custo de setup.\n\n"
    "**CTA:** Agende uma demo gratuita hoje e receba o diagnóstico da sua "
    "operação.\n"
    "[TESTE-08.7-A]"
)

ESTADO_ROTA_A: CortexState = {
    "entrada_bruta": (
        "Ideia: anúncio de Commerce — campanha para lançar uma oferta de "
        "R$ 99,00 na assinatura anual da plataforma de micro-saúde "
        "laboratorial, com copywriting persuasivo e call to action."
    ),
    "frente_alvo": "COPY_OFFER",
    "copy_comercial": COPY_COMERCIAL,
    "caminho_copy_md": str(
        RAIZ_PROJETO / "drafts" / "ofertas" / "oferta_20260927_170829.md"
    ),
    "contexto_rag": [],
    "erros": [],
}

# ---------------- Cenário 2: ROTA B (síntese refinada + MVP) ----------------
SINTESE_FINAL = (
    "# SÍNTESE FINAL E PLANO DE AÇÃO EXECUTIVO\n\n"
    "## 1. Decisão Técnica Final & Síntese Integrada\n"
    "Construir um pipeline local de processamento e auditoria de exames "
    "clínicos usando Python 3.11+, FastAPI e SQLite, com execução 100% "
    "offline para privacidade e conformidade com LGPD.\n\n"
    "## 2. Arquitetura e Stack Selecionada (R$ 0,00)\n"
    "- Python 3.11+\n"
    "- FastAPI e Uvicorn\n"
    "- SQLite nativo\n"
    "- Ollama local com timeout rígido de segurança\n\n"
    "## 3. MENOR PRÓXIMO PASSO (Ação Concreta <= 45 Minutos)\n"
    "Criar módulo 'app.py' com CRUD mínimo em SQLite e endpoint de status.\n\n"
    "## 4. Checklist Vivo de Execução (Governança RS4)\n"
    "- [ ] Inicializar banco SQLite com tabela 'exames'\n"
    "- [ ] Implementar endpoint/função de auditoria com validação básica\n"
    "- [ ] Criar smoke test de verificação\n"
)

CODIGO_MVP = (
    "# TEMPLATE E CÓDIGO MVP — RS4 CORTEX-FLOW\n\n"
    "## 1. Visão Geral e Estrutura de Arquivos\n"
    "```\nrs4-auditor/\n├── app.py\n├── requirements.txt\n└── test_smoke.py\n```\n\n"
    "## 2. Dependências (`requirements.txt`)\n"
    "```\nfastapi\nuvicorn\n```\n\n"
    "## 3. Código Fonte Principal (`app.py`)\n"
    "```python\nfrom dataclasses import dataclass\n\n\n"
    "@dataclass\nclass Exame:\n    \"\"\"Exame clínico auditável.\"\"\"\n\n"
    "    exame_id: int\n    paciente: str\n    status: str = \"pendente\"\n\n\n"
    "def auditar(exame: Exame) -> dict:\n"
    "    \"\"\"Audita um exame e devolve o status consolidado.\"\"\"\n"
    "    if not exame.paciente:\n"
    "        raise ValueError(\"Paciente obrigatório para auditoria.\")\n"
    "    return {\"exame_id\": exame.exame_id, \"status\": exame.status}\n```\n\n"
    "## 4. Como Executar (Guia Rápido em 3 Passos)\n"
    "1. `pip install -r requirements.txt`\n"
    "2. `uvicorn app:app --reload`\n"
    "3. `python test_smoke.py`\n"
)

ESTADO_ROTA_B: CortexState = {
    "entrada_bruta": "Pipeline local de processamento e auditoria de exames clínicos.",
    "frente_alvo": "LAB",
    "analise_mapeador": "Mapeamento estrutural aprovado.",
    "analise_techscout": "Stack Python + SQLite + FastAPI selecionada.",
    "analise_critico": "Aprovado com reservas: timeout obrigatório no serviço local.",
    "sintese_final": SINTESE_FINAL,
    "codigo_mvp": CODIGO_MVP,
    "caminho_template_md": str(
        RAIZ_PROJETO / "drafts" / "templates" / "template_mvp_20260928_122408.md"
    ),
    "contexto_rag": [],
    "erros": [],
}


def testar_parser_notas() -> tuple[bool, list[str]]:
    """Valida o parser da NOTA PRELIMINAR contra amostras sintéticas.

    Garante que o nó nunca invente nota: formatos reconhecíveis são lidos e
    um parecer sem nota volta como NOTA_NAO_IDENTIFICADA (0).
    """
    amostras = (
        ("NOTA_PRELIMINAR: 5\n## 1. VEREDICTO", 5),
        ("nota preliminar = 3\n\n## 1. VEREDICTO", 3),
        ("## Veredicto\nNota: 4/5 — bom e utilizável.", 4),
        ("Avaliação: 2 / 5 (estrutura fraca).", 2),
        ("Nota atribuída: 1 — reprovado por risco.", 1),
        ("Parecer sem nota explícita nenhuma.", NOTA_NAO_IDENTIFICADA),
    )
    falhas: list[str] = []
    for parecer, esperado in amostras:
        obtido, origem = extrair_nota_preliminar(parecer)
        print(
            f"   • parser nota: esperado={esperado} obtido={obtido} "
            f"(origem={origem})"
        )
        if obtido != esperado:
            falhas.append(f"parser: {parecer[:40]!r} -> {obtido} != {esperado}")
    return (not falhas), falhas


def _executar_cenario(nome: str, estado: CortexState, rota_esperada: str) -> dict:
    """Executa o nó para um cenário e imprime um resumo compacto com telemetria."""
    print("=" * 78)
    print(f"CENÁRIO: {nome}")
    print("=" * 78)

    inicio = time.perf_counter()
    estado_atualizado = nodo_evaluator(estado)
    latencia_cenario_ms = round((time.perf_counter() - inicio) * 1000, 4)

    parecer = str(estado_atualizado.get("parecer_evaluator") or "")
    nota = estado_atualizado.get("nota_preliminar")
    recomendacao = estado_atualizado.get("recomendacao_hitl")
    caminho_md = str(estado_atualizado.get("caminho_avaliacao_md") or "")
    contexto = estado_atualizado.get("contexto_rag") or []
    erros = estado_atualizado.get("erros") or []

    print(f"✔ parecer_evaluator retornado  -> {len(parecer)} caracteres")
    print(f"✔ nota_preliminar atribuída    -> {nota}/5")
    print(f"✔ recomendacao_hitl            -> {recomendacao}")
    print(f"✔ contexto_rag retornado       -> {len(contexto)} resultado(s)")
    for i, hit in enumerate(contexto, 1):
        meta = hit.get("metadata") or {}
        print(
            f"   [{i}] id={hit.get('id')} tipo={meta.get('tipo')} "
            f"distância={hit.get('distancia')}"
        )
    print(f"✔ artefato HITL                -> {caminho_md}")
    print(f"✔ latência do cenário          -> {latencia_cenario_ms} ms")
    if erros:
        print(f"⚠ erros registrados no estado: {erros}")

    artefato_ok = bool(caminho_md) and Path(caminho_md).exists()
    if not artefato_ok:
        print(f"[ERRO] FALHA: artefato HITL não encontrado em: {caminho_md}")
    else:
        conteudo = Path(caminho_md).read_text(encoding="utf-8")
        if len(conteudo) < 300 or "Governança HITL" not in conteudo:
            artefato_ok = False
            print("[ERRO] FALHA: artefato HITL incompleto (sem bloco de decisão).")

    print("\n→ Trecho inicial do parecer do Evaluator:")
    print("-" * 78)
    print(parecer[:900])
    print("-" * 78)

    return {
        "estado": estado_atualizado,
        "parecer": parecer,
        "nota": nota,
        "recomendacao": recomendacao,
        "caminho_md": caminho_md,
        "artefato_ok": artefato_ok,
        "contexto": contexto,
        "rota_esperada": rota_esperada,
        "latencia_cenario_ms": latencia_cenario_ms,
    }


def main() -> int:
    """Executa o teste unitário do nó e devolve 0 (SUCCESS) ou 1 (FAILURE)."""
    print("=" * 78)
    print("TESTE UNITÁRIO — NÓ EVALUATOR / AVALIADOR (Item 08.7)")
    print("=" * 78)

    falhas: list[str] = []

    # 1) Validação de sintaxe (py_compile) do nó e do próprio teste
    caminho_nodo = RAIZ_PROJETO / "cortex_flow_v2" / "nodes" / "evaluator.py"
    caminho_teste = Path(__file__).resolve()
    print("\n[INFO] Validando sintaxe com py_compile (nó + teste)...")
    for rotulo, caminho in (("evaluator.py", caminho_nodo), ("teste", caminho_teste)):
        try:
            py_compile.compile(str(caminho), doraise=True)
            print(f"[OK] py_compile {rotulo}: {caminho}")
        except py_compile.PyCompileError as exc:
            falhas.append(f"py_compile {rotulo}: {exc}")
            print(f"[ERRO] py_compile {rotulo}: {exc}")
    if falhas:
        print("\n[ERRO] FALHA: sintaxe inválida — execução abortada.")
        return 1

    # 2) Parser da NOTA PRELIMINAR (unidade pura, sem Ollama)
    print("\n[INFO] Validando parser da NOTA PRELIMINAR (amostras sintéticas)...")
    parser_ok, falhas_parser = testar_parser_notas()
    falhas.extend(falhas_parser)
    print(
        f"[{'OK' if parser_ok else 'ERRO'}] parser da nota: "
        f"{'todos os formatos reconhecidos' if parser_ok else 'divergências'}"
    )

    # 3) Cenário ROTA A — rascunho de copy/oferta (Redator)
    cenario_a = _executar_cenario(
        f"ROTA A — rascunho de copy/oferta (frente COPY_OFFER) → {ROTA_A}",
        ESTADO_ROTA_A,
        ROTA_A,
    )

    # 4) Cenário ROTA B — síntese refinada + MVP do Builder (último: define as métricas)
    cenario_b = _executar_cenario(
        f"ROTA B — síntese refinada + MVP do Builder → {ROTA_B}",
        ESTADO_ROTA_B,
        ROTA_B,
    )

    # 5) Telemetria (Regra CEO RS4) — relatório do último cenário executado
    if not RUTA_METRICS_EVALUATOR.exists():
        print(f"\n[ERRO] FALHA: métricas não encontradas: {RUTA_METRICS_EVALUATOR}")
        return 1
    try:
        metricas = json.loads(RUTA_METRICS_EVALUATOR.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"[ERRO] FALHA: erro ao decodificar JSON de métricas: {exc}")
        return 1

    validacion = metricas.get("validacion", {})
    avaliacao = metricas.get("avaliacao", {})
    nodo_metrics = metricas.get("nodo", {})
    ollama_metrics = metricas.get("ollama", {})
    artefato = metricas.get("artefato_hitl", {})
    entrada_metrics = metricas.get("entrada", {})

    status_metrics = validacion.get("status")
    exit_code_metrics = validacion.get("exit_code")
    py_compile_state = validacion.get("py_compile_evaluator")
    nodo_estado = validacion.get("nodo_estado")
    nota_metrics = avaliacao.get("nota_preliminar")
    recomendacao_metrics = avaliacao.get("recomendacao_hitl")
    modelo_usado = ollama_metrics.get("modelo")
    tokens_segundo = ollama_metrics.get("tokens_por_segundo")
    tokens_resposta = ollama_metrics.get("tokens_resposta")
    duracao_ms = nodo_metrics.get("duracao_total_ms")
    rota_metrics = entrada_metrics.get("rota_detectada")
    rag_total = nodo_metrics.get("contexto_rag_total")
    caminho_artefato = artefato.get("caminho_absoluto")

    print(f"\n📊 {RUTA_METRICS_EVALUATOR.name} (último cenário = Rota B):")
    print(f"   status validação       : {status_metrics}")
    print(f"   exit_code              : {exit_code_metrics}")
    print(f"   py_compile_evaluator   : {py_compile_state}")
    print(f"   nodo_estado            : {nodo_estado}")
    print(f"   rota avaliada          : {rota_metrics}")
    print(f"   nota preliminar        : {nota_metrics}/5")
    print(f"   recomendação HITL      : {recomendacao_metrics}")
    print(f"   modelo utilizado       : {modelo_usado}")
    print(f"   tokens gerados         : {tokens_resposta}")
    print(f"   tokens por segundo     : {tokens_segundo} tokens/s")
    print(f"   duração do nó          : {duracao_ms} ms")
    print(f"   contexto RAG (hits)    : {rag_total}")
    print(f"   artefato HITL          : {artefato.get('arquivo_markdown')}")
    print(f"   status decisão         : {artefato.get('status_decisao')}")
    print(
        "   latência RAG (ms)      : "
        f"{metricas.get('rag_chromadb', {}).get('latencia_ms')}"
    )
    print(f"   latência cenário A (ms): {cenario_a['latencia_cenario_ms']}")
    print(f"   latência cenário B (ms): {cenario_b['latencia_cenario_ms']}")

    def _tem_dna(hits: list) -> bool:
        """True se ao menos um hit do RAG traz DNA da Filosofia RS4."""
        return any(
            (h.get("metadata") or {}).get("tipo") == "dna_filosofia" for h in hits
        )

    modelos_aceitos = {MODELO_PRINCIPAL, *MODELO_FALLBACKS}
    notas_validas = all(
        isinstance(c["nota"], int) and 1 <= c["nota"] <= 5
        for c in (cenario_a, cenario_b)
    )

    criterios = {
        "parser_nota": parser_ok,
        "parecer_rota_a": bool(cenario_a["parecer"].strip()),
        "parecer_rota_b": bool(cenario_b["parecer"].strip()),
        "notas_1_a_5_ambos_cenarios": notas_validas,
        "rag_rota_a": bool(cenario_a["contexto"]) and _tem_dna(cenario_a["contexto"]),
        "rag_rota_b": bool(cenario_b["contexto"]) and _tem_dna(cenario_b["contexto"]),
        "artefato_hitl_rota_a": cenario_a["artefato_ok"],
        "artefato_hitl_rota_b": cenario_b["artefato_ok"],
        "rota_gravada_no_artefato": (
            _rota_do_artefato(cenario_a) == ROTA_A
            and _rota_do_artefato(cenario_b) == ROTA_B
        ),
        "metrics_status_success": status_metrics == "SUCCESS",
        "metrics_exit_code_0": exit_code_metrics == 0,
        "metrics_py_compile_ok": py_compile_state == "OK",
        "metrics_nodo_estado_ok": nodo_estado == "OK",
        "metrics_nota_valida": isinstance(nota_metrics, int)
        and 1 <= nota_metrics <= 5,
        "metrics_rota_b": rota_metrics == ROTA_B,
        "metrics_modelo_aceito": modelo_usado in modelos_aceitos,
        "metrics_latencia_numerica": isinstance(duracao_ms, (int, float)),
        "metrics_artefato_persistido": bool(caminho_artefato)
        and Path(str(caminho_artefato)).exists(),
        "metrics_status_decisao": str(artefato.get("status_decisao", "")).startswith(
            "AGUARDANDO"
        ),
        "diretorio_avaliacoes": DIR_DRAFTS_AVALIACOES.is_dir(),
    }
    print("\nCRITÉRIOS DE ACEITAÇÃO (Item 08.7):")
    for nome_criterio, ok in criterios.items():
        print(f"   [{'x' if ok else ' '}] {nome_criterio}")
    falhas.extend(k for k, v in criterios.items() if not v)

    print("\n" + "=" * 78)
    if not falhas:
        print(
            "✅ SUCCESS — Nó Evaluator / Avaliador (Item 08.7) validado: "
            "entregáveis das ROTAS A e B avaliados, RAG do DNA RS4 via "
            "'decisoes', parecer justificativo + NOTA PRELIMINAR via Ollama "
            f"({modelo_usado}), artefato HITL em drafts/avaliacoes/ e "
            f"{RUTA_METRICS_EVALUATOR.name} com status SUCCESS e exit_code 0."
        )
        print("=" * 78)
        return 0

    print("❌ FAILURE — critérios de validação não atendidos:")
    for falha in falhas:
        print(f"   • {falha}")
    print("=" * 78)
    return 1


def _rota_do_artefato(cenario: dict) -> str:
    """Lê a rota gravada no YAML Front-Matter do artefato HITL do cenário."""
    caminho = cenario.get("caminho_md")
    if not caminho or not Path(str(caminho)).exists():
        return ""
    for linha in Path(str(caminho)).read_text(encoding="utf-8").splitlines():
        if linha.startswith("rota:"):
            return linha.split(":", 1)[1].strip()
    return ""


if __name__ == "__main__":
    raise SystemExit(main())
