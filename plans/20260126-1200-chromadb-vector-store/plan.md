# ChromaDB Vector Store Integration

## Objective
Add ChromaDB as separate vector database for fair comparison: **Vector (Chroma)** vs **Graph (Neo4j)**

## Current State
- Vector-only: Uses Neo4j word-match (not true vector search)
- Graph-enhanced: Uses Neo4j with graph traversal
- Both use same data source → unfair comparison

## Target State
- Vector-only: ChromaDB with embedding similarity (true vector search)
- Graph-enhanced: Neo4j with graph traversal (unchanged)
- Fair A/B comparison for evaluation

## Phases

| Phase | Description | Status |
|-------|-------------|--------|
| 01 | Add ChromaDB dependency & service | ⏳ Pending |
| 02 | Create sync script Neo4j → Chroma | ⏳ Pending |
| 03 | Update vector retrieval to use Chroma | ⏳ Pending |
| 04 | Test & verify comparison works | ⏳ Pending |

## Architecture

```
┌─────────────────┐     ┌─────────────────┐
│  Vector-only    │     │  Graph-enhanced │
│   (ChromaDB)    │     │    (Neo4j)      │
└────────┬────────┘     └────────┬────────┘
         │                       │
         ▼                       ▼
   Pure embedding          Embedding +
   similarity              Graph traversal
```

## Files to Create/Modify
- `requirements-api.txt` - Add chromadb
- `api/db/chroma.py` - ChromaDB client
- `api/services/tools.py` - Update vector retrieval
- `scripts/sync_neo4j_to_chroma.py` - Data sync script

## Success Criteria
- [ ] ChromaDB initialized with embeddings from Neo4j
- [ ] Vector retrieval uses Chroma (pure embedding search)
- [ ] Graph retrieval uses Neo4j (unchanged)
- [ ] Compare endpoint shows different source IDs
