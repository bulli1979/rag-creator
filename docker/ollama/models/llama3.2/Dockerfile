# Eigenstaendiger Ollama-Container nur fuer llama3.2 (schnell, ~2 GB)
# Start: docker compose -f docker/ollama/models/llama3.2/compose.yml up -d --build
FROM ollama/ollama:latest

ENV OLLAMA_MODEL=llama3.2

COPY docker/ollama/entrypoint-model.sh /entrypoint-model.sh
RUN chmod +x /entrypoint-model.sh

EXPOSE 11434
ENTRYPOINT ["/entrypoint-model.sh"]
