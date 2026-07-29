# 🏛️ Multi-User RAG API for Hindi Government Circulars

> Production-ready, asynchronous FastAPI RAG service for ingesting Hindi government circular PDFs (Rajasthan Finance Department orders on *"Mukhya Mantri Ayushman Jeevan Raksha Yojana"*) into isolated FAISS vector stores and generating strictly grounded responses in formal Devanagari Hindi.

---

## 📌 Problem Statement

Official Indian government circulars are published in dense, formal Devanagari Hindi with structured clause numbering (`1.`, `2.`, `3.`) and attached legal annexures. Standard character-based naive splitters fragment these numbered provisions or merge distinct annexures, corrupting context retrieval and causing LLM hallucinations.

This service solves this by implementing **clause-aware text parsing with standalone Annexure isolation**, **non-blocking per-user FAISS vector indexing**, and **factually grounded response generation** using Groq's 70B Llama-3.3 engine.

For a deep-dive technical reference, see [WALKTHROUGH.md](WALKTHROUGH.md).

---

## 🏗️ Architecture

```
                                 +----------------------------+
                                 |    Government Circular     |
                                 |   PDF (Hindi Devanagari)   |
                                 +-------------+--------------+
                                               |
                                               v
                                 +----------------------------+
                                 |   PyMuPDF (fitz) Parser    |
                                 |  Clause & Annexure Splitter|
                                 +-------------+--------------+
                                               |
                                               v
                                 +----------------------------+
                                 |   Sentence-Transformers    |
                                 | (paraphrase-multilingual)  |
                                 +-------------+--------------+
                                               |
                                               v
                                 +----------------------------+
                                 |   Per-User FAISS Index     |
                                 |  (faiss_index.bin + json)  |
                                 +-------------+--------------+
                                               ^
                                               | Top-k Cosine Sim (Threadpool)
  +------------------+                +--------+-------+               +-----------------------+
  |  POST /rag/query +--------------->|  Query Embed   +-------------->| Groq LLM (70B-Class)  |
  |  {"query": ...}  | (Async Pool)   +----------------+               |  llama-3.3-70b        |
  +--------+---------+                                                 |  Strict Formal Hindi  |
           ^                                                           +-----------+-----------+
           |                      JSON Response / SSE Stream                       |
           +-----------------------------------------------------------------------+
```

---

## ✨ Features

- **Clause & Annexure Aware Chunking**: Preserves intact legal provisions and forces standalone chunk boundaries for `ANNEXURE-I` and `ANNEXURE-II` sections.
- **Multi-User Dataset Scoping**: Per-user dataset isolation under `./data/{user_id}/` supporting dynamic dataset creation (`rajasthani`, `dev1`, `company_docs`).
- **Non-Blocking Async Event Loop**: Wraps CPU-heavy `sentence-transformers` encoding and `FAISS` vector search calls in `run_in_threadpool` to preserve async server throughput.
- **Strict Formal Hindi Grounding**: System prompt strictly restricts answers to retrieved context and preserves exact figures/timelines (e.g. `रू0 10000/-`, `48 घंटे`).
- **Real SSE Token Streaming**: Stream tokens live over Server-Sent Events (`POST /rag/query/stream`).
- **Execution Timings**: Calculates high-resolution retrieval and LLM generation timing metrics (`retrieval_ms`, `generation_ms`, `total_ms`).

---

## 🛠️ Tech Stack

| Technology | Purpose |
| :--- | :--- |
| **FastAPI** | Asynchronous Web Framework |
| **PyMuPDF (`fitz`)** | Structural PDF Text Extraction |
| **FAISS (`faiss-cpu`)** | Local L2-Normalized Cosine Similarity Vector Search |
| **Sentence-Transformers** | Multilingual Embeddings (`paraphrase-multilingual-mpnet-base-v2`) |
| **Groq API** | 70B LLM Inference Engine (`llama-3.3-70b-versatile`) |
| **Pydantic & Settings** | Data Validation & Environment Settings Management |
| **Pytest & HTTPX** | Async Integration & Unit Test Suite |

---

## 📡 API Endpoints Summary

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `GET /health` | `GET` | Health check reporting loaded datasets, vector dimensions & model readiness |
| `POST /rag/upload/batch` | `POST` | Batch upload multiple PDF files for a specific dataset/user_id |
| `GET /dataset/read` | `GET` | Inspect dataset status, file lists, and chunk counts for a user_id |
| `POST /rag/query` | `POST` | Primary RAG query returning `{ "query", "answer", "context", "timings" }` |
| `POST /query` | `POST` | Alias query route |
| `POST /rag/query/stream` | `POST` | Real-time SSE token streaming query endpoint |

---

## 🚀 Setup & Quick Start

### 1. Clone Repository & Create Virtual Environment
```bash
git clone https://github.com/your-username/annexture.git
cd annexture

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Linux/macOS:
source venv/bin/activate
# On Windows:
venv\Scripts\activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Environment Configuration
Copy `.env.example` to `.env` and configure your `GROQ_API_KEY`:
```bash
cp .env.example .env
```
Edit `.env`:
```ini
GROQ_API_KEY=gsk_your_actual_groq_key_here
GROQ_MODEL=llama-3.3-70b-versatile
```

### 4. Generate Sample Hindi PDF Circular
A fresh clone contains an empty `data/` directory. Generate the authentic Rajasthan Finance Department circular PDF into `./data/rajasthani/`:
```bash
python create_rajasthan_circular_pdf.py
```

### 5. Start the Server
```bash
uvicorn main:app --reload --port 8080
```
Open [http://127.0.0.1:8080/docs](http://127.0.0.1:8080/docs) in your browser for the interactive Swagger UI.

---

## 💻 Usage & Example cURL Commands

### 1. Check Service Health
```bash
curl -X GET "http://127.0.0.1:8080/health"
```

### 2. Batch Upload PDF Documents for a Dataset
```bash
curl -X POST "http://127.0.0.1:8080/rag/upload/batch?user_id=rajasthani" \
  -F "files=@./data/rajasthani/Mukhya_Mantri_Ayushman_Jeevan_Raksha_Yojana.pdf"
```

### 3. Read Dataset Status
```bash
curl -X GET "http://127.0.0.1:8080/dataset/read?user_id=rajasthani"
```

### 4. Standard RAG Query (`POST /rag/query`)
```bash
curl -X POST "http://127.0.0.1:8080/rag/query" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "rajasthani",
    "query": "सड़क दुर्घटना पीड़ित की प्रोत्साहन राशि कितनी है?",
    "include_timings": true
  }'
```

#### Example Output:
```json
{
  "query": "सड़क दुर्घटना पीड़ित की प्रोत्साहन राशि कितनी है?",
  "answer": "सड़क दुर्घटना में गंभीर घायल व्यक्ति को समय पर अस्पताल पहुँचाने पर रू0 10000/- की प्रोत्साहन राशि प्रदान की जाती है।",
  "context": "3. प्रोत्साहन राशि एवं सम्मान:\n(1) सड़क दुर्घटना में गंभीर घायल व्यक्ति को समय पर अस्पताल/आघात केंद्र पहुँचाने वाले प्रत्येक भले व्यक्ति को रू0 10000/- की प्रोत्साहन राशि प्रदान की जाएगी।",
  "timings": {
    "retrieval_ms": 12.4,
    "generation_ms": 845.2,
    "total_ms": 857.6
  }
}
```

### 5. Stream Token Response (`POST /rag/query/stream`)
```bash
curl -N -X POST "http://127.0.0.1:8080/rag/query/stream" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "rajasthani",
    "query": "प्रोत्साहन राशि कितनी है?"
  }'
```

---

## 📓 Running the Standalone Jupyter Notebook

To inspect and debug the pipeline step-by-step without running a web server:

```bash
jupyter notebook rag_pipeline.ipynb
```
The notebook executes sequentially cell-by-cell:
1. **Environment Setup**: Key masking and dependency imports.
2. **PDF Extraction**: Clause & Annexure isolation inspector output.
3. **FAISS Indexing**: Vector normalization and index persistence.
4. **Semantic Retrieval**: Top-k similarity search.
5. **LLM Generation**: Groq 70B grounded Hindi answer generation.
6. **End-to-End Demo**: Interactive side-by-side display of context and generated answer.

---

## 🧪 Testing & Verification

The codebase includes both an automated pytest test suite and a manual verification script:

### Automated Pytest Suite
Runs offline unit tests and live endpoint tests:
```bash
pytest test_service.py -v
```
- Offline unit tests (OCR cleaner, clause splitter, uninitialized dataset reader) run unconditionally.
- Live LLM integration tests run automatically when `GROQ_API_KEY` is configured in `.env` (and skip gracefully in key-free CI builds via `@pytest.mark.skipif`).

### Manual Endpoint Verification Script
Runs end-to-end HTTP verification across all 6 API endpoints sequentially:
```bash
python test_all_endpoints.py
```

---

## 📂 Project Structure

```text
annexture/
├── config.py                 # Pydantic settings loading .env variables
├── create_rajasthan_circular_pdf.py # Helper script generating sample Devanagari PDF
├── inspect_chunks.py         # CLI chunk inspection utility
├── llm_client.py             # Async Groq API client with formal Hindi system prompt & SSE generator
├── main.py                   # FastAPI application & route definitions
├── pdf_parser.py             # PyMuPDF clause & annexure-aware text splitter
├── rag_pipeline.ipynb        # Standalone Jupyter notebook pipeline
├── requirements.txt          # Pinned dependency requirements
├── test_all_endpoints.py    # Manual HTTP end-to-end verification script
├── test_service.py           # Automated pytest integration suite
├── vector_store.py           # Multi-user FAISS vector store manager
├── .env.example              # Environment variable template (no secrets committed)
├── .gitignore                # Git exclusion rules
├── LICENSE                   # MIT License
├── README.md                 # Primary project documentation
├── WALKTHROUGH.md            # Technical walkthrough & deep-dive reference
└── scripts/                  # Internal development scripts
    ├── build_rag_notebook.py # Notebook builder utility
    └── run_notebook_cells.py # Notebook execution validator
```

---

## ⚠️ Known Limitations

1. **Local Disk Storage**: FAISS vector indices and chunk metadata are persisted on the local filesystem under `./data/{user_id}/`.
2. **Groq Free-Tier Rate Limits**: Production deployments with high concurrency should use paid API keys or higher rate-limit tiers.
3. **Document Scale**: Retrieval default (`top_k=3`) and chunking size (~200–300 tokens) are optimized for short to medium-length government circulars (1–20 pages).

---

## 📄 License

Distributed under the [MIT License](LICENSE).
