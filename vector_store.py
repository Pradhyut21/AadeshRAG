import os
import json
import asyncio
import numpy as np
import faiss
from typing import List, Dict, Any, Optional, Tuple
from sentence_transformers import SentenceTransformer
from starlette.concurrency import run_in_threadpool
from config import settings

class VectorStoreManager:
    def __init__(self, model_name: str = settings.EMBEDDING_MODEL):
        self.model_name = model_name
        self.model = SentenceTransformer(model_name)
        self.dimension = self.model.get_sentence_embedding_dimension()
        # Storage dictionary mapping user_id -> {"index": faiss.Index, "chunks": List[dict]}
        self.stores: Dict[str, Dict[str, Any]] = {}

    def _normalize_vectors(self, vectors: np.ndarray) -> np.ndarray:
        """Normalize vectors to unit length for Cosine Similarity using Inner Product."""
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1e-10
        return vectors / norms

    def get_user_paths(self, user_id: str) -> Tuple[str, str, str]:
        """Get directory, index, and metadata file paths for a given user_id."""
        user_dir = os.path.join(settings.DATA_DIR, user_id)
        os.makedirs(user_dir, exist_ok=True)
        index_path = os.path.join(user_dir, "faiss_index.bin")
        metadata_path = os.path.join(user_dir, "chunks.json")
        return user_dir, index_path, metadata_path

    def build_index_for_user(self, user_id: str, chunks: List[Dict[str, Any]]) -> None:
        """Build FAISS index for a specific user_id."""
        if not chunks:
            raise ValueError("Cannot build index with empty chunks list")

        texts = [c["text"] for c in chunks]
        embeddings = self.model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
        embeddings = self._normalize_vectors(embeddings.astype("float32"))

        index = faiss.IndexFlatIP(self.dimension)
        index.add(embeddings)

        self.stores[user_id] = {
            "index": index,
            "chunks": chunks
        }
        self.save_user_index(user_id)

    def save_user_index(self, user_id: str) -> None:
        """Save user's FAISS index and metadata to disk."""
        if user_id not in self.stores:
            return
        _, index_path, metadata_path = self.get_user_paths(user_id)
        faiss.write_index(self.stores[user_id]["index"], index_path)
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(self.stores[user_id]["chunks"], f, ensure_ascii=False, indent=2)

    def load_user_index(self, user_id: str) -> bool:
        """Load user's FAISS index and metadata from disk."""
        _, index_path, metadata_path = self.get_user_paths(user_id)
        if not os.path.exists(index_path) or not os.path.exists(metadata_path):
            return False

        index = faiss.read_index(index_path)
        with open(metadata_path, "r", encoding="utf-8") as f:
            chunks = json.load(f)

        self.stores[user_id] = {
            "index": index,
            "chunks": chunks
        }
        return True

    def is_user_loaded(self, user_id: str) -> bool:
        """Check if index for user_id is currently loaded."""
        return user_id in self.stores and self.stores[user_id]["index"] is not None

    def get_user_chunks_count(self, user_id: str) -> int:
        """Get total chunks for user_id."""
        if not self.is_user_loaded(user_id):
            return 0
        return len(self.stores[user_id]["chunks"])

    def search_sync(self, user_id: str, query: str, top_k: int = settings.TOP_K) -> List[Dict[str, Any]]:
        """Synchronous vector search call for specific user_id."""
        # Fallback to default rajasthani dataset if specific user_id not loaded
        target_user = user_id if self.is_user_loaded(user_id) else "rajasthani"
        
        if not self.is_user_loaded(target_user):
            raise RuntimeError(f"Index for dataset/user_id '{target_user}' is not loaded.")

        store = self.stores[target_user]
        index = store["index"]
        chunks = store["chunks"]

        query_vec = self.model.encode([query], convert_to_numpy=True)
        query_vec = self._normalize_vectors(query_vec.astype("float32"))

        k = min(top_k, len(chunks))
        scores, indices = index.search(query_vec, k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx != -1 and idx < len(chunks):
                chunk_data = dict(chunks[idx])
                chunk_data["score"] = float(score)
                results.append(chunk_data)

        return results

    async def search_async(self, user_id: str, query: str, top_k: int = settings.TOP_K) -> List[Dict[str, Any]]:
        """Non-blocking async vector search using threadpool."""
        return await run_in_threadpool(self.search_sync, user_id, query, top_k)
