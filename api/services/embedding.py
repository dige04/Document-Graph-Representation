"""Embedding service for RAG queries using Gemini API.

Uses Gemini embedding API to avoid loading heavy local models.
Memory-optimized for Render free tier (512MB limit).
"""
import os
import logging
from typing import List

logger = logging.getLogger(__name__)

# Gemini embedding model
_GEMINI_EMBEDDING_MODEL = "text-embedding-004"


def _get_gemini_client():
    """Get configured Gemini client."""
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY not set")

    import google.generativeai as genai
    genai.configure(api_key=api_key)
    return genai


def embed_query(text: str) -> List[float]:
    """
    Embed a query text using Gemini embedding API.

    Args:
        text: Query string to embed

    Returns:
        List of floats (768 dimensions)
    """
    if not text or not text.strip():
        raise ValueError("Text cannot be empty")
    if len(text) > 10000:
        logger.warning(f"Text truncated from {len(text)} to 10000 chars")
        text = text[:10000]

    try:
        genai = _get_gemini_client()
        result = genai.embed_content(
            model=f"models/{_GEMINI_EMBEDDING_MODEL}",
            content=text,
            task_type="retrieval_query"
        )
        return result['embedding']
    except Exception as e:
        logger.error(f"Gemini embedding failed: {e}")
        raise


def embed_texts(texts: List[str]) -> List[List[float]]:
    """
    Embed multiple texts using Gemini embedding API.

    Args:
        texts: List of strings to embed

    Returns:
        List of embedding vectors
    """
    genai = _get_gemini_client()
    embeddings = []

    for text in texts:
        if len(text) > 10000:
            text = text[:10000]
        try:
            result = genai.embed_content(
                model=f"models/{_GEMINI_EMBEDDING_MODEL}",
                content=text,
                task_type="retrieval_document"
            )
            embeddings.append(result['embedding'])
        except Exception as e:
            logger.error(f"Gemini embedding failed for text: {e}")
            # Return zero vector as fallback
            embeddings.append([0.0] * 768)

    return embeddings


def get_embedding_dimension() -> int:
    """Get the dimension of embeddings (768 for Gemini text-embedding-004)."""
    return 768
