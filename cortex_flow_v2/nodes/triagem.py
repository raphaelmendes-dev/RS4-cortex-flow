# -*- coding: utf-8 -*-
"""Nó Agente 0 (Triador / Roteador Dinâmico) — Cortex-Flow V2 (Dose 2 / Fase 2).

Primer nó do grafo V2 (LangGraph-ready): clasifica a 'entrada_bruta' de forma
determinística (senza LLM / sin rede) entre duas intenções de frente:

  a) COPY_OFFER        — Copywriting / Anúncio (marketing, ofertas, ventas).
  b) BUILDER_TEMPLATE  — Freela / Vaga / Código (templates, proyectos técnicos).

A decisão rota no campo 'frente_alvo' do CortexState, de modo que os nós
seguintes (mapeador, techscout, crítico, sintetizador) saben em qual frente
operar.

Regras de classificação (heurística determinística sobre texto normalizado):
  1) Puntuación por pistas léxicas (keywords pt-BR / es / en, sin acentos).
  2) Impulso fuerte si o template traz 'Frente Alvo: [X] COMMERCE' (COPY_OFFER)
     ou 'Frente Alvo: [X] FREELAS' (BUILDER_TEMPLATE).
  3) Empate → conservar 'frente_alvo' previo si já era uma intención válida;
     em caso contrário usar INTENCAO_POR_DEFECTO.

Telemetria (Regra CEO RS4): mide a duración exacta, valida py_compile e grava
o relatório completo em Metrics/metrics_triagem_v2.json (tempo, status, exit_code).
"""

from __future__ import annotations

import datetime
import json
import platform
import py_compile
import re
import socket
import time
import unicodedata
from pathlib import Path

from cortex_flow_v2.graph.state import CortexState

# ---------------- Constantes ----------------
INTENCAO_COPY_OFFER = "COPY_OFFER"
INTENCAO_BUILDER_TEMPLATE = "BUILDER_TEMPLATE"
INTENCAO_VALIDAS = (INTENCAO_COPY_OFFER, INTENCAO_BUILDER_TEMPLATE)
INTENCAO_POR_DEFECTO = INTENCAO_BUILDER_TEMPLATE
PESO_MARCADOR_FRENTE = 3

DIR_RAIZ = Path(__file__).resolve().parents[2]
RUTA_METRICS_TRIAGEM = DIR_RAIZ / "Metrics" / "metrics_triagem_v2.json"

# Pistas de COPY_OFFER (Copywriting / Anúncio) — comparação por substring
# sobre texto normalizado (minúsculas, sem acentos).
PISTAS_COPY_OFFER: tuple[str, ...] = (
    "copy",
    "copywriting",
    "anuncio",
    "campana",  # campanha / campaña
    "oferta",
    "promocion",
    "promo",
    "marketing",
    "publicidad",
    "publicidade",
    "email marketing",
    "newsletter",
    "landing page",
    "lead magnet",
    "venta",
    "venda",
    "call to action",
    "call-to-action",
    "embudo",
    "funnel",
    "redes sociales",
    "instagram",
    "tiktok",
    "banner",
    "eslogan",
    "slogan",
    "headline",
    "producto",
    "produto",
    "cliente",
    "conversion",
    "convertir",
    "audiencia",
)

# Pistas curtas de COPY_OFFER — casadas como palavra completa (word boundary),
# para evitar falso-positivos de substring ("rapido" não deve ativar "api").
PISTAS_COPY_OFFER_CORTAS: tuple[str, ...] = (
    "cta",
    "ads",
    "post",
)

# Pistas de BUILDER_TEMPLATE (Freela / Vaga / Código).
PISTAS_BUILDER_TEMPLATE: tuple[str, ...] = (
    "freela",
    "freelance",
    "freelancer",
    "vaga",
    "empleo",
    "trabajo",
    "contratacion",
    "codigo",  # código
    "template",
    "plantilla",
    "builder",
    "no code",
    "no-code",
    "nocode",
    "low code",
    "low-code",
    "lowcode",
    "desarrollo",
    "desenvolvimento",
    "programacion",
    "programador",
    "desarrollador",
    "desenvolvedor",
    "script",
    "backend",
    "frontend",
    "fullstack",
    "front-end",
    "back-end",
    "integracion",
    "automatizacion",
    "scraping",
    "chatbot",
    "pagina web",
    "sitio web",
    "web app",
    "aplicacion web",
    "base de datos",
    "especificacion",
    "proyecto tecnico",
    "stack",
)

# Pistas curtas de BUILDER_TEMPLATE — casadas como palavra completa.
PISTAS_BUILDER_TEMPLATE_CORTAS: tuple[str, ...] = (
    "api",
    "sql",
)


def _agora() -> datetime.datetime:
    """Timestamp ISO/legível para a telemetria."""
    return datetime.datetime.now()


def normalizar_texto(texto: str) -> str:
    """Minúsculas + sem acentos + espaços colapsados.

    Unifica pt-BR ("anúncio", "código", "promoción") e es ("anuncio",
    "codigo", "promocion") para que uma única pista cubra ambas variantes.
    """
    if not texto:
        return ""
    minusculas = texto.lower()
    sem_acentos = "".join(
        c for c in unicodedata.normalize("NFD", minusculas)
        if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"\s+", " ", sem_acentos).strip()


def _pistas_detectadas(
    texto: str,
    pistas: tuple[str, ...],
    cortas: tuple[str, ...],
) -> list[str]:
    """Retorna as pistas presentes no texto (substring / word boundary)."""
    detectadas = [p for p in pistas if p in texto]
    for p in cortas:
        if re.search(rf"\b{re.escape(p)}\b", texto):
            detectadas.append(p)
    return detectadas


def _marcadores_frente(texto: str) -> list[str]:
    """Extrai os rótulos marcados com [X] no template 'Frente Alvo'.

    Ex.: 'Frente Alvo: [ ] LAB | [X] COMMERCE | [ ] GERAL.' -> ['commerce']
    """
    return [m.strip() for m in re.findall(r"\[x\]\s*([^\[\]|\n]+)", texto)]


def classificar_intencao(entrada_bruta: str, frente_alvo_previo: str = "") -> dict:
    """Classifica a entrada entre COPY_OFFER e BUILDER_TEMPLATE.

    Heurística determinística (sem LLM):
      - score_copy / score_builder: número de pistas léxicas detectadas;
      - impulso +PESO_MARCADOR_FRENTE por marcador '[X] COMMERCE' (copy) ou
        '[X] FREELAS' (builder);
      - empate: conserva 'frente_alvo_previo' se já for intenção válida,
        senão INTENCAO_POR_DEFECTO.

    Retorna um dict com 'intencao', scores e pistas detectadas (telemetria).
    """
    texto = normalizar_texto(entrada_bruta)
    marcadores = _marcadores_frente(texto)

    pistas_copy = _pistas_detectadas(
        texto, PISTAS_COPY_OFFER, PISTAS_COPY_OFFER_CORTAS
    )
    pistas_builder = _pistas_detectadas(
        texto, PISTAS_BUILDER_TEMPLATE, PISTAS_BUILDER_TEMPLATE_CORTAS
    )

    score_copy = len(pistas_copy)
    score_builder = len(pistas_builder)

    for marcador in marcadores:
        if "commerce" in marcador:
            score_copy += PESO_MARCADOR_FRENTE
        if "freela" in marcador:
            score_builder += PESO_MARCADOR_FRENTE

    if score_copy > score_builder:
        intencao = INTENCAO_COPY_OFFER
    elif score_builder > score_copy:
        intencao = INTENCAO_BUILDER_TEMPLATE
    elif frente_alvo_previo in INTENCAO_VALIDAS:
        intencao = frente_alvo_previo
    else:
        intencao = INTENCAO_POR_DEFECTO

    return {
        "intencao": intencao,
        "frente_alvo_nuevo": intencao,
        "score_copy_offer": score_copy,
        "score_builder_template": score_builder,
        "pistas_copy_detectadas": pistas_copy,
        "pistas_builder_detectadas": pistas_builder,
        "marcadores_frente_detectados": marcadores,
    }


def nodo_triagem(state: CortexState) -> dict:
    """Executa o Agente 0 (Triador / Roteador Dinâmico) sobre el CortexState.

    Analiza 'entrada_bruta', clasifica la intención (COPY_OFFER ou
    BUILDER_TEMPLATE) y actualiza 'frente_alvo' no estado.

    Retorna a atualização parcial do estado:
        {"frente_alvo": str, "erros": list}
    E registra a telemetria completa em Metrics/metrics_triagem_v2.json
    (tempo, status, exit_code).
    """
    inicio_nodo = time.perf_counter()
    estado = dict(state)
    entrada_bruta = str(estado.get("entrada_bruta", "")).strip()
    frente_alvo_previo = str(estado.get("frente_alvo", "")).strip()

    agora = _agora()
    reporte: dict = {
        "proyecto": "RS4-cortex-flow v2 (Cortex-Flow V2)",
        "dose": "Dose 2 (Fase 2) - Nó Agente 0 (Triador / Roteador Dinâmico)",
        "regla": "Regla CEO RS4 - Telemetria de nó LangGraph",
        "descripcion": (
            "Nó Agente 0: triagem determinística da entrada_bruta -> COPY_OFFER "
            "(Copywriting/Anúncio) ou BUILDER_TEMPLATE (Freela/Vaga/Código); "
            "a intenção rota no campo 'frente_alvo' do CortexState."
        ),
        "fecha_hora": agora.strftime("%Y-%m-%d %H:%M:%S"),
        "fecha_hora_iso": agora.isoformat(timespec="seconds"),
        "ambiente": {
            "python": platform.python_version(),
            "plataforma": platform.platform(),
            "maquina": socket.gethostname(),
            "workdir": str(DIR_RAIZ),
        },
        "entrada": {
            "frente_alvo_previo": frente_alvo_previo,
            "entrada_bruta_caracteres": len(entrada_bruta),
            "entrada_bruta_preview": entrada_bruta[:200],
        },
        "clasificacion": {},
        "nodo": {},
        "erros": list(estado.get("erros") or []),
        "validacion": {},
    }

    # (a) Triagem / classificação de intenção
    try:
        clasificacion = classificar_intencao(entrada_bruta, frente_alvo_previo)
        reporte["clasificacion"] = clasificacion
        intencao = str(clasificacion["intencao"])
        estado_nodo = "OK"
    except Exception as exc:
        reporte["erros"].append(f"CLASIFICAR: {type(exc).__name__}: {exc}")
        intencao = INTENCAO_POR_DEFECTO
        reporte["clasificacion"] = {
            "intencao": INTENCAO_POR_DEFECTO,
            "detalle": f"fallback por excepción: {exc}",
        }
        estado_nodo = "ERRO_CLASSIFICAO"

    duracao_nodo_ms = round((time.perf_counter() - inicio_nodo) * 1000, 4)
    reporte["nodo"] = {
        "funcao": "nodo_triagem",
        "assinatura": "nodo_triagem(state: CortexState) -> dict",
        "duracao_total_ms": duracao_nodo_ms,
        "frente_alvo_nuevo": intencao,
        "estado": estado_nodo,
    }

    # Telemetria/validação (Regra CEO RS4)
    try:
        py_compile.compile(__file__, doraise=True)
        ok_sintaxe = True
    except py_compile.PyCompileError as exc:
        ok_sintaxe = False
        reporte["erros"].append(f"PY_COMPILE: {exc}")

    suceso = estado_nodo == "OK" and ok_sintaxe
    reporte["validacion"] = {
        "py_compile_triagem": "OK" if ok_sintaxe else "ERRO",
        "nodo_estado": estado_nodo,
        "status": "SUCCESS" if suceso else "FAILURE",
        "exit_code": 0 if suceso else 1,
    }

    try:
        RUTA_METRICS_TRIAGEM.parent.mkdir(parents=True, exist_ok=True)
        RUTA_METRICS_TRIAGEM.write_text(
            json.dumps(reporte, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except (OSError, TypeError, ValueError) as exc:
        reporte["erros"].append(f"METRICS_WRITE: {exc}")

    return {
        "frente_alvo": intencao,
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
            "Ideia: anúncio de Commerce — campanha de email marketing para "
            "lançar uma oferta com copywriting persuasivo, landing page e "
            "call to action. Frente Alvo: [ ] LAB | [X] COMMERCE | [ ] GERAL. "
            "Objetivo: incrementar as vendas da tienda com promoção."
        ),
        "frente_alvo": "",
        "analise_mapeador": "",
        "analise_techscout": "",
        "analise_critico": "",
        "sintese_final": "",
        "contexto_rag": [],
        "erros": [],
    }
    resultado = nodo_triagem(demo)
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    return 0 if resultado.get("frente_alvo") in INTENCAO_VALIDAS else 1


if __name__ == "__main__":
    raise SystemExit(_main_demo())