FROM ollama/ollama:latest
ENV OLLAMA_MODEL=gemma2:27b
COPY docker/ollama/entrypoint-model.sh /entrypoint-model.sh
RUN chmod +x /entrypoint-model.sh
EXPOSE 11434
ENTRYPOINT ["/entrypoint-model.sh"]
