# Technical Walkthrough - Multi-User RAG API

> Detailed technical reference for the Multi-User RAG API, including structural clause chunking rules, threadpool async execution, FAISS index persistence, system prompt engineering, inspect outputs, and API schema verification.

---

## 1. Deep-Dive Architecture

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

## 2. Structural Clause Chunking & Annexure Isolation

Official Devanagari Hindi government circulars contain numbered provisions (`1.`, `2.`, `3.`, `(1)`, `(2)`) and attached legal annexures (`ANNEXURE-I`, `ANNEXURE-II`, `अनेक्सचर-I`). 

### Key Chunking Rules in `pdf_parser.py`:
1. **Regex Clause Boundary Matching**: Split text at Devanagari/ASCII clause numbers and paragraph titles (`1.`, `2.`, `(1)`, `(2)`, `प्रकरण:`, `पात्रता:`).
2. **Mandatory Annexure Isolation**: Headers like `ANNEXURE-I` and `ANNEXURE-II` automatically force an immediate chunk boundary, preventing annexures from merging into preceding clauses.
3. **Granularity Target**: Target ~200–300 tokens (400–600 characters) per chunk to preserve contiguous legal figures (`रू0 10000/-`, `48 घंटे`).

#### Verified Output of `inspect_chunks.py`:
```text
======================================================================
 HINDI GOVERNMENT CIRCULAR CHUNK INSPECTOR
======================================================================
Parsing PDF: ./data/rajasthani/Mukhya_Mantri_Ayushman_Jeevan_Raksha_Yojana.pdf

Total Chunks Extracted: 9
======================================================================
CHUNK 1/9 | ID: chunk_0 | Page: 1 | Clause: 1. | Length: 285 chars
CHUNK 2/9 | ID: chunk_1 | Page: 1 | Clause: (1) | Length: 498 chars
CHUNK 3/9 | ID: chunk_2 | Page: 1 | Clause: 5. | Length: 439 chars
CHUNK 4/9 | ID: chunk_3 | Page: 1 | Clause: 5. | Length: 192 chars
CHUNK 5/9 | ID: chunk_4 | Page: 2 | Clause: ANNEXURE-I | Length: 217 chars (Isolated Standalone Chunk)
CHUNK 6/9 | ID: chunk_5 | Page: 2 | Clause: ANNEXURE-I | Length: 54 chars
CHUNK 7/9 | ID: chunk_6 | Page: 2 | Clause: ANNEXURE-II | Length: 160 chars (Isolated Standalone Chunk)
CHUNK 8/9 | ID: chunk_7 | Page: 2 | Clause: ANNEXURE-II | Length: 38 chars
CHUNK 9/9 | ID: chunk_8 | Page: 2 | Clause: 2. | Length: 136 chars
======================================================================
```

---

## 3. Multilingual Embedding & FAISS Persistence

- **Embedding Model**: `sentence-transformers/paraphrase-multilingual-mpnet-base-v2` (768 dimensions).
- **Index Type**: `faiss.IndexFlatIP` (Inner Product).
- **L2 Vector Normalization**: Embeddings are unit-normalized so Inner Product searches yield exact Cosine Similarity scores:
  $$\text{Cosine Similarity}(\vec{u}, \vec{v}) = \frac{\vec{u} \cdot \vec{v}}{\|\vec{u}\| \|\vec{v}\|}$$
- **Multi-User On-Disk Storage**: Per-user vector binary and JSON metadata stored under `./data/{user_id}/faiss_index.bin` and `./data/{user_id}/chunks.json`.

---

## 4. Non-Blocking Async Event Loop

Synchronous vector encoding and FAISS matrix operations block single-threaded asyncio event loops under heavy traffic. The API wraps CPU-bound calls using Starlette's `run_in_threadpool`:

```python
retrieved_chunks = await vector_store.search_async(uid, clean_query, top_k=settings.TOP_K)
```

---

## 5. System Prompt & Grounding Engineering

```text
आप राजस्थान सरकार के आधिकारिक नियम/परिपत्र (जैसे "मुख्यमंत्री आयुष्मान जीवन रक्षा योजना") पर आधारित एक सटीक, तथ्यपरक सहायक हैं।

आपको नीचे केवल संबंधित संदर्भ (Context) दिया जा रहा है। उत्तर देते समय निम्न नियमों का सख्ती से पालन करें:

1. केवल प्रदान किए गए संदर्भ (Context) के आधार पर ही उत्तर दें। कोई बाहरी ज्ञान या अनुमान न लगाएं।
2. भाषा एवं शैली:
   - उत्तर का माध्यम और शैली स्रोत दस्तावेज के समान औपचारिक/सरकारी हिंदी (Devanagari script) होनी चाहिए।
   - यदि उपयोगकर्ता का प्रश्न अंग्रेजी में है, तब भी उत्तर को पूरी तरह हिंदी स्रोत पाठ पर ही आधारित रखें, परंतु उत्तर अंग्रेजी में दिया जा सकता है।
3. यदि प्रश्न का उत्तर दिए गए संदर्भ में उपलब्ध नहीं है, तो स्पष्ट रूप से लिखें कि "प्रदान किए गए संदर्भ में इस संबंध में जानकारी उपलब्ध नहीं है।"
4. सटीकता एवं विवरण:
   - उत्तर को संक्षिप्त और तथ्यपरक रखें।
   - विशिष्ट आंकड़ों, तिथियों, समय-सीमाओं (जैसे 48 घंटे, 10000/-, रू0 10000/-) और खंड/पैरा संख्याओं को स्रोत दस्तावेज के अनुसार ही सटीक उद्धृत करें।
```

---

## 6. Full API Endpoint Specification

### `GET /health`
Returns system readiness, loaded datasets, embedding model, and LLM model info.

### `POST /rag/upload/batch?user_id=...`
Accepts `multipart/form-data` PDF uploads for any user dataset ID and builds a custom FAISS index.

### `GET /dataset/read?user_id=...`
Returns dataset status, file list, and chunk counts for any user ID (returns clean `uninitialized` status if empty).

### `POST /rag/query` & `POST /query`
Standard RAG query endpoint with payload:
```json
{
  "user_id": "rajasthani",
  "query": "सड़क दुर्घटना में गंभीर घायल को सहायता राशि कितनी है?",
  "include_timings": true
}
```
Response:
```json
{
  "query": "सड़क दुर्घटना में गंभीर घायल को सहायता राशि कितनी है?",
  "answer": "सड़क दुर्घटना में गंभीर घायल व्यक्ति को समय पर अस्पताल पहुँचाने पर रू0 10000/- की प्रोत्साहन राशि प्रदान की जाती है।",
  "context": "3. प्रोत्साहन राशि एवं सम्मान:\n(1) सड़क दुर्घटना में गंभीर घायल व्यक्ति को समय पर अस्पताल पहुँचाने वाले व्यक्ति को रू0 10000/- की प्रोत्साहन राशि दी जाएगी।",
  "timings": {
    "retrieval_ms": 14.2,
    "generation_ms": 780.5,
    "total_ms": 794.7
  }
}
```

### `POST /rag/query/stream`
Token-by-token Server-Sent Events (SSE) streaming query endpoint yielding:
```http
data: {"type": "metadata", "query": "...", "context": "..."}
data: {"type": "token", "content": "..."}
data: [DONE]
```

---

## 7. Verification Test Suite Results

```text
============================= test session starts =============================
platform win32 -- Python 3.13.5, pytest-9.1.1, pluggy-1.6.0
rootdir: D:\annexture

test_service.py .....ss                                                  [100%]

======================== 5 passed, 2 skipped in 13.64s ========================
```
- Core unit & offline endpoint tests execute and pass 100%.
- Live LLM integration tests run automatically when `GROQ_API_KEY` is present in `.env` (and skip gracefully via `@pytest.mark.skipif` in key-free CI builds).
