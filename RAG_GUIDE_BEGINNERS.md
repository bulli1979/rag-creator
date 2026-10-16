# RAG System: Beginner's Guide

## What is RAG?

**RAG** = "Retrieval Augmented Generation"

Think of it like a **smart librarian**:
1. You ask a question
2. The librarian searches through all the books (documents) in the library
3. The librarian finds the most relevant pages
4. The librarian reads those pages to you
5. The librarian summarizes the answer based on what they read

Your RAG system does exactly this, but with documents instead of books.

---

## How Your RAG System Works

### The 3 Main Parts

#### 1. **Vector Database** (The Library Index)
- **Location**: `~/RAGIngestStudio-legacy_ollama_en/vector_sqlite/default.sqlite` (LOCAL on your machine)
- **What it stores**: All your documents converted into "vectors" (mathematical representations)
- **Why vectors?**: Computers can quickly find similar documents by comparing vectors
- **Local means**: Everything stays on YOUR computer — no data goes to the cloud
- **Size**: About 1-2 GB for 877 documents (depending on file sizes)

#### 2. **The Embedder** (The Translator)
- **Model used**: `all-MiniLM-L6-v2` (legacy profile) or `BAAI/bge-large-en-v1.5` (gemma4 profile)
- **What it does**: Converts text into vectors so the database can understand them
- **Runs on**: Your GPU/CPU (locally)
- **Speed**: ~10-20 documents per minute (depending on your hardware)

#### 3. **The LLM** (The Answerer)
- **Model used**: Ollama (legacy) or Gemma4 (gemma4 profile)
- **What it does**: Reads the retrieved documents and writes an answer in plain English
- **Runs on**: Your computer (via Ollama)

### The Flow: How Questions Get Answered

```
You ask a question
    ↓
Follow-up questions are resolved using the recent conversation
    ↓
Question is converted to a vector
    ↓
Vector database returns a wide pool of similar chunks
    ↓
Chunks are re-ranked (meaning + shared words + numbers), de-duplicated and capped per source
    ↓
Facts that can be read directly from the sources (tables, lists, ranges, procedures) are answered without the LLM
    ↓
Otherwise the LLM answers in JSON, citing quotations from the chunks
    ↓
Every claim is checked against its cited quotation; one repair attempt, then a source excerpt or "not found"
    ↓
You get the answer with sources (and an encrypted audit record is written)
```

See [METHODOLOGY.md](METHODOLOGY.md) for the details.

---

## Local Vector Database: What That Means

### ✅ Advantages
- **Privacy**: Your documents never leave your computer
- **Fast**: No network latency, searches happen instantly
- **Cheap**: Free tools, no subscription services
- **Offline**: Works without internet after initial setup

### ⚠️ Limitations
- **Limited to your computer**: Can't access from other machines easily
- **Storage**: Takes up disk space locally
- **Compute**: Embedding 1000s of documents takes time on your machine

### The Database Structure
```
~/RAGIngestStudio-legacy_ollama_en/
├── index.sqlite           ← Tracks which documents are indexed
├── files/                 ← Stores uploaded documents
├── corpus/                ← Extracted text from documents
└── vector_sqlite/
    └── default.sqlite     ← The actual vector database
```

---

## How to Update the Vector Database

### Adding New Documents

**Option 1: Via API (Web Interface)**
1. Open the document upload UI (Electron app or web interface)
2. Select PDF/TXT files
3. Click "Upload"
4. Wait for embedding to complete (5-10 minutes for 50 documents)

**Option 2: Via Script (Bulk Upload)**
```bash
export RAG_API_KEY=your_client_key   # all /api endpoints require an API key, see "API keys" below
python ingest_folder_batch.py "/path/to/your/documents" 200
```
This uploads everything in a folder in batches of 200 files.

**Option 3: Via HTTP API (Programmatic)**
```bash
curl -X POST http://127.0.0.1:8000/api/documents/upload-folder-path \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $RAG_API_KEY" \
  -d '{
    "folder_path": "/path/to/documents",
    "tags": ["my_tag"],
    "source": "lokal",
    "offset": 0,
    "batch_size": 200
  }'
```

### Monitoring Progress

**Option A: Count indexed chunks (vector database)**
```bash
sqlite3 ~/RAGIngestStudio-legacy_ollama_en/vector_sqlite/default.sqlite \
  "SELECT COUNT(DISTINCT document_id) as indexed_docs, COUNT(*) as total_chunks FROM rag_documents;"
```

Expected output:
```
indexed_docs | total_chunks
869          | 9144
```
This means: 869 documents fully embedded, split into 9,144 chunks.

**Option B: Check job status (index database)**
```bash
# Summary by status
sqlite3 ~/RAGIngestStudio-legacy_ollama_en/index.sqlite \
  "SELECT status, COUNT(*) FROM documents GROUP BY status;"
```

Expected output:
```
done|869
error|3
```

**Option C: List all successfully indexed documents**
```bash
sqlite3 ~/RAGIngestStudio-legacy_ollama_en/index.sqlite \
  ".headers on" \
  "SELECT fileName, chunkCount FROM documents WHERE status='done' ORDER BY fileName;"
```

**Option D: List failed documents with error reasons**
```bash
sqlite3 ~/RAGIngestStudio-legacy_ollama_en/index.sqlite \
  ".headers on" \
  "SELECT fileName, errorMessage FROM documents WHERE status='error';"
```

> **Note on errors**: Image-only PDFs (logos, drawings) and empty `.txt` files will show `status='error'` because there is no extractable text. This is expected and harmless.

> **Column names** in `index.sqlite` use camelCase: `fileName`, `chunkCount`, `errorMessage`, `docId`, `status`.

---

## How Long Does It Take to Build the Database?

### Timing Breakdown

| Task | Time per Document | Example |
|------|-------------------|---------|
| Parse text from PDF/TXT | 1-5 seconds | 1 PDF page ≈ 2 sec |
| Split into chunks | Instant | Automatic |
| Generate embeddings | 5-30 seconds | Depends on GPU |
| Store in database | 1-2 seconds | Write to disk |
| **Total per document** | **10-40 seconds** | Typical: 20 sec |

### Full Database Creation Times

| Documents | Chunks | GPU | CPU |
|-----------|--------|-----|-----|
| 100 | ~1,500 | 30 min | 2-3 hours |
| 500 | ~7,500 | 2.5 hours | 12-15 hours |
| 877 | ~12,000 | 4 hours | 20 hours |
| 1000 | ~15,000 | 5 hours | 25 hours |

**Your Setup** (legacy_ollama_en):
- **877 documents** = ~12,000 chunks
- **Expected time**: 4-6 hours with GPU, 18-24 hours with CPU only
- **Can run in background**: Yes! The embedding happens automatically

---

## Installation on Linux (Full Step-by-Step)

### Step 0: Prerequisites

You need:
- **Linux** (Ubuntu 20.04+ recommended)
- **Python 3.10+** (`python3 --version`)
- **Node.js 16+** (`node --version`)
- **Git** (`git --version`)
- **GPU** (NVIDIA with CUDA recommended, but CPU works too)

### Step 1: Clone the Repository

```bash
cd ~
git clone https://github.com/danutaparaficz2/rag-creator.git
cd rag-creator
```

### Step 2: Set Up Python Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
```

### Step 3: Install Python Dependencies

```bash
pip install -r documentApi/requirements.txt
```

### Step 4: Install Node.js Dependencies

```bash
npm install
cd chatBot && npm install && cd ..
cd documentHandling && npm install && cd ..
```

### Step 5: Create Profile Configuration

```bash
mkdir -p documentApi/profiles/legacy_ollama_en
cat > documentApi/profiles/legacy_ollama_en/settings.json << 'EOF'
{
  "activePostgresEnvironmentId": "default",
  "postgresEnvironments": [
    {
      "id": "default",
      "name": "SQLite Embedded",
      "vectorBackend": "sqlite_embedded",
      "dbHost": "localhost",
      "dbPort": 5432,
      "dbName": "rag",
      "dbUser": "postgres",
      "dbPassword": "",
      "dbSchema": "public",
      "dbTableName": "rag_documents",
      "sqliteFilePath": "",
      "qdrantLocalPath": ""
    }
  ],
  "chunkSize": 1200,
  "chunkOverlap": 15,
  "embeddingModel": "all-MiniLM-L6-v2",
  "storeMarkdown": true
}
EOF
```

Do the same for `chat_settings.json`:

```bash
cat > documentApi/profiles/legacy_ollama_en/chat_settings.json << 'EOF'
{
  "llmBaseUrl": "http://127.0.0.1:11434",
  "llmModel": "qwen2.5:7b",
  "maxContextLength": 6000,
  "systemPrompt": "You are a helpful assistant. Use ONLY the provided context to answer."
}
EOF
```

### Step 6: Start Ollama (if using legacy_ollama_en profile)

**Option A: Via Docker** (recommended)
```bash
docker run -d --gpus all -v ollama:/root/.ollama -p 11434:11434 --name ollama ollama/ollama
docker exec ollama ollama pull qwen2.5:7b
```

**Option B: Native Install**
```bash
curl -fsSL https://ollama.ai/install.sh | sh
ollama serve &  # Run in background
ollama pull qwen2.5:7b
```

### Step 7: Start the DocumentAPI

```bash
DOCUMENT_API_PORT=8000 DOCUMENT_API_PROFILE=legacy_ollama_en node scripts/run-document-api.mjs &
```

Wait for: `INFO: Application startup complete.`

**API keys:** on the first start the API creates a client key and an admin key and prints them **once** in the log (`Default API key (client): ...`). To choose your own, set `RAG_DEFAULT_API_KEY` and `RAG_ADMIN_API_KEY` before the first start. Send the client key in the `X-API-Key` header with every request (`export RAG_API_KEY=...` for the commands below). Only `/` and `/api/auth/status` are open.

### Step 8: Upload Your First Documents

```bash
# Create a test folder
mkdir -p ~/my_documents
cp /path/to/your/documents/*.pdf ~/my_documents/
cp /path/to/your/documents/*.txt ~/my_documents/

# Run the ingest script (reads RAG_API_KEY)
python ingest_folder_batch.py ~/my_documents 50
```

Monitor progress:
```bash
# Terminal 2 - Run every minute to check progress
watch -n 60 'sqlite3 ~/RAGIngestStudio-legacy_ollama_en/vector_sqlite/default.sqlite "SELECT COUNT(DISTINCT document_id), COUNT(*) FROM rag_documents;"'
```

### Step 9: Test the System

```bash
# Ask a question
curl -X POST http://127.0.0.1:8000/api/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $RAG_API_KEY" \
  -d '{
    "message": "What are the main topics in the documents?",
    "history": [],
    "language": "en"
  }' | python3 -m json.tool
```

---

## Troubleshooting

### "Port 8000 already in use"
```bash
kill $(lsof -t -iTCP:8000)
```

### "Ollama connection refused"
```bash
# Make sure Ollama is running
ollama serve &

# Download the model if missing
ollama pull qwen2.5:7b
```

### "No GPU detected / Slow embedding"
The system falls back to CPU. It's slower but works fine. To optimize:
```bash
# Check if GPU is available
python3 -c "import torch; print(torch.cuda.is_available())"

# If False, install GPU support (NVIDIA example)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

### "ModuleNotFoundError"
```bash
# Make sure venv is activated
source .venv/bin/activate

# Reinstall dependencies
pip install -r documentApi/requirements.txt
```

---

## Key Files You Need to Know

| File | Purpose |
|------|---------|
| `documentApi/app/main.py` | Starts the HTTP API |
| `documentApi/app/chat_service.py` | RAG logic (retrieve, select evidence, generate, validate, log) |
| `documentApi/app/grounding.py` | Checks every claim against its cited quotation |
| `documentApi/app/document_processing.py` | Structure-aware chunking of documents |
| `documentApi/app/ingest_service.py` | Handles document uploading/embedding and source versions |
| `documentApi/app/services/folder_scan.py` | Filters which file types to ingest |
| `ingest_folder_batch.py` | Bulk upload script |
| `documentApi/profiles/*/settings.json` | Profile configuration |

---

## Quick Reference: Common Commands

```bash
# Start API with legacy_ollama_en profile
DOCUMENT_API_PORT=8000 DOCUMENT_API_PROFILE=legacy_ollama_en node scripts/run-document-api.mjs &

# Upload documents from a folder
python ingest_folder_batch.py /path/to/docs 200

# Check indexing progress
sqlite3 ~/RAGIngestStudio-legacy_ollama_en/vector_sqlite/default.sqlite \
  "SELECT COUNT(DISTINCT document_id), COUNT(*) FROM rag_documents;"

# Stop the API
kill $(lsof -t -iTCP:8000)

# View API documentation
# Open: http://127.0.0.1:8000/docs in browser
```

---

## Frequently Asked Questions

### Q: Can I share the database with others?
**A**: Yes! Copy the entire `~/RAGIngestStudio-legacy_ollama_en/` folder to another machine and it will work.

### Q: How do I remove a document from the database?
**A**: Yes. `DELETE /api/documents/{doc_id}`, `POST /api/documents/remove-bulk` and `POST /api/documents/remove-not-ingested` remove documents (also available in the document-management UI). Re-indexing a changed source replaces its older version automatically.

### Q: What if I want to use a different embedding model?
**A**: Edit `documentApi/profiles/legacy_ollama_en/settings.json` and change `embeddingModel` to any HuggingFace model name (e.g., `"all-mpnet-base-v2"`). Re-ingest documents.

### Q: Can I run this on a server?
**A**: Yes! Set `DOCUMENT_API_HOST=0.0.0.0` to listen on all interfaces instead of just localhost.

### Q: How much storage do I need?
**A**: Roughly: 1 GB disk per 1,000 documents (varies based on document size). Vector database itself is efficient.

---

## Next Steps

1. **Install** following Step-by-Step above
2. **Add documents** using `ingest_folder_batch.py`
3. **Wait** for embedding to complete (check progress with SQLite query)
4. **Test** by asking questions via the API or UI
5. **Customize** by editing profiles and settings

Good luck! 🚀
