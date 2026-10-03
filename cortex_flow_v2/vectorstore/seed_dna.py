# -*- coding: utf-8 -*-
"""Seed DNA — Ingestão da filosofia/DNA do RS4 (Checklist Mestre — Item 07).

Cortex-Flow V2.

  1) Leitura:  filosofia_rs4.txt (raíz do projeto).
  2) Chunking: divide o conteúdo pelas seções numeradas (delimitador '====');
     cada seção se converte em um bloque/decisão com id determinístico
     'dna_rs4_<secao:03d>' → UPSERT idempotente em re-execucões.
  3) Ingestão: coleção 'decisoes' do ChromaDB local (./chroma_db_data) usando
     'chroma_client.py' + embedding Ollama 'nomic-embed-text'.
  4) Métricas: Metrics/metrics_seed_dna_v2.json com status + latência real.

Uso:  python cortex_flow_v2/vectorstore/seed_dna.py
"""

from __future__ import annotations

import datetime
import json
import platform
import py_compile
import re
import sys
import time
from pathlib import Path

import chromadb

# Garante que a raiz do projeto esteja no sys.path para os imports do paquete.
RAIZ_PROJETO = Path(__file__).resolve().parents[2]
if RAIZ_PROJETO not in sys.path:
    sys.path.insert(0, str(RAIZ_PROJETO))

from cortex_flow_v2.vectorstore.chroma_client import (
    CHROMA_DATA_DIR,
    COLLECTION_DECISOES,
    MODELO_EMBEDDING,
    crear_cliente_chroma,
    garantizar_coleccion_decisoes,
    verificar_modelo_embedding,
)

# ---------------- Constantes ----------------
RUTA_FILOSOFIA = RAIZ_PROJETO / "filosofia_rs4.txt"
CHROMA_DATA_DIR_ABSOLUTO = str(RAIZ_PROJETO / "chroma_db_data")
RUTA_METRICS = RAIZ_PROJETO / "Metrics" / "metrics_seed_dna_v2.json"
SEPARADOR_SECCION = re.compile(r"^\s*={20,}\s*$")
TIPO_DOCUMENTO = "dna_filosofia"
FUENTE_DOCUMENTO = "filosofia_rs4.txt"


def _agora() -> datetime.datetime:
    """Timestamp para a telemetria (Regla CEO RS4)."""
    return datetime.datetime.now()


def dividir_filosofia(texto: str) -> list[dict]:
    """Divide o conteúdo em bloques/decisões por seção numerada.

    Cada seção do arquivo tem a forma::

        ====================
        N. TÍTULO
        ====================
        <corpo da sección>

    O preámbulo antes do primeiro separador é conservado como bloque 0.
    Retorna una lista de bloques: {'id', 'numero', 'titulo', 'cuerpo'}.
    """
    lineas = texto.strip("\n").splitlines()
    indices_sep = [
        i for i, linea in enumerate(lineas) if SEPARADOR_SECCION.match(linea)
    ]
    if len(indices_sep) % 2 != 0:
        raise ValueError(
            f"Número ímpar de separadores de seção ({len(indices_sep)}) "
            f"em {RUTA_FILOSOFIA.name}: revisar o formato do arquivo."
        )

    bloques: list[dict] = []

    # --- Bloque 0: preámbulo antes do primeiro separador ---
    preambulo = "\n".join(lineas[: indices_sep[0]]).strip()
    if preambulo:
        bloques.append(
            {
                "id": "dna_rs4_000",
                "numero": 0,
                "titulo": "PREÁMBULO — CONTEXTO GENERAL",
                "cuerpo": preambulo,
            }
        )

    # --- Seções numeradas: separador / título / separador / corpo ---
    for k in range(0, len(indices_sep) - 1, 2):
        inicio_titulo = indices_sep[k] + 1
        fin_titulo = indices_sep[k + 1]
        fin_cuerpo = (
            indices_sep[k + 2] if k + 2 < len(indices_sep) else len(lineas)
        )

        titulo = ""
        for linea in lineas[inicio_titulo:fin_titulo]:
            if linea.strip():
                titulo = linea.strip()
                break
        corpo = "\n".join(lineas[fin_titulo + 1 : fin_cuerpo]).strip()

        numero = 0
        match = re.match(r"(\d+)\.\s*(.*)", titulo)
        if match:
            numero = int(match.group(1))
            titulo = match.group(2).strip() or titulo

        cuerpo_final = f"{titulo}\n\n{corpo}".strip() if corpo else titulo
        bloques.append(
            {
                "id": f"dna_rs4_{numero:03d}",
                "numero": numero,
                "titulo": titulo,
                "cuerpo": cuerpo_final,
            }
        )

    return bloques
def _metadata_para(bloque: dict) -> dict:
    """Metadatos de rastreabilidade para cada decisão persistida."""
    return {
        "fuente": FUENTE_DOCUMENTO,
        "tipo": TIPO_DOCUMENTO,
        "secao": bloque["numero"],
        "titulo": bloque["titulo"],
        "seed_dna_v2": True,
    }


def main() -> int:
    """Punto de entrada: seed DNA + registro de métricas com latência real."""
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    inicio_total = time.perf_counter()
    ahora = _agora()
    reporte: dict = {
        "proyecto": "RS4-cortex-flow v2 (Cortex-Flow V2)",
        "item": "Checklist Mestre Item 07 - Seed DNA",
        "regla": "Regla CEO RS4 - Semilla de memória / populación coleccion 'decisoes'",
        "descripcion": (
            "Ingestão da filosofia/DNA do RS4 (filosofia_rs4.txt) na coleção "
            "'decisoes' do ChromaDB local (./chroma_db_data) com embedding "
            "Ollama 'nomic-embed-text' e métricas de latência real."
        ),
        "fecha_hora": ahora.strftime("%Y-%m-%d %H:%M:%S"),
        "fecha_hora_iso": ahora.strftime("%Y-%m-%dT%H:%M:%S"),
        "ambiente": {
            "python": platform.python_version(),
            "chromadb_version": chromadb.__version__,
            "plataforma": platform.platform(),
            "workdir": str(RAIZ_PROJETO),
        },
    }

    try:
        # ---------- 1) Lectura + chunking ----------
        if not RUTA_FILOSOFIA.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {RUTA_FILOSOFIA}")
        texto = RUTA_FILOSOFIA.read_text(encoding="utf-8")
        bloques = dividir_filosofia(texto)

        reporte["entrada"] = {
            "archivo": RUTA_FILOSOFIA.name,
            "ruta_absoluta": str(RUTA_FILOSOFIA.resolve()),
            "caracteres_totales": len(texto),
            "lineas_totales": len(texto.splitlines()),
            "secciones_detectadas": len(bloques),
        }
        reporte["chunking"] = {
            "estrategia": "bloques por seção numerada (delimitador '====')",
            "total_bloques": len(bloques),
            "bloques": [
                {
                    "id": b["id"],
                    "numero": b["numero"],
                    "titulo": b["titulo"],
                    "caracteres": len(b["cuerpo"]),
                    "preview": b["cuerpo"][:80].replace("\n", " "),
                }
                for b in bloques
            ],
        }

        print("=" * 78)
        print("SEED DNA — POPULACIÓN COLEÇÃO 'decisoes' (Checklist Mestre Item 07)")
        print("=" * 78)
        print(f"Fonte : {RUTA_FILOSOFIA}")
        print(f"Palavras: char={len(texto)} lineas={len(texto.splitlines())}")
        print(f"Bloques/decisões detectados : {len(bloques)}")
        print("-" * 78)
        for b in bloques:
            print(
                f"  {b['id']:<16} | {b['numero']:>3} | "
                f"{b['titulo'][:45]:<45} | {len(b['cuerpo']):>6} chars"
            )
        print("-" * 78)
# ---------- 2) Sonda de embedding (nomic-embed-text) ----------
        check = verificar_modelo_embedding()
        reporte["embedding_ollama"] = check
        print(
            f"\nEmbedding '{MODELO_EMBEDDING}': {check.get('status')} "
            f"(dim={check.get('dimension_embedding')}, "
            f"lat={check.get('latencia_embedding_ms')} ms)"
        )

        # ---------- 3) Ingestão UPSERT idempotente na coleção 'decisoes' ----------
        cliente = crear_cliente_chroma(CHROMA_DATA_DIR_ABSOLUTO)
        coleccion = garantizar_coleccion_decisoes(cliente)
        count_antes = coleccion.count()
        print(f"\nCollection '{COLLECTION_DECISOES}': count_antes={count_antes}")

        inicio_ingestion = time.perf_counter()
        coleccion.upsert(
            ids=[b["id"] for b in bloques],
            documents=[b["cuerpo"] for b in bloques],
            metadatas=[_metadata_para(b) for b in bloques],
        )
        latencia_ingestion_ms = round(
            (time.perf_counter() - inicio_ingestion) * 1000, 4
        )
        count_despues = coleccion.count()
        print(
            f"UPSERT enviado={len(bloques)} | "
            f"count_despues={count_despues} | "
            f"latencia_ingestion={latencia_ingestion_ms} ms"
        )

        # ---------- 4) Auto-verificació + métricas ----------
        try:
            py_compile.compile(__file__)
            py_ok = "OK"
        except Exception as exc:
            py_ok = f"ERROR: {exc}"

        latencia_total_s = time.perf_counter() - inicio_total
        latencia_total_ms = round(latencia_total_s * 1000, 4)

        ok_embedding = check.get("status") == "OK"
        ok_ingestion = count_despues >= len(bloques)
        exito_total = bool(ok_embedding and ok_ingestion and py_ok == "OK")

        reporte["ingestion"] = {
            "coleccion": COLLECTION_DECISOES,
            "modelo_embedding": MODELO_EMBEDDING,
            "data_dir_relativo": CHROMA_DATA_DIR,
            "data_dir_absoluto": str(Path(CHROMA_DATA_DIR_ABSOLUTO).resolve()),
            "count_antes": count_antes,
            "count_despues": count_despues,
            "bloques_enviados": len(bloques),
            "latencia_ingestion_ms": latencia_ingestion_ms,
            "status": "OK" if ok_ingestion else "ERROR",
        }
        reporte["latencia"] = {
            "latencia_total_s": round(latencia_total_s, 4),
            "latencia_total_ms": latencia_total_ms,
            "latencia_embedding_ms": check.get("latencia_embedding_ms"),
            "latencia_ingestion_ms": latencia_ingestion_ms,
        }
        reporte["validacion"] = {
            "py_compile_seed_dna": py_ok,
            "embedding_status": check.get("status"),
            "coleccion": COLLECTION_DECISOES,
            "count_antes": count_antes,
            "count_despues": count_despues,
            "total_bloques": len(bloques),
            "todos_los_bloques_persistidos": ok_ingestion,
            "exit_code": 0 if exito_total else 1,
            "status": "SUCCESS" if exito_total else "FAILURE",
        }

        resumen = {
            "status": reporte["validacion"]["status"],
            "metrics_file": str(RUTA_METRICS),
            "bloques_persistidos": count_despues,
            "bloques_enviados": len(bloques),
            "coleccion": COLLECTION_DECISOES,
            "modelo": MODELO_EMBEDDING,
            "latencia_total_ms": latencia_total_ms,
            "latencia_embedding_ms": check.get("latencia_embedding_ms"),
            "latencia_ingestion_ms": latencia_ingestion_ms,
        }
        print("\n" + json.dumps(resumen, ensure_ascii=False, indent=2))
        return 0 if exito_total else 1

    except Exception as exc:
        import traceback

        latencia_total_s = time.perf_counter() - inicio_total
        reporte["error"] = {
            "tipo": type(exc).__name__,
            "mensaje": str(exc),
            "traceback": traceback.format_exc(),
        }
        reporte["latencia"] = {
            "latencia_total_s": round(latencia_total_s, 4),
            "latencia_total_ms": round(latencia_total_s * 1000, 4),
        }
        reporte["validacion"] = {
            "py_compile_seed_dna": "N/A",
            "embedding_status": "ERROR",
            "exit_code": 1,
            "status": "FAILURE",
        }
        print(f"\n❌ ERROR: {type(exc).__name__}: {exc}")
        return 1

    finally:
        RUTA_METRICS.parent.mkdir(parents=True, exist_ok=True)
        RUTA_METRICS.write_text(
            json.dumps(reporte, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    raise SystemExit(main())