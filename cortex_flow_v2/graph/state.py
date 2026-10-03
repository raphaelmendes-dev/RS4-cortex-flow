# -*- coding: utf-8 -*-
"""Estado do Grafo V2 — Cortex-Flow V2.

Define o tipo do estado compartido que fluye pelos nós do grafo
(mapeador, techscout, crítico, sintetizador). Base: TypedDict (typing stdlib).
"""

from typing import TypedDict


class CortexState(TypedDict, total=False):
    """Estado tipado que circula pelo Grafo V2.

    Campos:
        entrada_bruta:       entrada original sem refinar.
        frente_alvo:         frente de trabalho alvo da execução.
        analise_mapeador:    análise estrutural do mapeador.
        analise_techscout:   análise técnica do tech scout.
        analise_critico:     análise crítica / auditoria.
        sintese_final:       síntese final consolidada.
        codigo_mvp:          template de código ou MVP gerado pelo Builder.
        caminho_template_md: caminho físico do template salvo em drafts/templates/.
        copy_comercial:      copy/anúncio produzido pelo Redator (Rota A).
        caminho_copy_md:     caminho físico da copy salva em drafts/ofertas/.
        parecer_evaluator:   parecer justificativo do Evaluator (Item 08.7).
        nota_preliminar:     nota preliminar de 1 a 5 do Evaluator (0 = não identificada).
        recomendacao_hitl:   recomendação preliminar de governança
                             (APROVAR | REVISAR | REJEITAR).
        caminho_avaliacao_md: caminho físico do artefato HITL em drafts/avaliacoes/.
        contexto_rag:        contexto externo recuperado (RAG).
        erros:               erros detectados durante o fluxo.
    """

    entrada_bruta: str
    frente_alvo: str
    analise_mapeador: str
    analise_techscout: str
    analise_critico: str
    sintese_final: str
    codigo_mvp: str
    caminho_template_md: str
    copy_comercial: str
    caminho_copy_md: str
    parecer_evaluator: str
    nota_preliminar: int
    recomendacao_hitl: str
    caminho_avaliacao_md: str
    contexto_rag: list
    erros: list
