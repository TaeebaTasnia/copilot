"""Quick test to verify FAISS retriever works."""
import sys
sys.path.insert(0, ".")

from rag.faiss_retriever import FaissRetriever

retriever = FaissRetriever()
results = retriever.search("What is the BDT engine?")

print(f"Found {len(results)} results\n")
for r in results:
    print(f"Source: {r['source']} | Score: {r['score']:.2f}")
    print(f"Text: {r['content'][:150]}")
    print("---")