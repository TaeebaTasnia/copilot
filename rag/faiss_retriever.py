"""
FAISS Retriever
===============
Loads the index built by knowledge/ingest.py and searches it.

How it connects:
    Generic Agent
        → calls rag_search tool
        → tool calls FaissRetriever.search(query)
        → returns relevant doc chunks
        → Groq LLM reads chunks and answers the question
"""

import json
import logging
import os
from pathlib import Path
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# Default path — can be overridden with FAISS_INDEX_PATH env var
DEFAULT_INDEX_DIR = Path(__file__).parent.parent / "knowledge_base" / "faiss_index"


class FaissRetriever:
    """
    Searches the local FAISS index for relevant document chunks.
    No database needed — everything is in files on disk.
    """

    def __init__(self):
        index_dir = Path(
            os.environ.get("FAISS_INDEX_PATH", str(DEFAULT_INDEX_DIR))
        )

        index_path = index_dir / "index.faiss"
        metadata_path = index_dir / "metadata.json"

        if not index_path.exists():
            raise FileNotFoundError(
                f"FAISS index not found at {index_path.absolute()}. "
                f"Tried paths: {index_dir} (from env: {os.environ.get('FAISS_INDEX_PATH', 'not set')}). "
                "Run 'python knowledge_base/ingest.py' from project root."
            )

        # Load the FAISS index (the vectors)
        self._index = faiss.read_index(str(index_path))

        # Load the metadata (original text + source info)
        with open(metadata_path) as f:
            self._chunks = json.load(f)

        # Load the same embedding model used during ingestion
        # MUST be the same model — different models produce incompatible vectors
        model_name = os.environ.get(
            "EMBEDDING_MODEL",
            "sentence-transformers/all-MiniLM-L6-v2"
        )
        self._model = SentenceTransformer(model_name)
        logger.info(f"FaissRetriever ready — {self._index.ntotal} vectors loaded")

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """
        Convert query to a vector and find the top_k most similar chunks.

        Args:
            query: The user's question in plain text.
            top_k: How many results to return.

        Returns:
            List of dicts with: content, score, source, file_path
        """
        # Convert query text to vector
        embedding = self._model.encode(
            [query], normalize_embeddings=True
        )
        embedding = np.array(embedding, dtype="float32")

        # Search — returns similarity scores and chunk indices
        distances, indices = self._index.search(embedding, top_k)

        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx == -1:   # -1 means FAISS found fewer results than top_k
                continue
            chunk = self._chunks[idx]
            results.append({
                "content": chunk["text"],
                "score": float(dist),
                "source": chunk["source"],
                "file_path": chunk["file"],
            })
        return results

    def format_results(self, results: list[dict]) -> str:
        """
        Format results into a readable string the LLM can use as context.
        """
        if not results:
            return "No relevant documentation found."
        parts = []
        for i, r in enumerate(results, 1):
            parts.append(
                f"[{i}] Source: {r['source']} | Score: {r['score']:.2f}\n"
                f"{r['content']}"
            )
        return "\n\n---\n\n".join(parts)