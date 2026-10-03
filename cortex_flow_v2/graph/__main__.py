# -*- coding: utf-8 -*-
"""Ponto de entrada para ``python -m cortex_flow_v2.graph``.

Re-exporta o bloco executável do pacote: gera ``assets/cortex_flow_v2_graph.png``
chamando ``cortex_flow_v2.graph.exportar_grafo_png()``.
"""

from cortex_flow_v2.graph import exportar_grafo_png

if __name__ == "__main__":
    import sys

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass  # Python legado ou fluxos sem reconfigure: segue com o padrão do SO.

    png_gerado = exportar_grafo_png()
    print(f"✅ Grafo V2 exportado com sucesso: {png_gerado}")