# ==============================================================================
# RS4-cortex-flow (Claudio Project) — Dockerfile leve
# Pipelines multiagente 100% local (biblioteca padrão do Python, zero pip).
# O Ollama roda NA MÁQUINA HOSPEDEIRA (fora do container) e é alcançado via
# OLLAMA_URL=http://host.docker.internal:11434/api/generate.
# ==============================================================================
FROM python:3.10-slim

# Sem `pip install`: o orquestrador usa somente a biblioteca padrão.
WORKDIR /app

# Copia apenas o orquestrador. As pastas bruto/, agentes/ e biblioteca/ são
# montadas como volumes via docker-compose.yml (não entram na imagem).
COPY orquestrador_claudio.py /app/orquestrador_claudio.py

# Segurança: executa como usuário sem privilégios.
RUN useradd --create-home --uid 1000 claudio \
    && mkdir -p /app/bruto /app/agentes /app/biblioteca /app/logs \
    && chown -R claudio:claudio /app
USER claudio

# OLLAMA_URL padrão aponta para o host quando o container não usa compose.
# Mensagens de log saem sem buffer para acompanhar em `docker logs`.
ENV OLLAMA_URL=http://host.docker.internal:11434/api/generate \
    PYTHONUNBUFFERED=1

# Uso padrão: docker compose run --rm claudio-project python \
#   orquestrador_claudio.py teste_frontend.txt
CMD ["python", "orquestrador_claudio.py"]