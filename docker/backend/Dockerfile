# documentApi — Build-Kontext: Repository-Root (../..)
FROM python:3.12-slim-bookworm

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libmagic1 \
    poppler-utils \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

COPY documentApi/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY documentApi/app ./app

ENV PYTHONUNBUFFERED=1
ENV RAG_DATA_ROOT=/data

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
