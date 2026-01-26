#!/usr/bin/env python3
"""Sync embeddings from Neo4j to ChromaDB.

Migrates document chunks and their embeddings from Neo4j graph database
to ChromaDB vector store for fair vector-only vs graph comparison.

Usage:
    python scripts/sync_neo4j_to_chroma.py [--clear] [--batch-size 100]
"""
import sys
import os
import argparse
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.db.neo4j import get_neo4j_client
from api.db.chroma import (
    get_collection,
    add_documents,
    clear_collection,
    get_collection_stats,
    COLLECTION_NAME
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def fetch_neo4j_documents(namespace: str = "Test_rel_2", batch_size: int = 100):
    """Fetch documents with embeddings from Neo4j in batches."""
    client = get_neo4j_client()

    # Get total count
    count_result = client.execute_query(f"""
        MATCH (n:{namespace})
        WHERE n.text IS NOT NULL AND n.original_embedding IS NOT NULL
        RETURN count(n) as total
    """)
    total = count_result[0]["total"] if count_result else 0
    logger.info(f"Found {total} documents with embeddings in Neo4j")

    # Fetch in batches
    offset = 0
    while offset < total:
        query = f"""
            MATCH (n:{namespace})
            WHERE n.text IS NOT NULL AND n.original_embedding IS NOT NULL
            RETURN n.id AS id, n.text AS text, n.original_embedding AS embedding
            ORDER BY n.id
            SKIP $offset
            LIMIT $limit
        """
        results = client.execute_query(query, {"offset": offset, "limit": batch_size})

        if not results:
            break

        yield results
        offset += batch_size
        logger.info(f"Fetched {min(offset, total)}/{total} documents")


def sync_to_chroma(clear: bool = False, batch_size: int = 100, namespace: str = "Test_rel_2"):
    """Sync all documents from Neo4j to ChromaDB."""

    if clear:
        logger.info("Clearing existing ChromaDB collection...")
        clear_collection(COLLECTION_NAME)

    collection = get_collection()
    existing_count = collection.count()

    if existing_count > 0 and not clear:
        logger.info(f"ChromaDB already has {existing_count} documents. Use --clear to resync.")
        return

    total_synced = 0

    for batch in fetch_neo4j_documents(namespace=namespace, batch_size=batch_size):
        ids = [doc["id"] for doc in batch]
        texts = [doc["text"] for doc in batch]
        embeddings = [doc["embedding"] for doc in batch]

        # Skip if already exists
        existing = set(collection.get(ids=ids, include=[])["ids"])
        new_ids = []
        new_texts = []
        new_embeddings = []

        for i, doc_id in enumerate(ids):
            if doc_id not in existing:
                new_ids.append(doc_id)
                new_texts.append(texts[i])
                new_embeddings.append(embeddings[i])

        if new_ids:
            add_documents(
                ids=new_ids,
                texts=new_texts,
                embeddings=new_embeddings,
                metadatas=[{"source": "neo4j", "namespace": namespace} for _ in new_ids]
            )
            total_synced += len(new_ids)

    stats = get_collection_stats()
    logger.info(f"Sync complete! Total synced: {total_synced}, Collection size: {stats['count']}")


def main():
    parser = argparse.ArgumentParser(description="Sync Neo4j embeddings to ChromaDB")
    parser.add_argument("--clear", action="store_true", help="Clear existing collection before sync")
    parser.add_argument("--batch-size", type=int, default=100, help="Batch size for fetching")
    parser.add_argument("--namespace", type=str, default="Test_rel_2", help="Neo4j namespace/label")
    args = parser.parse_args()

    sync_to_chroma(clear=args.clear, batch_size=args.batch_size, namespace=args.namespace)


if __name__ == "__main__":
    main()
