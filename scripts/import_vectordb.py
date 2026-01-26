#!/usr/bin/env python3
"""Extract documents from old ChromaDB and import to new ChromaDB with fresh embeddings.

Since the old ChromaDB format is incompatible, we extract text and metadata from SQLite
and regenerate embeddings using the current PhoBERT model.
"""
import sys
import os
import sqlite3
import json

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.db.chroma import get_collection, clear_collection, COLLECTION_NAME, get_collection_stats
from api.services.embedding import embed_query

# Old ChromaDB path
OLD_CHROMA_PATH = "data/chromadb/chroma_Hybrid_phoBERT/chroma.sqlite3"
BATCH_SIZE = 50


def extract_documents(db_path: str, batch_size: int = 100):
    """Extract documents and metadata from old ChromaDB SQLite."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get total count from fulltext search table
    cursor.execute("SELECT COUNT(*) FROM embedding_fulltext_search")
    total = cursor.fetchone()[0]
    print(f"Total documents: {total}")

    # Get embeddings with their rowid (matches fulltext_search rowid)
    cursor.execute("SELECT COUNT(*) FROM embeddings")
    emb_count = cursor.fetchone()[0]
    print(f"Total embeddings: {emb_count}")

    # Join embeddings with fulltext search by rowid
    offset = 0
    while offset < emb_count:
        # Get embedding IDs and document text
        cursor.execute("""
            SELECT e.id, e.embedding_id, efs.string_value as document
            FROM embeddings e
            JOIN embedding_fulltext_search efs ON efs.rowid = e.id
            ORDER BY e.id
            LIMIT ? OFFSET ?
        """, (batch_size, offset))

        rows = cursor.fetchall()
        if not rows:
            break

        # Get metadata for these embeddings
        embedding_internal_ids = [r[0] for r in rows]
        placeholders = ",".join(["?" for _ in embedding_internal_ids])

        cursor.execute(f"""
            SELECT id, key, string_value, int_value, float_value
            FROM embedding_metadata
            WHERE id IN ({placeholders})
        """, embedding_internal_ids)

        metadata_rows = cursor.fetchall()

        # Group metadata by internal id
        metadata_map = {}
        for row in metadata_rows:
            internal_id, key, str_val, int_val, float_val = row
            if internal_id not in metadata_map:
                metadata_map[internal_id] = {}
            value = str_val if str_val is not None else (int_val if int_val is not None else float_val)
            if value is not None:
                metadata_map[internal_id][key] = value

        # Yield batch
        batch = []
        for internal_id, emb_id, document in rows:
            batch.append({
                "id": emb_id,
                "document": document,
                "metadata": metadata_map.get(internal_id, {})
            })

        yield batch
        offset += batch_size
        print(f"Extracted {min(offset, emb_count)}/{emb_count}")

    conn.close()


def import_to_new_chroma(clear: bool = True):
    """Import extracted documents to new ChromaDB with fresh embeddings."""
    if clear:
        print("Clearing existing collection...")
        clear_collection(COLLECTION_NAME)

    collection = get_collection()
    total_imported = 0
    failed = 0

    for batch in extract_documents(OLD_CHROMA_PATH, batch_size=BATCH_SIZE):
        ids = []
        documents = []
        embeddings = []
        metadatas = []

        for doc in batch:
            if not doc["document"] or len(doc["document"].strip()) < 10:
                continue

            try:
                # Generate fresh embedding with PhoBERT
                embedding = embed_query(doc["document"][:512])  # Limit text length
                ids.append(doc["id"])
                documents.append(doc["document"])
                embeddings.append(embedding)
                metadatas.append(doc["metadata"])
            except Exception as e:
                print(f"Failed to embed {doc['id']}: {e}")
                failed += 1

        if ids:
            try:
                collection.add(
                    ids=ids,
                    documents=documents,
                    embeddings=embeddings,
                    metadatas=metadatas
                )
                total_imported += len(ids)
            except Exception as e:
                print(f"Failed to add batch: {e}")
                failed += len(ids)

        print(f"Imported {total_imported} documents (failed: {failed})")

    stats = get_collection_stats()
    print(f"\n=== Import Complete ===")
    print(f"Total imported: {total_imported}")
    print(f"Failed: {failed}")
    print(f"Collection stats: {stats}")


def preview():
    """Preview documents from old ChromaDB."""
    for batch in extract_documents(OLD_CHROMA_PATH, batch_size=5):
        for doc in batch[:3]:
            print(f"\n--- Document {doc['id']} ---")
            print(f"Text: {doc['document'][:200]}...")
            print(f"Metadata: {doc['metadata']}")
        break


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--preview", action="store_true", help="Preview documents without importing")
    parser.add_argument("--clear", action="store_true", default=True, help="Clear existing collection")
    args = parser.parse_args()

    if args.preview:
        preview()
    else:
        import_to_new_chroma(clear=args.clear)
