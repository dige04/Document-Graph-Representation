"""ChromaDB client for vector-only retrieval.

Provides pure embedding similarity search as baseline for comparison
against graph-enhanced retrieval from Neo4j.
"""
import os
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

import chromadb
from chromadb.config import Settings

logger = logging.getLogger(__name__)

# Singleton client
_chroma_client: Optional[chromadb.Client] = None
_collection: Optional[chromadb.Collection] = None

# Default collection name (matches Neo4j namespace)
COLLECTION_NAME = "legal_documents"
# Persist directory
CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./data/chroma")


def get_chroma_client() -> chromadb.Client:
    """Get or create ChromaDB client singleton."""
    global _chroma_client

    if _chroma_client is None:
        persist_path = Path(CHROMA_PERSIST_DIR)
        persist_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"Initializing ChromaDB at {persist_path}")
        _chroma_client = chromadb.PersistentClient(
            path=str(persist_path),
            settings=Settings(anonymized_telemetry=False)
        )
        logger.info("ChromaDB client initialized successfully")

    return _chroma_client


def get_collection(name: str = COLLECTION_NAME) -> chromadb.Collection:
    """Get or create ChromaDB collection."""
    global _collection

    if _collection is None or _collection.name != name:
        client = get_chroma_client()
        _collection = client.get_or_create_collection(
            name=name,
            metadata={"description": "Legal document chunks with embeddings"}
        )
        logger.info(f"Collection '{name}' ready with {_collection.count()} documents")

    return _collection


def add_documents(
    ids: List[str],
    texts: List[str],
    embeddings: List[List[float]],
    metadatas: Optional[List[Dict[str, Any]]] = None
) -> None:
    """Add documents with pre-computed embeddings to ChromaDB."""
    collection = get_collection()

    # ChromaDB requires metadatas if provided
    if metadatas is None:
        metadatas = [{"source": "neo4j"} for _ in ids]

    collection.add(
        ids=ids,
        embeddings=embeddings,
        documents=texts,
        metadatas=metadatas
    )
    logger.info(f"Added {len(ids)} documents to ChromaDB")


def query_similar(
    query_embedding: List[float],
    top_k: int = 10
) -> Dict[str, Any]:
    """
    Query ChromaDB for similar documents using embedding.

    Returns:
        Dict with keys: ids, documents, distances, metadatas
    """
    collection = get_collection()

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        include=["documents", "distances", "metadatas"]
    )

    return {
        "ids": results["ids"][0] if results["ids"] else [],
        "documents": results["documents"][0] if results["documents"] else [],
        "distances": results["distances"][0] if results["distances"] else [],
        "metadatas": results["metadatas"][0] if results["metadatas"] else []
    }


def get_collection_stats() -> Dict[str, Any]:
    """Get collection statistics."""
    try:
        collection = get_collection()
        return {
            "name": collection.name,
            "count": collection.count(),
            "persist_dir": CHROMA_PERSIST_DIR
        }
    except Exception as e:
        logger.error(f"Failed to get collection stats: {e}")
        return {"error": str(e)}


def clear_collection(name: str = COLLECTION_NAME) -> None:
    """Clear all documents from collection (for re-sync)."""
    global _collection
    client = get_chroma_client()

    try:
        client.delete_collection(name)
        _collection = None
        logger.info(f"Deleted collection '{name}'")
    except Exception as e:
        logger.warning(f"Collection '{name}' not found: {e}")
