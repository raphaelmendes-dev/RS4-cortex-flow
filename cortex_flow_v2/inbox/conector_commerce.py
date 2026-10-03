# -*- coding: utf-8 -*-
"""Conector do Commerce — Item 11 (Fase 3) — Cortex-Flow V2.

Carrega as oportunidades com status 'PENDENTE' do ``payload_commerce.json``
(exatamente como especificado no checklist da Fase 3) e as converte em
``CortexState`` pronto para o ``app.invoke(...)`` do grafo.

Fluxo:

    payload_commerce.json
        └── oportunidades[].status == "PENDENTE"
                └── montar_entrada_bruta(oportunidade)   (template RS4)
                        └── estado_da_oportunidade(...)  -> CortexState

Cada oportunidade vira uma ``entrada_bruta`` no template padrão do RS4
(linha 'Frente Alvo: [X] ...'), de modo que o nó Triagem (Agente 0)
classifica deterministicamente a rota:

    frente COMMERCE  -> [X] COMMERCE -> rota A (COPY_OFFER)
    frente FREELAS   -> [X] FREELAS  -> rota B (BUILDER_TEMPLATE)

O conector é determinístico (sem LLM, sem rede) e grava sua telemetria em
``Metrics/metrics_conector_commerce_v2.json`` (Regra CEO RS4).

Uso:
    from cortex_flow_v2.inbox.conector_commerce import (
        carregar_oportunidades_pendentes,
        carregar_estado_commerce,
    )
"""

from __future__ import annotations

import datetime
import json
import py_compile
import sys
from pathlib import Path

# Bootstrap de sys.path: permite executar este arquivo diretamente
# (python cortex_flow_v2/inbox/conector_commerce.py) além do import como pacote.
RAIZ_PROJETO = Path(__file__).resolve().parents[2]
if str(RAIZ_PROJETO) not in sys.path:
    sys.path.insert(0, str(RAIZ_PROJETO))

from cortex_flow_v2.graph.state import CortexState

# ---------------- Constantes ----------------
DIR_RAIZ = Path(__file__).resolve().parents[2]
PAYLOAD_PADRAO = Path(__file__).resolve().parent / "payload_commerce.json"
RUTA_METRICS_CONECTOR = DIR_RAIZ / "Metrics" / "metrics_conector_commerce_v2.json"

STATUS_PENDENTE = "PENDENTE"

# Linha 'Frente Alvo' do template RS4 por frente do Commerce.
# Observação: a heurística do Triagem casa o marcador '[X] COMMERCE' com a
# intenção COPY_OFFER e '[X] FREELAS' com a intenção BUILDER_TEMPLATE.
MARCADOR_FRENTES = {
    "COMMERCE": "[ ] LAB | [X] COMMERCE | [ ] FREELAS | [ ] GERAL",
    "FREELAS": "[ ] LAB | [ ] COMMERCE | [X] FREELAS | [ ] GERAL",
    "PADRAO": "[ ] LAB | [X] COMMERCE | [ ] FREELAS | [ ] GERAL",
}


def carregar_payload(caminho: str | Path | None = None) -> dict:
    """Lê o ``payload_commerce.json`` e devolve o dicionário completo.

    Args:
        caminho: caminho opcional do payload. Padrão: ``payload_commerce.json``
            ao lado deste módulo (``cortex_flow_v2/inbox/``).

    Returns:
        dict: payload completo (chaves ``oportunidades``, ``origem`` etc.).

    Raises:
        FileNotFoundError: se o arquivo não existir.
        ValueError: se o JSON for inválido ou não for um dicionário.
    """
    rota = Path(caminho) if caminho else PAYLOAD_PADRAO
    texto = rota.read_text(encoding="utf-8")
    dados = json.loads(texto)
    if not isinstance(dados, dict):
        raise ValueError(f"Payload inválido (esperado objeto JSON): {rota}")
    return dados


def carregar_oportunidades_pendentes(caminho: str | Path | None = None) -> list[dict]:
    """Filtra as oportunidades com status 'PENDENTE' do payload do Commerce.

    Args:
        caminho: caminho opcional do payload (padrão: ``payload_commerce.json``).

    Returns:
        list[dict]: oportunidades pendentes, na ordem original do payload.
    """
    payload = carregar_payload(caminho)
    oportunidades = payload.get("oportunidades") or []
    return [
        dict(o)
        for o in oportunidades
        if str(o.get("status", "")).strip().upper() == STATUS_PENDENTE
    ]


def montar_entrada_bruta(oportunidade: dict) -> str:
    """Converte uma oportunidade do Commerce no template bruto padrão do RS4.

    O template inclui a linha 'Frente Alvo: [X] ...' exigida pela heurística
    determinística do nó Triagem para rotear a execução.

    Args:
        oportunidade: dicionário da oportunidade (titulo, descricao, frente...).

    Returns:
        str: entrada_bruta no template RS4.
    """
    frente = str(oportunidade.get("frente") or "COMMERCE").strip().upper()
    marcador = MARCADOR_FRENTES.get(frente, MARCADOR_FRENTES["PADRAO"])
    agora = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    titulo = str(oportunidade.get("titulo") or "").strip()
    descricao = str(oportunidade.get("descricao") or "").strip()
    canal = str(oportunidade.get("canal") or "commerce").strip()
    id_opp = str(oportunidade.get("id") or "SEM_ID").strip()
    prioridade = str(oportunidade.get("prioridade") or "MEDIA").strip()

    return (
        "1. IDENTIFICACAO & DATA\n"
        f"• Data e Hora: {agora}\n"
        f"• Origem: Commerce (payload_commerce.json | id {id_opp} | "
        f"status {STATUS_PENDENTE} | prioridade {prioridade})\n"
        f"• Frente Alvo: {marcador}\n"
        "\n"
        "2. A IDEIA BRUTA (Oportunidade de Commerce)\n"
        f"Titulo: {titulo}\n"
        f"Descricao: {descricao}\n"
        f"\nCanal: {canal}"
    )


def estado_da_oportunidade(oportunidade: dict) -> CortexState:
    """Monta o ``CortexState`` inicial de uma oportunidade do Commerce.

    Args:
        oportunidade: oportunidade pendente lida do payload.

    Returns:
        CortexState: estado com ``entrada_bruta`` preenchida e demais chaves
        inicializadas vazias (o Triagem define ``frente_alvo`` no início do
        fluxo).
    """
    return {
        "entrada_bruta": montar_entrada_bruta(oportunidade),
        "frente_alvo": "",
        "analise_mapeador": "",
        "analise_techscout": "",
        "analise_critico": "",
        "sintese_final": "",
        "codigo_mvp": "",
        "caminho_template_md": "",
        "copy_comercial": "",
        "caminho_copy_md": "",
        "parecer_evaluator": "",
        "nota_preliminar": 0,
        "recomendacao_hitl": "",
        "caminho_avaliacao_md": "",
        "contexto_rag": [],
        "erros": [],
    }


def carregar_estado_commerce(
    caminho: str | Path | None = None,
    oportunidade_id: str | None = None,
) -> tuple[CortexState, dict]:
    """Carrega uma oportunidade PENDENTE do Commerce direto no ``CortexState``.

    Args:
        caminho: caminho opcional do payload.
        oportunidade_id: id específico a carregar. Se omitido, usa a primeira
            oportunidade pendente da fila.

    Returns:
        tuple ``(estado, oportunidade)``: o estado pronto para o grafo e a
        oportunidade de origem (para rastreabilidade).

    Raises:
        FileNotFoundError: se o payload não existir.
        KeyError: se nenhuma oportunidade pendente for encontrada ou se o
            ``oportunidade_id`` solicitado não estiver pendente.
    """
    pendentes = carregar_oportunidades_pendentes(caminho)
    if not pendentes:
        raise KeyError(
            f"Nenhuma oportunidade '{STATUS_PENDENTE}' encontrada em "
            f"{caminho or PAYLOAD_PADRAO}"
        )

    if oportunidade_id is None:
        alvo = pendentes[0]
    else:
        alvo = next(
            (o for o in pendentes if str(o.get("id")) == str(oportunidade_id)),
            None,
        )
        if alvo is None:
            raise KeyError(
                f"Oportunidade '{oportunidade_id}' não está "
                f"'{STATUS_PENDENTE}' no payload."
            )
    return estado_da_oportunidade(alvo), alvo


def gravar_metricas_conector(relatorio: dict) -> Path:
    """Grava a telemetria do conector em Metrics/ (Regra CEO RS4)."""
    try:
        RUTA_METRICS_CONECTOR.parent.mkdir(parents=True, exist_ok=True)
        RUTA_METRICS_CONECTOR.write_text(
            json.dumps(relatorio, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except (OSError, TypeError, ValueError) as exc:
        relatorio.setdefault("erros", []).append(f"METRICS_WRITE: {exc}")
    return RUTA_METRICS_CONECTOR


def _main_demo() -> int:
    """Demonstração/validação do conector (uso manual no terminal)."""
    try:
        import sys as _sys

        _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    inicio = datetime.datetime.now()
    pendentes = carregar_oportunidades_pendentes()
    rotas = {}
    for opp in pendentes:
        estado = estado_da_oportunidade(opp)
        rotas[str(opp.get("id"))] = len(estado["entrada_bruta"])

    try:
        py_compile.compile(__file__, doraise=True)
        ok_sintaxe = True
    except py_compile.PyCompileError as exc:
        ok_sintaxe = False
        print(f"❌ py_compile: {exc}")

    sucesso = ok_sintaxe and len(pendentes) >= 2 and all(v > 0 for v in rotas.values())
    relatorio = {
        "proyecto": "RS4-cortex-flow v2 (Cortex-Flow V2)",
        "dose": "Fase 3 — Item 11 — Conector do Commerce",
        "regla": "Regla CEO RS4 - Telemetria de integracao",
        "fecha_hora": inicio.strftime("%Y-%m-%d %H:%M:%S"),
        "payload": str(PAYLOAD_PADRAO),
        "oportunidades_pendentes": len(pendentes),
        "ids_pendentes": [str(o.get("id")) for o in pendentes],
        "entrada_bruta_caracteres": rotas,
        "validacion": {
            "py_compile_conector": "OK" if ok_sintaxe else "ERRO",
            "status": "SUCCESS" if sucesso else "FAILURE",
            "exit_code": 0 if sucesso else 1,
        },
    }
    ruta = gravar_metricas_conector(relatorio)
    print(json.dumps(relatorio, ensure_ascii=False, indent=2))
    print(f"📊 Métricas gravadas: {ruta}")
    return 0 if sucesso else 1


if __name__ == "__main__":
    raise SystemExit(_main_demo())

