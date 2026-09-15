from datetime import datetime
import json
import os
import socket
import sys
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
OLLAMA_URL = "http://localhost:11434/api/generate"
MODELO = "qwen2.5:7b"  # Modelo de 7B confirmado via `ollama list` na v1
MAX_TOKENS_POR_CHUNK = 256  # Limite rígido de tokens por resposta (num_predict).
                             # Ajustado de 512->256: CPU mede ~6,2 tok/s, logo 256 tokens
                             # levam ~41s (bem dentro do timeout de 90s). Segue filosofia
                             # RS4: respostas curtas, previsíveis e sem estourar memória.
MAX_CARACTERES_HISTORICO = 1500  # Teto do histórico/contexto por chamada (chunking)
TIMEOUT_SEGUNDOS = 90  # Timeout explícito: evita loops infinitos e travamento de memória


def chamar_ollama_seguro(prompt_sistema, entrada_usuario):
    """Envia o chunk com limitação de tokens e timeout de segurança."""
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

    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SEGUNDOS) as response:
            res_json = json.loads(response.read().decode("utf-8"))
            return res_json.get("response", "").strip()
    except urllib.error.HTTPError as e:
        # Captura específica para HTTP 404: modelo inexistente no Ollama
        if e.code == 404:
            print(
                f"\n❌ HTTP 404: O modelo '{MODELO}' não foi encontrado no Ollama.\n"
                f"   Execute 'ollama pull {MODELO}' ou ajuste a variável MODELO "
                f"para um modelo instalado ('ollama list')."
            )
        else:
            print(
                f"\n❌ Erro HTTP {e.code} ao chamar {OLLAMA_URL}. "
                f"Verifique o servidor Ollama."
            )
        sys.exit(1)
    except urllib.error.URLError as e:
        print(
            f"\n❌ Falha de conexão com o Ollama em {OLLAMA_URL}.\n"
            f"   O servidor está rodando? Detalhe: {e.reason}"
        )
        sys.exit(1)
    except socket.timeout:
        print(
            f"\n❌ TRAVA DE SEGURANÇA ATIVADA: Timeout de {TIMEOUT_SEGUNDOS}s "
            f"excedido no agente. Abortando para evitar loops infinitos e "
            f"travamento de memória."
        )
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ TRAVA DE SEGURANÇA ATIVADA: Falha/Timeout no Ollama ({e})")
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
    print(f"🚀 Iniciando Claudio Project (Modelo: {MODELO})...")

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
    res_agente1 = chamar_ollama_seguro(sys_g1, entrada_agente1)

    # --- AGENTE 2: Tech Scout ---
    print("⏳ [2/4] Agente 2 (Tech Scout) em execução...")
    chunk_g2 = f"IDEIA:\n{truncar_chunk(ideia_bruta, 500)}\n\nAGENTE 1:\n{truncar_chunk(res_agente1, 800)}"
    res_agente2 = chamar_ollama_seguro(sys_g2, chunk_g2)

    # --- AGENTE 3: Crítico Ácido ---
    print("⏳ [3/4] Agente 3 (Crítico Ácido) em execução...")
    chunk_g3 = f"AGENTE 1:\n{truncar_chunk(res_agente1, 500)}\n\nAGENTE 2:\n{truncar_chunk(res_agente2, 800)}"
    res_agente3 = chamar_ollama_seguro(sys_g3, chunk_g3)

    # --- AGENTE 4: Sintetizador ---
    print("⏳ [4/4] Agente 4 (Sintetizador) em execução...")
    chunk_g4 = f"CRÍTICA AGENTE 3:\n{truncar_chunk(res_agente3, 800)}\n\nTECH AGENTE 2:\n{truncar_chunk(res_agente2, 500)}"
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
PROJETO: Claudio Project (v1.0)
DATA_EXECUCAO: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
MODELO_USADO: {MODELO}
FRENTE_ALVO: {frente_alvo}
TAGS: #rs4machine #claudio-project #refino-multiagente #conhecimento-local
STATUS: Refinado (Aguardando Decisão Humana)
---

# RELATÓRIO DE REFINO — CLAUDIO PROJECT

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

    print(f"\n✅ Concluído com Sucesso e Segurança!")
    print(f"📁 Arquivo gerado em: {caminho_saida}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("⚠️ Uso correto: python orquestrador_claudio.py <nome_do_arquivo.txt>")
        sys.exit(1)

    executar_cadeia_claudio(sys.argv[1])