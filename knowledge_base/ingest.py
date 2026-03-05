"""
FAISS Ingestion Script
======================
Reads all .md files from knowledge/ subfolders, splits them into chunks,
generates embeddings, and saves a FAISS index to knowledge/faiss_index/.

The Generic Agent's rag_search tool reads from this index at runtime.

Run once before starting the project:
    cd knowledge
    pip install sentence-transformers faiss-cpu numpy
    python ingest.py
"""

import json
from pathlib import Path
import numpy as np
from sentence_transformers import SentenceTransformer
import faiss

# --- Config ---
KNOWLEDGE_DIR = Path(__file__).parent          # this is knowledge/
OUTPUT_DIR = KNOWLEDGE_DIR / "faiss_index"     # knowledge/faiss_index/
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
CHUNK_SIZE = 500    # characters per chunk
CHUNK_OVERLAP = 50  # overlap between chunks so context isn't lost at boundaries

SOURCES = [
    {"name": "maveric",         "subdir": "maveric"},
    {"name": "bdt_engine",      "subdir": "bdt_engine"},
    {"name": "data_sim",        "subdir": "data_sim"},
    {"name": "gateway",         "subdir": "gateway"},
    {"name": "rapp",            "subdir": "rapp"},
    {"name": "smo_sim",         "subdir": "smo_sim"},
    {"name": "platform_design", "subdir": "platform_design"},
]


def chunk_text(text: str) -> list[str]:
    """
    Split text into overlapping chunks.
    Overlap means a sentence at the edge of a chunk appears
    in both the previous and next chunk — so nothing gets cut off.
    """
    chunks = []
    start = 0
    while start < len(text):
        chunk = text[start:start + CHUNK_SIZE]
        if chunk.strip():
            chunks.append(chunk)
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks


def load_all_chunks() -> list[dict]:
    """
    Walk every source subdirectory, read all .md files,
    split into chunks, and return a flat list.

    Each item looks like:
        {"text": "...", "source": "bdt_engine", "file": "README.md"}
    """
    all_chunks = []
    for source in SOURCES:
        subdir = KNOWLEDGE_DIR / source["subdir"]
        if not subdir.exists():
            print(f"  [SKIP] {subdir} not found")
            continue
        for md_file in subdir.rglob("*.md"):
            content = md_file.read_text(encoding="utf-8")
            for chunk in chunk_text(content):
                all_chunks.append({
                    "text": chunk,
                    "source": source["name"],
                    "file": md_file.name,
                })
        print(f"  [OK] loaded: {source['name']}")
    return all_chunks


def main():
    print("=" * 50)
    print("NetAI Copilot — FAISS Ingestion")
    print("=" * 50)

    # Step 1: Load embedding model
    # This model converts text into 384-dimensional vectors
    # First run downloads ~90MB from HuggingFace
    print(f"\nLoading embedding model: {EMBEDDING_MODEL}")
    model = SentenceTransformer(EMBEDDING_MODEL)

    # Step 2: Load and chunk all markdown files
    print("\nLoading documents...")
    chunks = load_all_chunks()
    if not chunks:
        print("ERROR: No chunks found. Did you create the knowledge/ files?")
        return
    print(f"Total chunks: {len(chunks)}")

    # Step 3: Generate embeddings
    # Each chunk of text becomes a vector of 384 numbers
    # normalize_embeddings=True makes cosine similarity work correctly
    print("\nGenerating embeddings (this may take a minute)...")
    texts = [c["text"] for c in chunks]
    embeddings = model.encode(
        texts,
        show_progress_bar=True,
        normalize_embeddings=True
    )
    embeddings = np.array(embeddings, dtype="float32")

    # Step 4: Build FAISS index
    # IndexFlatIP = inner product search (cosine similarity when normalized)
    print("\nBuilding FAISS index...")
    dimension = embeddings.shape[1]   # 384 for all-MiniLM-L6-v2
    index = faiss.IndexFlatIP(dimension)
    index.add(embeddings)
    print(f"Index built: {index.ntotal} vectors, dimension={dimension}")

    # Step 5: Save index and metadata to disk
    # index.faiss  = the actual vectors (binary file)
    # metadata.json = the original text + source info for each vector
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(OUTPUT_DIR / "index.faiss"))
    with open(OUTPUT_DIR / "metadata.json", "w") as f:
        json.dump(chunks, f, indent=2)

    print(f"\n✓ Saved: {OUTPUT_DIR / 'index.faiss'}")
    print(f"✓ Saved: {OUTPUT_DIR / 'metadata.json'}")
    print("\nIngestion complete. You can now start the project.")


if __name__ == "__main__":
    main()