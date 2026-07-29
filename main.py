import os
import glob
import time
import json
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, HTTPException, status, Query, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from config import settings
from pdf_parser import parse_pdf_to_chunks
from vector_store import VectorStoreManager
from llm_client import LLMClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("rag_service")

# Global vector store manager and LLM client
vector_store = VectorStoreManager(model_name=settings.EMBEDDING_MODEL)
llm_client = LLMClient()

def initialize_default_dataset():
    """Load default dataset 'rajasthani' on startup."""
    logger.info("Initializing vector datasets...")
    if not vector_store.load_user_index("rajasthani"):
        pdf_files = []
        if os.path.exists(settings.DATA_DIR):
            pdf_files.extend(glob.glob(os.path.join(settings.DATA_DIR, "*.pdf")))
        pdf_files.extend(glob.glob("*.pdf"))
        pdf_files = sorted(list(set(pdf_files)))

        all_chunks = []
        for pdf_path in pdf_files:
            logger.info(f"Ingesting PDF for 'rajasthani' dataset: {pdf_path}")
            chunks = parse_pdf_to_chunks(pdf_path)
            all_chunks.extend(chunks)

        if all_chunks:
            logger.info(f"Building 'rajasthani' dataset index with {len(all_chunks)} chunks...")
            vector_store.build_index_for_user("rajasthani", all_chunks)
            logger.info("Dataset 'rajasthani' successfully indexed and saved.")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan startup/shutdown lifecycle."""
    await run_in_threadpool(initialize_default_dataset)
    yield
    logger.info("Multi-User RAG API shutting down.")

app = FastAPI(
    title="Multi-User RAG API",
    version="FINAL",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Pydantic Schemas matching reference spec http://35.200.212.88:8080/docs
class QueryRequest(BaseModel):
    user_id: str = Field(default="rajasthani", description="Dataset identifier (e.g. rajasthani, dev1, med, or any custom user ID)")
    query: str = Field(..., description="Natural language query")
    include_timings: bool = Field(default=True, description="Include execution timing metrics")

class QueryResponse(BaseModel):
    query: str
    answer: str
    context: str
    timings: Optional[Dict[str, float]] = Field(default=None, description="Execution timing metrics in ms")

@app.get("/health", status_code=status.HTTP_200_OK)
async def health():
    """Health check endpoint."""
    loaded_users = [uid for uid in vector_store.stores.keys() if vector_store.is_user_loaded(uid)]
    return {
        "status": "healthy",
        "loaded_datasets": loaded_users,
        "embedding_model": settings.EMBEDDING_MODEL,
        "llm_model": settings.GROQ_MODEL
    }

@app.post("/rag/upload/batch", status_code=status.HTTP_200_OK)
async def upload_batch(
    user_id: str = Query(..., description="Target dataset user ID"),
    files: List[UploadFile] = File(..., description="PDF files to ingest")
):
    """Batch upload endpoint to ingest PDF files for any dataset/user_id."""
    clean_uid = user_id.strip()
    if not clean_uid:
        raise HTTPException(status_code=400, detail="User ID cannot be empty.")
    if not files:
        raise HTTPException(status_code=400, detail="No files provided.")

    user_dir, _, _ = vector_store.get_user_paths(clean_uid)
    saved_chunks = []

    for file in files:
        if not file.filename.lower().endswith(".pdf"):
            continue
        file_path = os.path.join(user_dir, file.filename)
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)

        chunks = parse_pdf_to_chunks(file_path)
        saved_chunks.extend(chunks)

    if not saved_chunks:
        raise HTTPException(status_code=400, detail="No valid text extracted from uploaded PDFs.")

    await run_in_threadpool(vector_store.build_index_for_user, clean_uid, saved_chunks)

    return {
        "user_id": clean_uid,
        "message": f"Successfully ingested {len(files)} file(s).",
        "total_chunks": len(saved_chunks)
    }

@app.get("/dataset/read", status_code=status.HTTP_200_OK)
async def read_dataset(
    user_id: str = Query(..., description="Target dataset user ID")
):
    """Read dataset details safely even if uninitialized."""
    clean_uid = user_id.strip()
    # Try loading from disk if not in memory
    if not vector_store.is_user_loaded(clean_uid):
        vector_store.load_user_index(clean_uid)

    is_loaded = vector_store.is_user_loaded(clean_uid)
    chunk_count = vector_store.get_user_chunks_count(clean_uid)
    user_dir, _, _ = vector_store.get_user_paths(clean_uid)

    files = glob.glob(os.path.join(user_dir, "*.pdf")) if os.path.exists(user_dir) else []

    return {
        "user_id": clean_uid,
        "status": "ready" if is_loaded else "uninitialized",
        "file_count": len(files),
        "filenames": [os.path.basename(f) for f in files],
        "total_chunks": chunk_count
    }

async def _process_query(request: QueryRequest) -> QueryResponse:
    """Core logic to process query against designated user dataset."""
    clean_query = request.query.strip()
    if not clean_query:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query string cannot be empty."
        )

    uid = request.user_id.strip() if request.user_id else "rajasthani"
    
    # Try loading user index if not loaded
    if not vector_store.is_user_loaded(uid):
        vector_store.load_user_index(uid)

    start_time = time.time()

    try:
        retrieved_chunks = await vector_store.search_async(uid, clean_query, top_k=settings.TOP_K)
        retrieval_ms = round((time.time() - start_time) * 1000, 2)

        if not retrieved_chunks:
            retrieved_chunk_ids = []
            context_text = ""
        else:
            retrieved_chunk_ids = [c["id"] for c in retrieved_chunks]
            context_text = "\n\n".join([c["text"] for c in retrieved_chunks])

        logger.info(f"User: '{uid}' | Retrieval: {retrieval_ms}ms | Chunks: {retrieved_chunk_ids}")

        gen_start = time.time()
        answer = await llm_client.generate_answer(clean_query, context_text)
        gen_ms = round((time.time() - gen_start) * 1000, 2)
        total_ms = round((time.time() - start_time) * 1000, 2)

        logger.info(f"User: '{uid}' | LLM Gen: {gen_ms}ms | Total: {total_ms}ms")

        timings_data = {
            "retrieval_ms": retrieval_ms,
            "generation_ms": gen_ms,
            "total_ms": total_ms
        } if request.include_timings else None

        return QueryResponse(
            query=clean_query,
            answer=answer,
            context=context_text,
            timings=timings_data
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Query processing error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process query: {str(e)}"
        )

@app.post("/rag/query", response_model=QueryResponse, status_code=status.HTTP_200_OK)
async def query_rag(request: QueryRequest) -> QueryResponse:
    """POST /rag/query endpoint."""
    return await _process_query(request)

@app.post("/query", response_model=QueryResponse, status_code=status.HTTP_200_OK)
async def query_legacy(request: QueryRequest) -> QueryResponse:
    """POST /query legacy endpoint."""
    return await _process_query(request)

@app.post("/rag/query/stream", status_code=status.HTTP_200_OK)
async def query_rag_stream(request: QueryRequest):
    """POST /rag/query/stream endpoint with real SSE token streaming."""
    clean_query = request.query.strip()
    if not clean_query:
        raise HTTPException(status_code=400, detail="Query string cannot be empty.")

    uid = request.user_id.strip() if request.user_id else "rajasthani"
    if not vector_store.is_user_loaded(uid):
        vector_store.load_user_index(uid)

    retrieved_chunks = await vector_store.search_async(uid, clean_query, top_k=settings.TOP_K)
    context_text = "\n\n".join([c["text"] for c in retrieved_chunks]) if retrieved_chunks else ""

    async def sse_generator():
        # First event: yield metadata context
        meta_payload = {
            "type": "metadata",
            "query": clean_query,
            "context": context_text
        }
        yield f"data: {json.dumps(meta_payload, ensure_ascii=False)}\n\n"

        # Stream token chunks
        async for token in llm_client.generate_answer_stream(clean_query, context_text):
            token_payload = {"type": "token", "content": token}
            yield f"data: {json.dumps(token_payload, ensure_ascii=False)}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(sse_generator(), media_type="text/event-stream")
