#!/usr/bin/env python3
"""Import exported embeddings to new ChromaDB.

Reads JSONL file with pre-computed embeddings and imports to ChromaDB.
"""
import sys
import os
import json

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.db.chroma import get_collection, clear_collection, COLLECTION_NAME, get_collection_stats

INPUT_PATH = "data/chromadb/output/embeddings.jsonl"
BATCH_SIZE = 500


def import_embeddings(clear: bool = True):
    """Import embeddings from JSONL to ChromaDB."""
    if clear:
        print("Clearing existing collection...")
        clear_collection(COLLECTION_NAME)

    collection = get_collection()
    total_imported = 0

    # Read and import in batches
    batch_ids = []
    batch_docs = []
    batch_embeddings = []
    batch_metadatas = []

    with open(INPUT_PATH, 'r') as f:
        for line in f:
            record = json.loads(line)

            # Skip if no embedding
            if not record.get("embedding") or len(record["embedding"]) != 768:
                continue

            batch_ids.append(record["id"])
            batch_docs.append(record["document"])
            batch_embeddings.append(record["embedding"])

            # Clean metadata (remove chroma:document to avoid duplication)
            meta = record.get("metadata", {})
            if "chroma:document" in meta:
                del meta["chroma:document"]
            # Truncate long metadata values (ChromaDB has limits)
            for k, v in list(meta.items()):
                if isinstance(v, str) and len(v) > 500:
                    meta[k] = v[:500] + "..."
            batch_metadatas.append(meta)

            # Import batch
            if len(batch_ids) >= BATCH_SIZE:
                collection.add(
                    ids=batch_ids,
                    documents=batch_docs,
                    embeddings=batch_embeddings,
                    metadatas=batch_metadatas
                )
                total_imported += len(batch_ids)
                print(f"Imported {total_imported} documents")

                batch_ids = []
                batch_docs = []
                batch_embeddings = []
                batch_metadatas = []

    # Import remaining
    if batch_ids:
        collection.add(
            ids=batch_ids,
            documents=batch_docs,
            embeddings=batch_embeddings,
            metadatas=batch_metadatas
        )
        total_imported += len(batch_ids)

    stats = get_collection_stats()
    print(f"\n=== Import Complete ===")
    print(f"Total imported: {total_imported}")
    print(f"Collection stats: {stats}")


if __name__ == "__main__":
    import_embeddings(clear=True)
