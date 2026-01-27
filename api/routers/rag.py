"""RAG API router for query endpoints."""
import asyncio
import time
import uuid
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Dict, List, Any, Optional
import logging

from api.schemas import (
    QueryRequest,
    RetrieveRequest,
    RetrieveResponse,
    RetrieveChunk,
    RerankRequest,
    RerankResponse
)
from api.services.rag_agent import get_rag_agent
from api.services.tools import retrieve_from_database, retrieve_with_graph_context
from api.services.reranker import rerank_chunks
from api.services.gemini import generate_answer, generate_answer_async
from api.routers.stats import record_response_time

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/rag", tags=["rag"])


@router.post("/query")
async def query_rag_agent(request: QueryRequest):
    """
    Query RAG agent with streaming or non-streaming response.

    Streaming (default):
    - Returns SSE events in real-time
    - Events: tool_start, tool_end, text, sources, done

    Non-streaming:
    - Returns complete JSON response
    """
    agent = get_rag_agent()

    if request.stream:
        return StreamingResponse(
            agent.query(request.question),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"  # Disable nginx buffering
            }
        )
    else:
        try:
            result = await agent.query_non_streaming(request.question)
            return result
        except Exception as e:
            logger.error(f"RAG query failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))


@router.post("/retrieve", response_model=RetrieveResponse)
async def retrieve_chunks_endpoint(request: RetrieveRequest):
    """
    Direct access to retrieve_from_database tool.
    Useful for testing and debugging retrieval.
    """
    try:
        result = retrieve_from_database(
            prompt=request.prompt,
            top_k=request.top_k,
            namespace=request.namespace
        )

        # Convert to response format
        chunks = [
            RetrieveChunk(id=c.get("id", ""), text=c.get("text", ""), score=s)
            for c, s in zip(result.chunks, result.scores)
        ]

        return RetrieveResponse(
            chunks=chunks,
            source_ids=result.source_ids,
            scores=result.scores
        )
    except Exception as e:
        logger.error(f"Retrieval failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rerank", response_model=RerankResponse)
async def rerank_chunks_endpoint(request: RerankRequest):
    """
    Direct access to reranking tool.
    Useful for testing reranker quality.
    """
    try:
        reranked, scores = rerank_chunks(
            query=request.query,
            chunks=request.chunks,
            top_n=request.top_n
        )

        return RerankResponse(
            reranked_chunks=reranked,
            scores=scores
        )
    except Exception as e:
        logger.error(f"Reranking failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tools")
async def list_tools():
    """List available RAG tools and their descriptions."""
    from api.services.tools import get_tool_descriptions
    return {"tools": get_tool_descriptions()}


@router.get("/sample-questions")
async def get_sample_questions_endpoint(count: int = 8, shuffle: bool = True):
    """
    Get sample questions from QA dataset for the UI.

    Returns questions from Google Sheet QA dataset, or fallback questions
    if the sheet is unavailable.
    """
    from api.services.qa_questions import get_sample_questions
    questions = get_sample_questions(count=count, shuffle=shuffle)
    return {"questions": questions}


# ============ Compare Endpoint for Vector vs Graph ============

class CompareRequest(BaseModel):
    """Request for comparing Vector vs Graph RAG."""
    question: str


class SourceItem(BaseModel):
    """Source reference item."""
    text: str
    score: float
    documentId: str
    documentName: Optional[str] = None


class MetricsItem(BaseModel):
    """Metrics for a RAG result."""
    latencyMs: int
    chunksUsed: int
    confidenceScore: Optional[float] = None
    graphNodesUsed: Optional[int] = None
    graphHops: Optional[int] = None


class VectorResult(BaseModel):
    """Vector-only RAG result."""
    answer: str
    sources: List[SourceItem]
    metrics: MetricsItem


class GraphContextItem(BaseModel):
    """Graph context node."""
    id: str
    label: str
    type: str


class GraphResult(BaseModel):
    """Graph-enhanced RAG result."""
    answer: str
    sources: List[SourceItem]
    cypherQuery: Optional[str] = None
    graphContext: List[Dict[str, Any]]
    metrics: MetricsItem


class CompareResponse(BaseModel):
    """Response comparing Vector vs Graph results."""
    questionId: str
    question: str
    vector: VectorResult
    graph: GraphResult
    timestamp: str


@router.post("/compare", response_model=CompareResponse)
async def compare_vector_graph(request: CompareRequest):
    """
    Compare Vector-only vs Graph-enhanced RAG for the same question.

    Returns both results side-by-side for annotation/evaluation.
    Runs retrieval and LLM calls in parallel for faster response.
    """
    question = request.question
    question_id = f"q_{uuid.uuid4().hex[:8]}"

    start_time = time.time()

    # ============ Run both retrievals in parallel ============
    async def get_vector_chunks():
        return await asyncio.to_thread(retrieve_from_database, prompt=question, top_k=20)

    async def get_graph_chunks():
        return await asyncio.to_thread(retrieve_with_graph_context, prompt=question, top_k=20)

    try:
        vector_result, graph_result = await asyncio.gather(
            get_vector_chunks(),
            get_graph_chunks()
        )
    except Exception as e:
        logger.error(f"Retrieval failed: {e}")
        raise HTTPException(status_code=500, detail=f"Retrieval failed: {str(e)}")

    retrieval_time = time.time()

    # ============ Rerank both in parallel ============
    async def rerank_vector():
        return await asyncio.to_thread(
            rerank_chunks, query=question, chunks=vector_result.chunks, top_n=5
        )

    async def rerank_graph():
        return await asyncio.to_thread(
            rerank_chunks, query=question, chunks=graph_result.chunks, top_n=5
        )

    try:
        (vector_reranked, vector_scores), (graph_reranked, graph_scores) = await asyncio.gather(
            rerank_vector(),
            rerank_graph()
        )
    except Exception as e:
        logger.error(f"Reranking failed: {e}")
        vector_reranked, vector_scores = [], []
        graph_reranked, graph_scores = [], []

    rerank_time = time.time()

    # ============ Generate answers in parallel with Gemini 2.5 Pro ============
    try:
        vector_answer, graph_answer = await asyncio.gather(
            generate_answer_async(question, vector_reranked),
            generate_answer_async(question, graph_reranked)
        )
    except Exception as e:
        logger.error(f"LLM generation failed: {e}")
        vector_answer = f"[Lỗi Vector] {str(e)}"
        graph_answer = f"[Lỗi Graph] {str(e)}"

    end_time = time.time()

    # Calculate latencies
    vector_latency = int((end_time - start_time) * 1000)
    graph_latency = int((end_time - start_time) * 1000)

    # Record response times for stats
    total_response_time = end_time - start_time
    record_response_time(total_response_time)

    # Build sources
    vector_sources = [
        SourceItem(
            text=chunk.get("text", "")[:300],
            score=score,
            documentId=chunk.get("id", ""),
            documentName="Văn bản pháp luật"
        )
        for chunk, score in zip(vector_reranked[:3], vector_scores[:3])
    ]

    graph_sources = [
        SourceItem(
            text=chunk.get("text", "")[:300],
            score=score,
            documentId=chunk.get("id", ""),
            documentName="Văn bản pháp luật"
        )
        for chunk, score in zip(graph_reranked[:3], graph_scores[:3])
    ]

    # Count graph nodes used
    graph_context = graph_result.graph_context if graph_result else []
    cypher_query = graph_result.cypher_query if graph_result else None
    graph_nodes_count = len([c for c in graph_result.chunks if not c.get("is_seed", True)]) if graph_result else 0

    return CompareResponse(
        questionId=question_id,
        question=question,
        vector=VectorResult(
            answer=vector_answer,
            sources=vector_sources,
            metrics=MetricsItem(
                latencyMs=vector_latency,
                chunksUsed=len(vector_reranked)
            )
        ),
        graph=GraphResult(
            answer=graph_answer,
            sources=graph_sources,
            cypherQuery=cypher_query,
            graphContext=graph_context,
            metrics=MetricsItem(
                latencyMs=graph_latency,
                chunksUsed=len(graph_reranked),
                graphNodesUsed=graph_nodes_count + len(graph_reranked),
                graphHops=1
            )
        ),
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    )
