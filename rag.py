import os
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"

import chromadb
from sentence_transformers import SentenceTransformer
import config

# Initialize ChromaDB Client
chroma_client = chromadb.PersistentClient(path=config.CHROMA_DB_PATH)
collection = chroma_client.get_or_create_collection(name=config.COLLECTION_NAME)

# Initialize BGE Embedder
# Use local_files_only=True to skip hanging on network checks for optional files
try:
    embedder = SentenceTransformer(config.EMBEDDING_MODEL, local_files_only=True)
except Exception as e:
    print(f"[RAG] Local cache missing or incomplete, attempting download (bypassing SSL)...")
    os.environ['CURL_CA_BUNDLE'] = ''
    embedder = SentenceTransformer(config.EMBEDDING_MODEL)

def get_collection():
    return collection

def get_embedder():
    return embedder

def retrieve_context(query: str, n_results: int = 10) -> str:
    """Retrieve relevant context from ChromaDB using BGE embeddings."""
    query_emb = embedder.encode(query).tolist()
    results = collection.query(query_embeddings=[query_emb], n_results=n_results)
    
    if results['documents'] and len(results['documents'][0]) > 0:
        # Filter out empty chunks and join
        valid_docs = [doc for doc in results['documents'][0] if doc.strip()]
        return "\n---\n".join(valid_docs)
    return ""
