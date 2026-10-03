from datetime import datetime
import json
import os
import platform
import py_compile
import socket
import sys
import time
import urllib.error
import urllib.request

# ==============================================================================
# ROBUSTEZ DE SAÍDA (Item 09) — força UTF-8 no console Windows
# ==============================================================================
# Em consoles Windows com codepage cp1252/cp850 (PowerShell padrão), o print()
# de emojis do log lançava UnicodeEncodeError e abortava o pipeline antes do
# primeiro agente. Reconfigura a saída para UTF-8 com fallback seguro.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass  # Python legado ou fluxos sem reconfigure: segue com o padrão do SO.


# ==============================================================================
# CONFIGURAÇÕES MESTRES & SEGURANÇA (RS4 MACHINE)
# ==============================================================================
# OLLAMA_URL lida da variável de ambiente: no Docker o compose injeta
# 'http://host.docker.internal:11434/api/generate' para alcançar o Ollama da
# máquina hospedeira. Localmente mantém o fallback para localhost.
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/generate")
MODELO = "qwen2.5:7b"  # Modelo de 7B confirmado via `ollama list` na v1
MAX_TOKENS_POR_CHUNK = 1024  # num_predict: respostas completas, sem cortar texto.
                             # Ajustado de 256->1024: cada agente pode concluir a
                             # síntese integral da resposta (7B cabe 1024 tokens).
MAX_CARACTERES_HISTORICO = 1500  # Teto do histórico/contexto por chamada (chunking)
TIMEOUT_SEGUNDOS = 240  # Timeout explícito de 4 min/chamada: cobre execuções mais
                        # longas (7B em CPU) sem travar loops infinitos.


# ==============================================================================
# NOVA REGRA DE FILOSOFIA CEO RS4 — MEDIÇÃO HOLÍSTICA (Metrics/)
# ==============================================================================
# Toda execução do orquestrador grava um relatório detalhado em 'Metrics/' com:
#   (a) CÓDIGO/SISTEMA  -> py_compile, taxa de erro, status das saídas.
#   (b) OLLAMA/MODELO   -> latência da API REST local, tempo por agente,
#                          tokens (prompt_eval_count/eval_count) e status HTTP.
#   (c) AGENTE/CLINE    -> desempenho da execução, assertividade e artefatos.
# Os relatórios são gravados no bloco finally — mesmo quando o pipeline falha,
# a telemetria parcial é preservada para diagnóstico.
PASTA_METRICAS = "Metrics"
INDICE_AGENTE_METRICA = -1  # índice do agente que está executando no momento

METRICAS_STATUS = {"status_geral": "EM_EXECUCAO", "erros_codigo": 0}
METRICAS_SISTEMA = {}   # metadados de código/sistema (preenchidos em main())
METRICAS_OLLAMA = {}    # agregação do modelo/API (preenchida durante o fluxo)
METRICAS_AGENTES = []   # um dicionário por agente (telemetria detalhada)


def iniciar_metrica_agente(nome_agente):
    """Registra um novo agente na lista de telemetria e o marca como atual."""
    global INDICE_AGENTE_METRICA
    METRICAS_AGENTES.append(
        {
            "agente": nome_agente,
            "inicio_iso": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "fim_iso": None,
            "duracao_total_s": None,
            "latencia_http_s": None,
            "status_http": None,
            "tokens_prompt": None,
            "tokens_resposta": None,
            "tempo_eval_ms": None,
            "tempo_prompt_ms": None,
            "tempo_total_modelo_ms": None,
            "caracteres_prompt": None,
            "caracteres_resposta": None,
            "estado": "EM_EXECUCAO",
            "erro": None,
        }
    )
    INDICE_AGENTE_METRICA = len(METRICAS_AGENTES) - 1
    return METRICAS_AGENTES[INDICE_AGENTE_METRICA]


def registrar_erro_agente(reg, mensagem, estado="ERRO"):
    """Marcar o agente atual como erro e incrementar o contador global."""
    if reg is not None:
        inicio = reg.pop("_inicio_total", None) or time.monotonic()
        reg.update(
            {
                "fim_iso": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "estado": estado,
                "erro": mensagem,
                "duracao_total_s": round(time.monotonic() - inicio, 4),
            }
        )
    METRICAS_STATUS["erros_codigo"] += 1


def verificar_api_ollama():
    """Mede a latência da API REST local (GET /api/version) antes do pipeline."""
    base_url = OLLAMA_URL.rsplit("/api/generate", 1)[0]
    url_versao = base_url + "/api/version"
    inicio = time.monotonic()
    try:
        with urllib.request.urlopen(url_versao, timeout=10) as r:
            payload = json.loads(r.read().decode("utf-8"))
            status = r.status
            versao = payload.get("version")
        METRICAS_OLLAMA["versao_api"] = versao
        METRICAS_OLLAMA["status_health_check"] = status
        METRICAS_OLLAMA["latencia_api_rest_s"] = round(time.monotonic() - inicio, 4)
        print(
            f"🩺 Ollama REST API v{versao} respondendo em "
            f"{METRICAS_OLLAMA['latencia_api_rest_s']:.4f}s"
        )
        return True
    except Exception as err:
        METRICAS_OLLAMA["status_health_check"] = f"ERRO: {err}"
        METRICAS_OLLAMA["latencia_api_rest_s"] = round(time.monotonic() - inicio, 4)
        print(f"⚠️ Health check REST do Ollama falhou: {err}")
        return False


def chamar_ollama_seguro(prompt_sistema, entrada_usuario):
    """Envia o chunk com limitação de tokens e timeout de segurança.

    Instrumenta a chamada HTTP com telemetria CEO RS4: tempo total, latência
    REST, status HTTP, contagem real de tokens (prompt_eval_count/eval_count)
    e caracteres — tudo registrado no registro do agente em execução.
    """
    global INDICE_AGENTE_METRICA
    # Chunking rígido: o histórico/contexto entre agentes nunca passa de 1500 caracteres.
    entrada_usuario = truncar_chunk(entrada_usuario, MAX_CARACTERES_HISTORICO)

    prompt_completo = (
        f"SYSTEM:\n{prompt_sistema}\n\nUSER INPUT:\n{entrada_usuario}"
    )

    payload = {
        "model": MODELO,
        "prompt": prompt_completo,
        "stream": False,
        "options": {
            "num_predict": MAX_TOKENS_POR_CHUNK,
            "temperature": 0.2,  # Raciocínio mais focado e rápido
        },
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        OLLAMA_URL, data=data, headers={"Content-Type": "application/json"}
    )

    # Registro de telemetria do agente atual (preparado por iniciar_metrica_agente).
    reg = (
        METRICAS_AGENTES[INDICE_AGENTE_METRICA]
        if 0 <= INDICE_AGENTE_METRICA < len(METRICAS_AGENTES)
        else None
    )
    METRICAS_OLLAMA["url_api_generate"] = OLLAMA_URL
    METRICAS_OLLAMA["modelo"] = MODELO
    METRICAS_OLLAMA["num_predict"] = MAX_TOKENS_POR_CHUNK
    if reg is not None:
        reg["caracteres_prompt"] = len(prompt_completo)
        reg["_inicio_total"] = time.monotonic()

    inicio_total = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SEGUNDOS) as response:
            status_http = response.status
            res_json = json.loads(response.read().decode("utf-8"))
            latencia_http_s = time.monotonic() - inicio_total
            resposta = res_json.get("response", "").strip()
        if reg is not None:
            reg.update(
                {
                    "fim_iso": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "duracao_total_s": round(time.monotonic() - inicio_total, 4),
                    "latencia_http_s": round(latencia_http_s, 4),
                    "status_http": status_http,
                    "tokens_prompt": res_json.get("prompt_eval_count"),
                    "tokens_resposta": res_json.get("eval_count"),
                    "tempo_prompt_ms": round((res_json.get("prompt_eval_duration") or 0) / 1_000_000, 2),
                    "tempo_eval_ms": round((res_json.get("eval_duration") or 0) / 1_000_000, 2),
                    "tempo_total_modelo_ms": round((res_json.get("total_duration") or 0) / 1_000_000, 2),
                    "caracteres_resposta": len(resposta),
                    "estado": "OK",
                    "erro": None,
                }
            )
            reg.pop("_inicio_total", None)
        return resposta
    except urllib.error.HTTPError as e:
        # Captura específica para HTTP 404: modelo inexistente no Ollama
        if e.code == 404:
            print(
                f"\n❌ HTTP 404: O modelo '{MODELO}' não foi encontrado no Ollama.\n"
                f"   Execute 'ollama pull {MODELO}' ou ajuste a variável MODELO "
                f"para um modelo instalado ('ollama list')."
            )
            registrar_erro_agente(reg, f"HTTP 404 — modelo '{MODELO}' ausente", "ERRO_HTTP")
        else:
            print(
                f"\n❌ Erro HTTP {e.code} ao chamar {OLLAMA_URL}. "
                f"Verifique o servidor Ollama."
            )
            registrar_erro_agente(reg, f"HTTP {e.code}", "ERRO_HTTP")
        sys.exit(1)
    except urllib.error.URLError as e:
        print(
            f"\n❌ Falha de conexão com o Ollama em {OLLAMA_URL}.\n"
            f"   O servidor está rodando? Detalhe: {e.reason}"
        )
        registrar_erro_agente(reg, f"URLError: {e.reason}", "ERRO_CONEXAO")
        sys.exit(1)
    except socket.timeout:
        print(
            f"\n❌ TRAVA DE SEGURANÇA ATIVADA: Timeout de {TIMEOUT_SEGUNDOS}s "
            f"excedido no agente. Abortando para evitar loops infinitos e "
            f"travamento de memória."
        )
        registrar_erro_agente(reg, f"Timeout de {TIMEOUT_SEGUNDOS}s", "ERRO_TIMEOUT")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ TRAVA DE SEGURANÇA ATIVADA: Falha/Timeout no Ollama ({e})")
        registrar_erro_agente(reg, str(e), "ERRO_GENERICO")
        sys.exit(1)


def carregar_arquivo(caminho):
    """Lê arquivos locais com checagem de existência."""
    if not os.path.exists(caminho):
        print(f"❌ Erro de Segurança: Arquivo não encontrado em '{caminho}'")
        sys.exit(1)
    with open(caminho, "r", encoding="utf-8") as f:
        return f.read().strip()


def truncar_chunk(texto, max_caracteres=1500):
    """Resume o contexto passado entre agentes para não sobrecarregar a janela do 7B."""
    if len(texto) > max_caracteres:
        return texto[:max_caracteres] + "\n...[CHUNK RESUMIDO PARA SEGURANÇA]..."
    return texto


def extrair_frente_alvo(ideia_bruta):
    """Extrai a Frente Alvo marcada com [X] no template da ideia bruta.

    Procura a linha 'Frente Alvo' (formato: • Frente Alvo: [X] LAB | [ ] COMMERCE ...).
    Se houver mais de uma marcação [X], une com ' / '. Se nenhuma marcação for
    encontrada, mantém o padrão 'LAB / GERAL'.
    """
    for linha in ideia_bruta.splitlines():
        if "frente alvo" not in linha.lower():
            continue
        frentes = []
        for parte in linha.split("|"):
            idx_marcacao = parte.lower().find("[x]")
            if idx_marcacao != -1:
                rotulo = parte[idx_marcacao + 3 :].strip()
                if rotulo:
                    frentes.append(rotulo)
        if frentes:
            return " / ".join(frentes)
        return "LAB / GERAL"
    return "LAB / GERAL"


def carregar_contexto_global():
    """Procura 'contexto_global.txt' na raiz do projeto (prioridade) ou em
    'agentes/'. Se o arquivo não existir, retorna None — o pipeline segue
    rodando normalmente (fallback gracioso, sem abortar).
    """
    candidatos = [
        os.path.join("contexto_global.txt"),
        os.path.join("agentes", "contexto_global.txt"),
    ]
    for caminho in candidatos:
        if os.path.exists(caminho):
            return carregar_arquivo(caminho)
    return None


def executar_cadeia_claudio(arquivo_ideia_bruta):
    print(f"🚀 Iniciando RS4-cortex-flow (Modelo: {MODELO})...")

    # 1. Carregar Entrada e System Prompts
    caminho_bruto = os.path.join("bruto", arquivo_ideia_bruta)
    ideia_bruta = carregar_arquivo(caminho_bruto)

    sys_g1 = carregar_arquivo(os.path.join("agentes", "agente1_mapeador.txt"))
    sys_g2 = carregar_arquivo(os.path.join("agentes", "agente2_techscout.txt"))
    sys_g3 = carregar_arquivo(os.path.join("agentes", "agente3_critico.txt"))
    sys_g4 = carregar_arquivo(
        os.path.join("agentes", "agente4_sintetizador.txt")
    )

    # Contexto Global opcional (Item 08) — fallback gracioso
    contexto_global = carregar_contexto_global()
    if contexto_global is not None:
        print("🌐 Contexto Global injetado com sucesso!")
    else:
        print("ℹ️ Nenhum arquivo 'contexto_global.txt' detectado. Rodando em modo isolado.")

    # --- AGENTE 1: Mapeador ---
    print("⏳ [1/4] Agente 1 (Mapeador) em execução...")
    # Injeção do Contexto Global no início do prompt do Mapeador (Item 08)
    entrada_agente1 = truncar_chunk(ideia_bruta)
    if contexto_global is not None:
        entrada_agente1 = (
            f"CONTEXTO GLOBAL DA RS4MACHINE:\n{truncar_chunk(contexto_global, 500)}\n\n"
            f"IDEIA BRUTA:\n{entrada_agente1}"
        )
    iniciar_metrica_agente("Agente 1 — Mapeador Estrutural")
    res_agente1 = chamar_ollama_seguro(sys_g1, entrada_agente1)

    # --- AGENTE 2: Tech Scout ---
    print("⏳ [2/4] Agente 2 (Tech Scout) em execução...")
    chunk_g2 = f"IDEIA:\n{truncar_chunk(ideia_bruta, 500)}\n\nAGENTE 1:\n{truncar_chunk(res_agente1, 800)}"
    iniciar_metrica_agente("Agente 2 — Tech Scout")
    res_agente2 = chamar_ollama_seguro(sys_g2, chunk_g2)

    # --- AGENTE 3: Crítico Ácido ---
    print("⏳ [3/4] Agente 3 (Crítico Ácido) em execução...")
    chunk_g3 = f"AGENTE 1:\n{truncar_chunk(res_agente1, 500)}\n\nAGENTE 2:\n{truncar_chunk(res_agente2, 800)}"
    iniciar_metrica_agente("Agente 3 — Crítico Ácido")
    res_agente3 = chamar_ollama_seguro(sys_g3, chunk_g3)

    # --- AGENTE 4: Sintetizador ---
    print("⏳ [4/4] Agente 4 (Sintetizador) em execução...")
    chunk_g4 = f"CRÍTICA AGENTE 3:\n{truncar_chunk(res_agente3, 800)}\n\nTECH AGENTE 2:\n{truncar_chunk(res_agente2, 500)}"
    iniciar_metrica_agente("Agente 4 — Sintetizador")
    res_agente4 = chamar_ollama_seguro(sys_g4, chunk_g4)

    # 2. Gravação Segura (Sem Sobrescrever Arquivos Antigos)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nome_saida = f"Refinado_{timestamp}.md"
    caminho_saida = os.path.join("biblioteca", nome_saida)

    if os.path.exists(caminho_saida):
        print(
            f"❌ Trava de Segurança: O arquivo '{caminho_saida}' já existe. Abortando para evitar perda de dados."
        )
        sys.exit(1)

    frente_alvo = extrair_frente_alvo(ideia_bruta)

    relatorio_md = f"""---
PROJETO: RS4-cortex-flow (v1.0.1)
DATA_EXECUCAO: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
MODELO_USADO: {MODELO}
FRENTE_ALVO: {frente_alvo}
TAGS: #rs4machine #claudio-project #refino-multiagente #conhecimento-local
STATUS: Refinado (Aguardando Decisão Humana)
---

# RELATÓRIO DE REFINO — RS4-CORTEX-FLOW

---
## 📄 IDEIA BRUTA
{ideia_bruta}

---
## 🔍 AGENTE 1: Mapeamento Estrutural
{res_agente1}

---
## 🛠️ AGENTE 2: Tech Scout & Arquitetura
{res_agente2}

---
## ⚡ AGENTE 3: Crítica Ácida
{res_agente3}

---
## 🎯 AGENTE 4: Síntese e Plano de Ação
{res_agente4}
"""

    with open(caminho_saida, "w", encoding="utf-8") as f:
        f.write(relatorio_md)

    # Telemetria CEO RS4: confirmação do artefato gerado (CÓDIGO/SISTEMA).
    METRICAS_SISTEMA["artefato_saida"] = caminho_saida
    METRICAS_SISTEMA["artefato_bytes"] = os.path.getsize(caminho_saida)

    print(f"\n✅ Concluído com Sucesso e Segurança!")
    print(f"📁 Arquivo gerado em: {caminho_saida}")


def montar_metricas_consolidadas_json():
    """Consolida toda a telemetria CEO RS4 num único dicionário serializável."""
    agentes_ok = sum(1 for a in METRICAS_AGENTES if a.get("estado") == "OK")
    agentes_total = len(METRICAS_AGENTES)
    taxa_erro = round((agentes_total - agentes_ok) / agentes_total, 4) if agentes_total else None
    total_tokens_prompt = sum((a.get("tokens_prompt") or 0) for a in METRICAS_AGENTES)
    total_tokens_resposta = sum((a.get("tokens_resposta") or 0) for a in METRICAS_AGENTES)
    total_duracao = round(sum((a.get("duracao_total_s") or 0) for a in METRICAS_AGENTES), 4)
    return {
        "projeto": "RS4-cortex-flow (Claudio Project) v1.0.1",
        "regra": "Nova Regra de Filosofia CEO RS4 — Medição Holística",
        "gerado_em": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "a_codigo_sistema": {
            "python": METRICAS_SISTEMA.get("python"),
            "plataforma": METRICAS_SISTEMA.get("plataforma"),
            "entrada": METRICAS_SISTEMA.get("entrada"),
            "arquivo_bruto_existe": METRICAS_SISTEMA.get("arquivo_bruto_existe"),
            "validacao_sintaxe_py_compile": METRICAS_SISTEMA.get("validacao_sintaxe_py_compile"),
            "inicio_iso": METRICAS_SISTEMA.get("inicio_iso"),
            "fim_iso": METRICAS_SISTEMA.get("fim_iso"),
            "status_geral": METRICAS_SISTEMA.get("status_geral"),
            "erros_total": METRICAS_SISTEMA.get("erros_total"),
            "taxa_erro": taxa_erro,
            "agentes_ok": agentes_ok,
            "agentes_total": agentes_total,
            "artefato_saida": METRICAS_SISTEMA.get("artefato_saida"),
            "artefato_bytes": METRICAS_SISTEMA.get("artefato_bytes"),
            "erro_final": METRICAS_SISTEMA.get("erro_final"),
        },
        "b_ollama_modelo": {
            "modelo": METRICAS_OLLAMA.get("modelo"),
            "url_api_generate": METRICAS_OLLAMA.get("url_api_generate"),
            "versao_api": METRICAS_OLLAMA.get("versao_api"),
            "status_health_check": METRICAS_OLLAMA.get("status_health_check"),
            "latencia_api_rest_s": METRICAS_OLLAMA.get("latencia_api_rest_s"),
            "num_predict": METRICAS_OLLAMA.get("num_predict"),
            "temperatura": 0.2,
            "total_tokens_prompt": total_tokens_prompt,
            "total_tokens_resposta": total_tokens_resposta,
            "total_duracao_agentes_s": total_duracao,
        },
        "c_agente_cline": {
            "status_geral": METRICAS_STATUS.get("status_geral"),
            "erros_codigo": METRICAS_STATUS.get("erros_codigo"),
            "nota": "Avaliação qualitativa final consolidada no relatório do teste medido.",
        },
        "d_detalhe_agentes": METRICAS_AGENTES,
    }


def _formatar_tempo(segundos):
    """Formata segundos (float) como '12.34s' ou 'N/D' quando nulo."""
    if segundos is None:
        return "N/D"
    return f"{segundos:.2f}s"


def montar_relatorio_holistico_md():
    """Gera o relatório Markdown holístico (CEO RS4) com as 3 dimensões."""
    gerado = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sis, oll = METRICAS_SISTEMA, METRICAS_OLLAMA
    agentes_ok = sum(1 for a in METRICAS_AGENTES if a.get("estado") == "OK")
    agentes_total = len(METRICAS_AGENTES)
    taxa_erro = round((agentes_total - agentes_ok) / agentes_total, 4) if agentes_total else "N/D"

    L = []
    L.append("---")
    L.append("PROJETO: RS4-cortex-flow (Claudio Project) v1.0.1")
    L.append("REGRA: Nova Regra de Filosofia CEO RS4 — Medição Holística")
    L.append(f"GERADO_EM: {gerado}")
    L.append(f"ENTRADA: {sis.get('entrada', 'N/D')}")
    L.append("TAGS: #rs4machine #claudio-project #metricas #ceo-rs4 #telemetria #performance")
    L.append("---")
    L.append("")
    L.append("# 📊 RELATÓRIO DE MÉTRICAS HOLÍSTICAS — CEO RS4")
    L.append("")
    L.append("Medição automática de **CÓDIGO/SISTEMA**, **OLLAMA/MODELO** e **AGENTE/CLINE**. Gravada em `Metrics/` em toda execução do orquestrador.")
    L.append("")

    L.append("## 1) CÓDIGO / SISTEMA")
    L.append("")
    L.append("| Métrica | Valor |")
    L.append("|---|---|")
    L.append(f"| Python | {sis.get('python', 'N/D')} |")
    L.append(f"| Plataforma | {sis.get('plataforma', 'N/D')} |")
    L.append(f"| Arquivo de entrada | `{sis.get('entrada', 'N/D')}` |")
    L.append(f"| Entrada detectada em bruto/ | {'✅ Sim' if sis.get('arquivo_bruto_existe') else '❌ Não'} |")
    L.append(f"| Validação de sintaxe (py_compile) | {sis.get('validacao_sintaxe_py_compile', 'N/D')} |")
    L.append(f"| Início (ISO) | {sis.get('inicio_iso', 'N/D')} |")
    L.append(f"| Fim (ISO) | {sis.get('fim_iso', 'N/D')} |")
    L.append(f"| Status geral | {sis.get('status_geral', 'N/D')} |")
    L.append(f"| Total de erros | {sis.get('erros_total', 0)} |")
    L.append(f"| Taxa de erro (agentes) | {taxa_erro} |")
    L.append(f"| Agentes OK / total | {agentes_ok} / {agentes_total} |")
    L.append(f"| Artefato de saída | `{sis.get('artefato_saida', 'N/D')}` |")
    L.append(f"| Tamanho do artefato | {sis.get('artefato_bytes', 'N/D')} bytes |")
    if sis.get("erro_final"):
        L.append(f"| Erro final | `{sis.get('erro_final')}` |")
    L.append("")

    L.append("## 2) OLLAMA / MODELO")
    L.append("")
    L.append("| Métrica | Valor |")
    L.append("|---|---|")
    L.append(f"| Modelo | {oll.get('modelo', 'N/D')} |")
    L.append(f"| Endpoint generate | `{oll.get('url_api_generate', 'N/D')}` |")
    L.append(f"| Versão da API Ollama | {oll.get('versao_api', 'N/D')} |")
    L.append(f"| Health check REST (GET /api/version) | {oll.get('status_health_check', 'N/D')} |")
    L.append(f"| Latência da API REST local | {_formatar_tempo(oll.get('latencia_api_rest_s'))} |")
    L.append(f"| num_predict (teto por agente) | {oll.get('num_predict', 'N/D')} |")
    L.append(f"| Temperatura | 0.2 |")
    total_tok_p = sum((a.get("tokens_prompt") or 0) for a in METRICAS_AGENTES)
    total_tok_r = sum((a.get("tokens_resposta") or 0) for a in METRICAS_AGENTES)
    total_dur = sum((a.get("duracao_total_s") or 0) for a in METRICAS_AGENTES)
    L.append(f"| Total tokens de prompt (4 agentes) | {total_tok_p} |")
    L.append(f"| Total tokens de resposta (4 agentes) | {total_tok_r} |")
    L.append(f"| Total de tempo de inferência (soma das chamadas) | {_formatar_tempo(total_dur)} |")
    L.append("")

    L.append("## 3) AGENTES — TELEMETRIA POR CHAMADA HTTP")
    L.append("")
    if METRICAS_AGENTES:
        L.append("| Agente | Estado | Status HTTP | Latência HTTP | Duração total | Tokens prompt | Tokens resposta | Chars resposta |")
        L.append("|---|---|---|---|---|---|---|---|")
        for a in METRICAS_AGENTES:
            L.append(
                f"| {a.get('agente', 'N/D')} | {a.get('estado', 'N/D')} "
                f"| {a.get('status_http', 'N/D')} | {_formatar_tempo(a.get('latencia_http_s'))} "
                f"| {_formatar_tempo(a.get('duracao_total_s'))} "
                f"| {a.get('tokens_prompt', 'N/D')} | {a.get('tokens_resposta', 'N/D')} "
                f"| {a.get('caracteres_resposta', 'N/D')} |"
            )
        erros = [a for a in METRICAS_AGENTES if a.get("estado") != "OK"]
        if erros:
            L.append("")
            L.append("**Detalhe de erros:**")
            for a in erros:
                L.append(f"- `{a.get('agente')}` → {a.get('erro')}")
    else:
        L.append("Nenhum agente executado (falha antes da primeira chamada).")
    L.append("")

    L.append("## 4) AGENTE / CLINE — DESEMPENHO E ASSERTIVIDADE")
    L.append("")
    L.append("| Critério | Resultado |")
    L.append("|---|---|")
    L.append(f"| Status geral da execução | {METRICAS_STATUS.get('status_geral', 'N/D')} |")
    L.append(f"| Erros de código detectados | {METRICAS_STATUS.get('erros_codigo', 0)} |")
    L.append(f"| Agentes respondidos com sucesso | {agentes_ok} / {agentes_total} |")
    L.append(f"| Artefato final gerado | {'✅ Sim' if sis.get('artefato_saida') else '❌ Não'} |")
    L.append("> Observação: a avaliação qualitativa final do agente executor (CLINE) é consolidada no relatório do teste medido (`Metrics/metrics_teste_backend_*.md`).")
    L.append("")
    return "\n".join(L)


def gravar_relatorios_metricas():
    """Grava o relatório holístico CEO RS4 em Metrics/ (.md + .json).

    Chamado no bloco finally do main(): roda em sucesso E em falha, garantindo
    que a telemetria parcial nunca seja perdida.
    """
    try:
        os.makedirs(PASTA_METRICAS, exist_ok=True)
    except OSError as err:
        print(f"⚠️ Não foi possível criar a pasta 'Metrics/': {err}")
        return

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    entrada = METRICAS_SISTEMA.get("entrada", "orquestrador")
    nome_base = os.path.splitext(os.path.basename(entrada))[0]
    base = f"metrics_orquestrador_{nome_base}_{ts}"

    try:
        with open(os.path.join(PASTA_METRICAS, base + ".md"), "w", encoding="utf-8") as f:
            f.write(montar_relatorio_holistico_md())
        with open(os.path.join(PASTA_METRICAS, base + ".json"), "w", encoding="utf-8") as f:
            json.dump(montar_metricas_consolidadas_json(), f, ensure_ascii=False, indent=2)
        print(f"📊 [CEO RS4] Relatório holístico gravado: Metrics/{base}.md")
    except OSError as err:
        print(f"⚠️ Falha ao gravar relatório de métricas em Metrics/: {err}")


def main():
    if len(sys.argv) < 2:
        print("⚠️ Uso correto: python orquestrador_claudio.py <nome_do_arquivo.txt>")
        sys.exit(1)

    nome_arquivo = sys.argv[1]

    # --- (a) CÓDIGO/SISTEMA: metadados de ambiente + validação de sintaxe ---
    METRICAS_SISTEMA.update(
        {
            "entrada": nome_arquivo,
            "arquivo_bruto_existe": os.path.exists(os.path.join("bruto", nome_arquivo)),
            "inicio_iso": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "python": sys.version.split()[0],
            "plataforma": platform.platform(),
            "workdir": os.getcwd(),
        }
    )
    try:
        py_compile.compile(__file__, doraise=True)
        METRICAS_SISTEMA["validacao_sintaxe_py_compile"] = "OK"
    except py_compile.PyCompileError as err:
        METRICAS_SISTEMA["validacao_sintaxe_py_compile"] = f"ERRO: {err}"
        print(f"❌ Erro de sintaxe em {__file__}: {err}")
        sys.exit(1)

    # --- (b) OLLAMA/MODELO: health check da API REST local ---
    verificar_api_ollama()

    try:
        executar_cadeia_claudio(nome_arquivo)
        METRICAS_STATUS["status_geral"] = "SUCESSO"
        print("✅ Pipeline concluído — relatório de métricas gravado em Metrics/.")
    except SystemExit as err:
        METRICAS_STATUS["status_geral"] = "FALHA"
        METRICAS_SISTEMA["erro_final"] = (
            "Pipeline abortado (exit " + str(err.code) + ") — consulte o relatório de métricas gravado em Metrics/."
        )
        raise
    finally:
        METRICAS_SISTEMA["fim_iso"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        METRICAS_SISTEMA["status_geral"] = METRICAS_STATUS.get("status_geral")
        METRICAS_SISTEMA["erros_total"] = METRICAS_STATUS.get("erros_codigo", 0)
        gravar_relatorios_metricas()


if __name__ == "__main__":
    main()