import os

import chromadb
from chromadb.config import Settings
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction

from config import settings

CHROMA_DIR = os.path.join(os.path.dirname(__file__), "..", "chroma_data")
COLLECTION_NAME = "k8s_knowledge"

_client = None
_embedding_fn = None


def _get_embedding_fn() -> OpenAIEmbeddingFunction:
    global _embedding_fn
    if _embedding_fn is None:
        _embedding_fn = OpenAIEmbeddingFunction(
            api_key=settings.embedding_api_key,
            api_base=settings.embedding_base_url,
            model_name=settings.embedding_model,
        )
    return _embedding_fn


def _get_client() -> chromadb.PersistentClient:
    global _client
    if _client is None:
        os.makedirs(CHROMA_DIR, exist_ok=True)
        _client = chromadb.PersistentClient(
            path=CHROMA_DIR,
            settings=Settings(anonymized_telemetry=False),
        )
    return _client


def get_collection() -> chromadb.Collection:
    client = _get_client()
    ef = _get_embedding_fn()
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"},
    )


def add_document(doc_id: str, title: str, content: str, metadata: dict | None = None) -> None:
    collection = get_collection()
    meta = metadata or {}
    meta["title"] = title
    collection.add(
        ids=[doc_id],
        documents=[content],
        metadatas=[meta],
    )


def delete_document(doc_id: str) -> None:
    """Delete a document by ID."""
    collection = get_collection()
    collection.delete(ids=[doc_id])


def search(query: str, k: int = 3) -> list[dict]:
    collection = get_collection()
    results = collection.query(query_texts=[query], n_results=k)
    docs = []
    if results["ids"] and results["ids"][0]:
        for i, doc_id in enumerate(results["ids"][0]):
            docs.append({
                "id": doc_id,
                "content": results["documents"][0][i] if results["documents"] else "",
                "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                "distance": results["distances"][0][i] if results["distances"] else 0,
            })
    return docs
