# -*- coding: utf-8 -*-
"""Grafo V2 — Cortex-Flow V2 (build LangGraph + exportação visual).

Monta o ``StateGraph`` oficial do Cortex-Flow V2 (Fase 3 — Item 12) unindo
as duas rotas de produção até o Evaluator:

    ROTA A (COPY_OFFER):
        START -> triagem -> redator -> critico -> evaluator -> END

    ROTA B (BUILDER_TEMPLATE):
        START -> triagem -> mapeador -> techscout -> critico
                -> sintetizador -> builder -> evaluator -> END

O roteamento é determinístico em dois pontos (sem LLM):

    * pós-``triagem``: lê ``frente_alvo`` classificada pelo Agente 0;
    * pós-``critico``: o nó ``critico`` é compartilhado pelas duas rotas,
      então o segundo roteador decide entre ``evaluator`` (rota A) e
      ``sintetizador`` (rota B).

TRAVA DE HARDWARE (Item 09): cada nó é envolvido por um wrapper que executa
``time.sleep(PAUSA_HARDWARE_S)`` (= 2.0 s) logo após o retorno, pausando de
forma determinística e reproduzível exatamente na transição para o próximo
nó (mesma pausa entre os passos do modelo local, aliviando pico de CPU/RAM).

O módulo expõe duas utilidades públicas:

    * ``app``                — grafo compilado (use ``app.get_graph()`` para
                               inspecionar e ``app.invoke(...)`` para executar).
    * ``exportar_grafo_png`` — função auxiliar que cria a pasta ``assets/``
                               caso não exista e exporta a imagem visual do
                               fluxo via ``app.get_graph().draw_mermaid_png()``.

Uso como script (gera ``assets/cortex_flow_v2_graph.png``):

    python -m cortex_flow_v2.graph
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Callable

from langgraph.graph import END, START, StateGraph

from cortex_flow_v2.graph.state import CortexState

# ---------------- Constantes ----------------
DIR_RAIZ = Path(__file__).resolve().parents[2]
CAMINHO_PNG_PADRAO = DIR_RAIZ / "assets" / "cortex_flow_v2_graph.png"

# Travas de hardware/latência (Item 09) — pausa determinística (s) aplicada
# após a execução de cada nó, ou seja, imediatamente antes de a transição
# disparar o próximo nó da malha.
PAUSA_HARDWARE_S = 2.0

# Intenções de rota usadas pelos roteadores determinísticos.
INTENCAO_COPY_OFFER = "COPY_OFFER"
INTENCAO_BUILDER_TEMPLATE = "BUILDER_TEMPLATE"

# Decisões dos roteadores condicionais.
ROTA_A_DECISAO = "ROTA_A"      # -> evaluator (direto, após o crítico)
ROTA_B_DECISAO = "ROTA_B"      # -> sintetizador (após o crítico)



def envolver_com_pausa(nome: str, funcao: Callable) -> Callable:
    """Envolve um nó com a pausa determinística de hardware (Item 09).

    A pausa ocorre DEPOIS que o nó retornou seu update de estado — portanto
    exatamente na transição para o próximo nó da malha —, garantindo uma
    cadência reprodutível de 2.0 s entre passos.

    Args:
        nome: nome do nó (usado apenas para depuração/diagrama).
        funcao: função original ``(state: CortexState) -> dict``.

    Returns:
        Callable: função equivalente com ``time.sleep(PAUSA_HARDWARE_S)`` ao final.
    """

    def no_com_pausa(state: CortexState) -> dict:
        resultado = funcao(state)
        time.sleep(PAUSA_HARDWARE_S)
        return resultado

    no_com_pausa.__name__ = f"pausa_{nome}"
    no_com_pausa.__qualname__ = no_com_pausa.__name__
    no_com_pausa.__doc__ = (
        f"Nó '{nome}' com trava de hardware: pausa determinística de "
        f"{PAUSA_HARDWARE_S}s na transição (Item 09)."
    )
    return no_com_pausa


def rotear_apos_triagem(estado: CortexState) -> str:
    """Roteador determinístico pós-triagem (Item 12).

    Args:
        estado: estado corrente com ``frente_alvo`` já classificado pelo Agente 0.

    Returns:
        str: ``ROTA_A`` para COPY_OFFER, ``ROTA_B`` para BUILDER_TEMPLATE
        (fallback determinístico: qualquer valor não COPY_OFFER vai à rota B,
        preservando o comportamento conservador do Agente 0).
    """
    frente = str(estado.get("frente_alvo") or "").strip().upper()
    if frente == INTENCAO_COPY_OFFER:
        return ROTA_A_DECISAO
    return ROTA_B_DECISAO


def rotear_apos_critico(estado: CortexState) -> str:
    """Roteador determinístico pós-crítico (Item 12).

    O nó ``critico`` é o ponto de encontro das duas rotas; a partir dele a
    rota A segue direto para o ``evaluator`` e a rota B passa pelo
    ``sintetizador`` + ``builder`` antes do ``evaluator``.

    Args:
        estado: estado corrente (``frente_alvo`` e ``copy_comercial``).

    Returns:
        str: ``ROTA_A`` (evaluator) ou ``ROTA_B`` (sintetizador).
    """
    frente = str(estado.get("frente_alvo") or "").strip().upper()
    if frente == INTENCAO_COPY_OFFER:
        return ROTA_A_DECISAO
    if str(estado.get("copy_comercial") or "").strip():
        # Copy já redigida (rota A) mesmo se frente_alvo estiver vazia.
        return ROTA_A_DECISAO
    return ROTA_B_DECISAO


def construir_grafo():
    """Monta e compila o StateGraph do Cortex-Flow V2 (Fase 3 — Item 12).

    Malha completa unificando as duas rotas até o Evaluator:

        Rota A: triagem -> redator -> critico -> evaluator -> END
        Rota B: triagem -> mapeador -> techscout -> critico
                -> sintetizador -> builder -> evaluator -> END

    Todos os nós recebem a trava de hardware ``time.sleep(2.0)`` na transição
    (Item 09) via :func:`envolver_com_pausa`.

    Os nós são importados AQUI (dentro da função) para evitar import circular:
    cada nó importa ``cortex_flow_v2.graph.state``, o que dispararia a
    inicialização do pacote ``cortex_flow_v2.graph`` (e vice-versa).
    """
    # Import local: evita import circular com os nós (que importam graph.state).
    from cortex_flow_v2.nodes.builder import nodo_builder
    from cortex_flow_v2.nodes.critico import nodo_critico
    from cortex_flow_v2.nodes.evaluator import nodo_evaluator
    from cortex_flow_v2.nodes.mapeador import nodo_mapeador
    from cortex_flow_v2.nodes.redator import nodo_redator
    from cortex_flow_v2.nodes.sintetizador import nodo_sintetizador
    from cortex_flow_v2.nodes.techscout import nodo_techscout
    from cortex_flow_v2.nodes.triagem import nodo_triagem

    builder = StateGraph(CortexState)

    # Nós LangGraph-ready (assinatura: node(state: CortexState) -> dict),
    # todos envolvidos pela trava de hardware de 2.0s na transição (Item 09).
    nos = {
        "triagem": nodo_triagem,
        "mapeador": nodo_mapeador,
        "techscout": nodo_techscout,
        "redator": nodo_redator,
        "critico": nodo_critico,
        "sintetizador": nodo_sintetizador,
        "builder": nodo_builder,
        "evaluator": nodo_evaluator,
    }
    for nome, funcao in nos.items():
        builder.add_node(nome, envolver_com_pausa(nome, funcao))

    # --- Aresta inicial ---
    builder.add_edge(START, "triagem")

    # Roteador pós-triagem: separa Rota A (COPY_OFFER) de Rota B (BUILDER_TEMPLATE).
    builder.add_conditional_edges(
        "triagem",
        rotear_apos_triagem,
        {ROTA_A_DECISAO: "redator", ROTA_B_DECISAO: "mapeador"},
    )

    # --- Rota A: triagem -> redator -> critico -> evaluator -> END ---
    builder.add_edge("redator", "critico")

    # --- Rota B: triagem -> mapeador -> techscout -> critico ---
    builder.add_edge("mapeador", "techscout")
    builder.add_edge("techscout", "critico")

    # Roteador pós-crítico (nó compartilhado): Rota A segue direto para o
    # evaluator; Rota B passa pelo sintetizador e builder antes do evaluator.
    builder.add_conditional_edges(
        "critico",
        rotear_apos_critico,
        {ROTA_A_DECISAO: "evaluator", ROTA_B_DECISAO: "sintetizador"},
    )

    # --- Continuação da Rota B e fechamento comum ---
    builder.add_edge("sintetizador", "builder")
    builder.add_edge("builder", "evaluator")
    builder.add_edge("evaluator", END)

    return builder.compile()


# Instância compilada oficial do grafo.
# get_graph() deriva dela o Mermaid/ASCII e draw_mermaid_png() a imagem PNG.
app = construir_grafo()


def exportar_grafo_png(
    output_file_path: str = "assets/cortex_flow_v2_graph.png",
) -> str:
    """Exporta a imagem visual do fluxo LangGraph para um arquivo PNG.

    1. Garante que a pasta de destino (padrão ``assets/``) exista, criando-a
       recursivamente caso não exista (``parents=True, exist_ok=True``).
    2. Chama ``app.get_graph().draw_mermaid_png(output_file_path=...)`` para
       renderizar e gravar a imagem do grafo.
    3. Retorna o caminho absoluto do arquivo gerado.

    Args:
        output_file_path: caminho relativo ou absoluto do PNG de saída.
            Padrão: ``assets/cortex_flow_v2_graph.png``.

    Returns:
        str: caminho absoluto do PNG gerado.

    Raises:
        OSError: se a pasta de destino não puder ser criada.
    """
    destino = Path(output_file_path)

    # (1) Cria a pasta 'assets/' caso não exista
    destino.parent.mkdir(parents=True, exist_ok=True)

    # (2) Exporta a imagem visual do fluxo (método oficial do LangGraph)
    app.get_graph().draw_mermaid_png(output_file_path=str(destino))

    return os.path.abspath(str(destino))


if __name__ == "__main__":
    try:
        import sys as _sys

        _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass  # Python legado ou fluxos sem reconfigure: segue com o padrão do SO.

    png_gerado = exportar_grafo_png()
    print(f"✅ Grafo V2 exportado com sucesso: {png_gerado}")
