"""Embedding service for RAG queries using PhoBERT.

Uses vinai/phobert-base to match the embeddings stored in Neo4j.
The stored embeddings were created using PhoBERT with mean pooling.
"""
import os
import logging
from typing import List
import numpy as np
import torch

# Avoid TensorFlow/Keras issues - use PyTorch backend only
os.environ["TRANSFORMERS_NO_TF"] = "1"
os.environ["USE_TORCH"] = "1"

logger = logging.getLogger(__name__)

# Lazy initialization
_tokenizer = None
_model = None
_model_name = "vinai/phobert-base"
_max_length = 256


def _get_phobert():
    """Get or create PhoBERT model singleton."""
    global _tokenizer, _model

    if _model is None:
        try:
            from transformers import AutoTokenizer, AutoModel
            logger.info(f"Loading embedding model: {_model_name}")
            _tokenizer = AutoTokenizer.from_pretrained(_model_name, use_fast=False)
            _model = AutoModel.from_pretrained(_model_name)
            _model.eval()
            logger.info("PhoBERT model loaded successfully")
        except ImportError:
            logger.error("transformers not installed")
            raise ImportError("transformers is required for PhoBERT embedding")
        except Exception as e:
            logger.error(f"Failed to load PhoBERT model: {e}")
            raise

    return _tokenizer, _model


def embed_query(text: str) -> List[float]:
    """
    Embed a query text using PhoBERT with mean pooling.

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

    tokenizer, model = _get_phobert()

    with torch.no_grad():
        inputs = tokenizer(
            text,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=_max_length
        )
        outputs = model(**inputs)
        # Mean pooling over sequence (same as original indexing)
        embedding = outputs.last_hidden_state.squeeze(0).mean(0).numpy()

    return embedding.tolist()


def embed_texts(texts: List[str]) -> List[List[float]]:
    """
    Embed multiple texts in batch using PhoBERT.

    Args:
        texts: List of strings to embed

    Returns:
        List of embedding vectors (768 dimensions each)
    """
    tokenizer, model = _get_phobert()
    embeddings = []

    with torch.no_grad():
        for text in texts:
            if len(text) > 10000:
                text = text[:10000]
            inputs = tokenizer(
                text,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=_max_length
            )
            outputs = model(**inputs)
            emb = outputs.last_hidden_state.squeeze(0).mean(0).numpy()
            embeddings.append(emb.tolist())

    return embeddings


def get_embedding_dimension() -> int:
    """Get the dimension of embeddings (768 for PhoBERT)."""
    return 768
