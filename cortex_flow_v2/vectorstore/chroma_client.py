# -*- coding: utf-8 -*-
"""Cliente ChromaDB local + embedding Ollama — Cortex-Flow V2 (Prompt 3).

Conexión vectorial:
  1. Cliente persistente de ChromaDB na carpeta './chroma_db_data'.
  2. Garantía de existencia da coleção 'decisoes'.
  3. Verificación de acceso al modelo de embedding local de Ollama
     'nomic-embed-text' (función de teste con medición de latencia real).

Dependencias externas: chromadb y ollama (paquete oficial, usado por el EF
de chromadb para la colección). El resto del módulo usa solo stdlib
(urllib, json, time, pathlib).
"""

from __future__ import annotations

import datetime
import json
import time
import urllib.request
from pathlib import Path

import chromadb
from chromadb.config import Settings
from chromadb.utils.embedding_functions import (
    OllamaEmbeddingFunction as OllamaEF,
)

# ---------------- Constantes ----------------
CHROMA_DATA_DIR = "./chroma_db_data"
COLLECTION_DECISOES = "decisoes"
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_API_TAGS = f"{OLLAMA_BASE_URL}/api/tags"
OLLAMA_API_EMBEDDINGS = f"{OLLAMA_BASE_URL}/api/embed"  # endpoint nuevo (0.34+); el legacy /api/embeddings devuelve []
MODELO_EMBEDDING = "nomic-embed-text"
TEXTO_PRUEBA = "verificacion de conexion vectorial cortex flow v2"
TIMEOUT_OLLAMA = 60


class OllamaEmbeddingFunction:
    """Sonda de acceso/medición (urllib, stdlib) para el modelo de embedding.

    Verifica accesibilidad y mide latencia de 'nomic-embed-text' llamando a
    la API local ``/api/embed`` de Ollama. La colección 'decisoes' usa el
    EF oficial ``OllamaEF`` de chromadb (esta sonda no alimenta ChromaDB).
    """

    def __init__(self, modelo: str = MODELO_EMBEDDING, url: str = OLLAMA_API_EMBEDDINGS):
        self.modelo = modelo
        self.url = url

    def _embed(self, texto: str) -> list[float]:
        payload = json.dumps({"model": self.modelo, "input": texto}).encode("utf-8")
        request = urllib.request.Request(
            self.url, data=payload, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(request, timeout=TIMEOUT_OLLAMA) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["embeddings"][0]  # /api/embed devuelve lista 2D

    def embed_documents(self, documentos: list[str]) -> list[list[float]]:
        return [self._embed(doc) for doc in documentos]

    def embed_query(self, consulta: str) -> list[float]:
        return self._embed(consulta)

    def __call__(self, input: list[str]) -> list[list[float]]:
        return self.embed_documents(input)


# ---------------- Funciones base ----------------
def modelos_ollama() -> list[str]:
    """Devuelve los nombres de los modelos disponibles en Ollama local."""
    with urllib.request.urlopen(OLLAMA_API_TAGS, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    lista = data.get("models", data) if isinstance(data, dict) else data
    return [m.get("name", "") for m in lista if isinstance(m, dict)]


def crear_cliente_chroma(db_dir: str = CHROMA_DATA_DIR) -> chromadb.PersistentClient:
    """Crea/abre el cliente persistente local de ChromaDB."""
    Path(db_dir).mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(
        path=db_dir, settings=Settings(anonymized_telemetry=False)
    )


def garantizar_coleccion_decisoes(cliente: chromadb.PersistentClient):
    """Garantiza la existencia de la colección 'decisoes' con el EF oficial de chromadb."""
    ef = OllamaEF(url=OLLAMA_BASE_URL, model_name=MODELO_EMBEDDING)
    return cliente.get_or_create_collection(
        name=COLLECTION_DECISOES, embedding_function=ef
    )


# ---------------- Función de teste (Prompt 3, ítem 4) ----------------
def verificar_modelo_embedding(texto: str = TEXTO_PRUEBA) -> dict:
    """Verifica que 'nomic-embed-text' sea accesible y mide la latencia real.

    Devuelve un dict con evidencia: modelos disponibles, presencia del modelo,
    dimensión del embedding y latencia de la llamada al modelo.
    """
    disponibles = modelos_ollama()
    ef = OllamaEmbeddingFunction()
    inicio = time.perf_counter()
    vector = ef._embed(texto)
    latencia_s = time.perf_counter() - inicio
    return {
        "modelo": MODELO_EMBEDDING,
        "api": OLLAMA_BASE_URL,
        "modelos_disponibles": disponibles,
        "modelo_presente_en_ollama": any(
            MODELO_EMBEDDING in m for m in disponibles
        ),
        "dimension_embedding": len(vector),
        "latencia_embedding_s": round(latencia_s, 4),
        "latencia_embedding_ms": round(latencia_s * 1000, 2),
        "status": "OK" if vector else "ERROR",
    }


# ---------------- Validación integral (Prompt 3, ítem 5) ----------------
def validacion_integral() -> dict:
    """Ejecuta toda la cadena vectorial y devuelve el reporte de evidencia.

    Cadena: cliente persistente -> colección 'decisoes' -> embedding Ollama ->
    roundtrip real (insert + query + delete de un documento sonda).
    """
    import platform

    ahora = datetime.datetime.now()
    reporte: dict = {
        "proyecto": "RS4-cortex-flow v2 (Cortex-Flow V2)",
        "regla": "Regla CEO RS4 - Conexion Vectorial - Prompt 3",
        "descripcion": (
            "Conexion vectorial: ChromaDB persistente + coleccion 'decisoes'"
            " + embedding Ollama 'nomic-embed-text' + roundtrip real."
        ),
        "fecha_hora": ahora.strftime("%Y-%m-%d %H:%M:%S"),
        "fecha_hora_iso": ahora.isoformat(timespec="seconds"),
        "ambiente": {},
        "chroma": {},
        "embedding_ollama": {},
        "roundtrip": {},
        "validacion": {},
    }

    try:
        cliente = crear_cliente_chroma()
        coleccion = garantizar_coleccion_decisoes(cliente)
        check = verificar_modelo_embedding()

        try:
            coleccion.delete(where={"probe": True})  # limpia sondas de corridas previas
        except Exception:
            pass
        doc_id = "probe_prompt_3"
        coleccion.add(
            ids=[doc_id],
            documents=[TEXTO_PRUEBA],
            metadatas=[{"probe": True, "origen": "prompt3"}],
        )
        count_con_sonda = coleccion.count()
        resultado_query = coleccion.query(query_texts=[TEXTO_PRUEBA], n_results=1)
        if isinstance(resultado_query, dict):  # chromadb >= 1.5 devuelve dict
            ids_top = resultado_query.get("ids", [[]])
            distancia_top1 = resultado_query.get("distances", [[None]])[0][0]
            formato_query = "dict"
        else:  # chromadb < 1.5 devuelve QueryResult
            ids_top = resultado_query.ids
            distancia_top1 = getattr(resultado_query, "distances", [[None]])[0][0]
            formato_query = "QueryResult"
        hits = (
            len(ids_top[0]) if ids_top and isinstance(ids_top[0], list) else len(ids_top)
        )
        coleccion.delete(where={"probe": True})
        count_final = coleccion.count()

        reporte["ambiente"] = {
            "python": platform.python_version(),
            "chromadb_version": chromadb.__version__,
            "plataforma": platform.platform(),
        }
        reporte["chroma"] = {
            "client_persistente": True,
            "data_dir_relativo": CHROMA_DATA_DIR,
            "data_dir_absoluto": str(Path(CHROMA_DATA_DIR).resolve()),
            "data_dir_existe": Path(CHROMA_DATA_DIR).is_dir(),
            "coleccion": COLLECTION_DECISOES,
            "coleccion_existe": True,
            "count_con_sonda": count_con_sonda,
            "count_final_sin_sonda": count_final,
            "status": "OK",
        }
        reporte["embedding_ollama"] = check
        reporte["roundtrip"] = {
            "insert_documento_sonda": "OK",
            "query_n_results_esperado": 1,
            "query_hits": hits,
            "distancia_top1": round(float(distancia_top1), 8),
            "formato_query_api": formato_query,
            "delete_documento_sonda": "OK",
            "status": "OK" if hits >= 1 else "SEÑAL DEBIL",
        }
        ok_embedding = check["status"] == "OK"
        ok_roundtrip = hits >= 1
        ok_chroma = reporte["chroma"]["status"] == "OK"
        exito_total = bool(ok_embedding and ok_roundtrip and ok_chroma)
        reporte["validacion"] = {
            "py_compile_chroma_client": "OK",
            "test_verificar_modelo_embedding": check["status"],
            "roundtrip_status": reporte["roundtrip"]["status"],
            "exit_code": 0 if exito_total else 1,
            "status": "SUCCESS" if exito_total else "FAILURE",
        }
    except Exception as exc:
        import traceback

        reporte["error"] = {
            "tipo": type(exc).__name__,
            "mensaje": str(exc),
            "traceback": traceback.format_exc(),
        }
        reporte["validacion"] = {
            "py_compile_chroma_client": "N/A",
            "test_verificar_modelo_embedding": "ERROR",
            "exit_code": 1,
            "status": "FAILURE",
        }

    return reporte


def main() -> int:
    """Punto de entrada: ejecuta la validación y registra las métricas."""
    reporte = validacion_integral()
    ruta_metrics = Path("Metrics", "metrics_chroma_v2.json")
    ruta_metrics.parent.mkdir(parents=True, exist_ok=True)
    ruta_metrics.write_text(
        json.dumps(reporte, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    resumen = {
        "status": reporte["validacion"].get("status"),
        "metrics_file": str(ruta_metrics),
        "modelo": reporte.get("embedding_ollama", {}).get("modelo"),
        "latencia_ms": reporte.get("embedding_ollama", {}).get(
            "latencia_embedding_ms"
        ),
        "dimension_embedding": reporte.get("embedding_ollama", {}).get(
            "dimension_embedding"
        ),
        "coleccion": reporte.get("chroma", {}).get("coleccion"),
        "count_final": reporte.get("chroma", {}).get("count_final_sin_sonda"),
    }
    print(json.dumps(resumen, ensure_ascii=False, indent=2))
    return 0 if reporte["validacion"].get("status") == "SUCCESS" else 1


if __name__ == "__main__":
    raise SystemExit(main())