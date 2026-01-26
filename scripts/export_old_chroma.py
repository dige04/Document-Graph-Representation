#!/usr/bin/env python3
"""Export embeddings from old ChromaDB format.

Runs in a Docker container with compatible ChromaDB version.
"""

import sys
import os
import json
import chromadb
from chromadb.config import Settings

# Path inside container
CHROMA_PATH = "/data/chroma_Hybrid_phoBERT"
OUTPUT_PATH = "/data/output/embeddings.jsonl"

def export_embeddings():
    """Export all embeddings to JSONL format."""
    print(f"Connecting to ChromaDB at {CHROMA_PATH}")
    client = chromadb.PersistentClient(
        path=CHROMA_PATH,
        settings=Settings(anonymized_telemetry=False)
    )

    collections = client.list_collections()
    print(f"Found collections: {[c.name for c in collections]}")

    for coll_info in collections:
        coll = client.get_collection(coll_info.name)
        count = coll.count()
        print(f"Collection {coll_info.name}: {count} documents")

        if count == 0:
            continue

        # Export in batches
        batch_size = 100
        offset = 0

        with open(OUTPUT_PATH, 'w') as f:
            while offset < count:
                # Get batch with embeddings
                results = coll.get(
                    limit=batch_size,
                    offset=offset,
                    include=["documents", "embeddings", "metadatas"]
                )

                for i, doc_id in enumerate(results["ids"]):
                    record = {
                        "id": doc_id,
                        "document": results["documents"][i] if results["documents"] else "",
                        "embedding": results["embeddings"][i] if results["embeddings"] else [],
                        "metadata": results["metadatas"][i] if results["metadatas"] else {}
                    }
                    f.write(json.dumps(record) + "\n")

                offset += batch_size
                print(f"Exported {min(offset, count)}/{count}")

        print(f"Exported to {OUTPUT_PATH}")
        break  # Only export first non-empty collection

if __name__ == "__main__":
    export_embeddings()
