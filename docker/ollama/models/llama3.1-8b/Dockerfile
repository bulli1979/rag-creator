FROM ollama/ollama:latest
ENV OLLAMA_MODEL=llama3.1:8b
COPY docker/ollama/entrypoint-model.sh /entrypoint-model.sh
RUN chmod +x /entrypoint-model.sh
EXPOSE 11434
ENTRYPOINT ["/entrypoint-model.sh"]
