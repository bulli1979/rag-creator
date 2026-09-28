#!/bin/sh
# Startet Ollama und zieht genau ein Modell beim ersten Start.
set -e

MODEL="${OLLAMA_MODEL:?OLLAMA_MODEL muss gesetzt sein}"

ollama serve &
SERVER_PID=$!

echo "Warte auf Ollama-Server..."
until ollama list >/dev/null 2>&1; do
  sleep 1
done

if ollama list | grep -q "${MODEL}"; then
  echo "Modell bereits vorhanden: ${MODEL}"
else
  echo "Lade Modell: ${MODEL}"
  ollama pull "${MODEL}"
fi

echo "Ollama bereit mit Modell ${MODEL} auf Port 11434"
wait "${SERVER_PID}"
