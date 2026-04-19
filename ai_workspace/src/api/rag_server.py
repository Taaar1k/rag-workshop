"""
Shared RAG Server with FastAPI and Qdrant integration.
Provides OpenAI-compatible endpoints for RAG operations.
"""

import os
import sys
import logging
import yaml
import asyncio
from typing import List, Dict, Optional, Any
from pathlib import Path
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import qdrant_client
from qdrant_client.models import VectorParams, Distance, PointStruct, Filter, FilterSelector, FieldCondition, MatchValue
from slowapi.errors import RateLimitExceeded

# Add src to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))

try:
    from core.config import Settings
except ImportError:
    from ..core.config import Settings

# Import rate limiter
from .rate_limiter import limiter, rate_limit_exceeded_handler, get_rate_limit_for_user

# Import health checker
from .health_check import health_checker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import scanner manager
from .scanner_manager import (
    initialize_scanner,
    start_scanner,
    stop_scanner,
    get_scanner_status,
    router as scanner_router,
)

# Load config for scanner
_config_path = Path(__file__).parent.parent.parent / "config" / "default.yaml"
_dir_scan_config = {}
if _config_path.exists():
    with open(_config_path, "r", encoding="utf-8") as f:
        _cfg = yaml.safe_load(f)
        _dir_scan_config = _cfg.get("directory_scanning", {})


@asynccontextmanager
async def lifespan(app_fastapi: FastAPI):
    # Startup
    logger.info("RAG server lifespan startup...")
    await initialize_scanner(_dir_scan_config)
    await start_scanner()
    yield
    # Shutdown
    logger.info("RAG server lifespan shutdown...")
    await stop_scanner()


# Initialize FastAPI app with lifespan
app = FastAPI(
    title="Shared RAG API",
    description="OpenAI-compatible RAG server with Qdrant vector storage",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add rate limit exception handler
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

# Add slowapi state for rate limit tracking
app.state.limiter = limiter

# Include scanner router
app.include_router(scanner_router, prefix="/scanner", tags=["scanner"])

# Global instances
settings = Settings()
qdrant_client_instance: Optional[qdrant_client.QdrantClient] = None
embedding_model_instance: Any = None
llm_model_instance: Any = None
directory_scanner_instance: Any = None


# Pydantic Models for OpenAI-compatible API
class Message(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = "shared-rag-v1"
    messages: List[Message]
    temperature: float = Field(default=0.7, ge=0.0, le=1.0)
    top_p: float = Field(default=1.0, ge=0.0, le=1.0)
    n: int = Field(default=1, ge=1, le=10)
    max_tokens: int = Field(default=512, ge=1, le=4096)
    stream: bool = False
    stop: Optional[List[str]] = None
    presence_penalty: float = Field(default=0.0, ge=-2.0, le=2.0)
    frequency_penalty: float = Field(default=0.0, ge=-2.0, le=2.0)


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[Dict[str, Any]]
    usage: Dict[str, int]


class EmbeddingRequest(BaseModel):
    model: str = "nomic-embed-text-v1.5"
    input: str | List[str]
    encoding_format: str = "float"


class EmbeddingResponse(BaseModel):
    object: str = "list"
    data: List[Dict[str, Any]]
    model: str
    usage: Dict[str, int]


class Document(BaseModel):
    id: str
    text: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RAGQueryRequest(BaseModel):
    query: str
    top_k: int = Field(default=5, ge=1, le=100)
    filters: Optional[Dict[str, Any]] = None
    temperature: float = Field(default=0.7, ge=0.0, le=1.0)
    max_tokens: int = Field(default=512, ge=1, le=4096)


class RAGQueryResponse(BaseModel):
    answer: str
    sources: List[Dict[str, Any]]
    metadata: Dict[str, Any]


# Health check endpoints (exempt from rate limiting)
@app.get("/health")
@limiter.exempt
async def health_check(request: Request):
    """Lightweight health check (uses cache)."""
    health = await health_checker.get_overall_health(verbose=False)
    return health


@app.get("/health/verbose")
@limiter.exempt
async def health_check_verbose(request: Request):
    """Detailed health check (no cache, checks all components)."""
    health = await health_checker.get_overall_health(verbose=True)
    health["cache_enabled"] = False
    return health


@app.get("/metrics")
@limiter.exempt
async def metrics(request: Request):
    """Prometheus-compatible metrics endpoint."""
    health = await health_checker.get_overall_health(verbose=False)
    metrics_output = health_checker.get_prometheus_metrics(health)
    return JSONResponse(content=metrics_output, media_type="text/plain")


# Rate limit status endpoint
@app.get("/rate-limit-status")
@limiter.exempt
async def rate_limit_status(request: Request):
    """Get current rate limit status for the caller."""
    return {
        "limit": getattr(request.state, 'rate_limit', None),
        "remaining": getattr(request.state, 'rate_limit_remaining', None),
        "reset": getattr(request.state, 'rate_limit_reset', None)
    }


# OpenAI-compatible endpoints
@app.post("/v1/chat/completions")
@limiter.limit("1000 per minute")
async def chat_completions(request: Request, body: ChatCompletionRequest):
    """
    OpenAI-compatible endpoint for chat completions with RAG.
    Uses Qdrant for vector search and LLM for response generation.
    """
    try:
        # Validate messages
        if not body.messages:
            raise HTTPException(status_code=422, detail="messages field is required and cannot be empty")
        
        # Extract query from messages
        query = body.messages[-1].content if body.messages else ""
        
        # Perform RAG query
        rag_response = perform_rag_query(
            query=query,
            top_k=body.top_k if hasattr(body, 'top_k') else 5,
            temperature=body.temperature
        )
        
        return ChatCompletionResponse(
            id=f"chatcmpl-{int(datetime.now().timestamp())}",
            created=int(datetime.now().timestamp()),
            model=body.model,
            choices=[{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": rag_response["answer"]
                },
                "finish_reason": "stop"
            }],
            usage={
                "prompt_tokens": len(query.split()),
                "completion_tokens": len(rag_response["answer"].split()),
                "total_tokens": len(query.split()) + len(rag_response["answer"].split())
            }
        )
    except HTTPException:
        # Re-raise HTTP exceptions (422, 400, etc.) without wrapping
        raise
    except Exception as e:
        logger.error(f"Error in chat completions: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/embeddings")
@limiter.limit("1000 per minute")
async def create_embeddings(request: Request, body: EmbeddingRequest):
    """
    OpenAI-compatible endpoint for embedding generation.
    Uses sentence-transformers for embedding generation.
    """
    try:
        inputs = body.input if isinstance(body.input, list) else [body.input]
        
        # Generate embeddings
        embeddings = []
        for text in inputs:
            embedding = generate_embedding(text)
            embeddings.append({
                "object": "embedding",
                "embedding": embedding,
                "index": len(embeddings)
            })
        
        return EmbeddingResponse(
            object="list",
            data=embeddings,
            model=body.model,
            usage={
                "prompt_tokens": sum(len(text.split()) for text in inputs),
                "total_tokens": sum(len(text.split()) for text in inputs)
            }
        )
    except Exception as e:
        logger.error(f"Error in embeddings: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# RAG-specific endpoints
@app.post("/rag/query")
@limiter.limit("1000 per minute")
async def rag_query(request: Request, body: RAGQueryRequest):
    """
    Custom RAG query endpoint with vector search and LLM generation.
    """
    try:
        response = perform_rag_query(
            query=body.query,
            top_k=body.top_k,
            temperature=body.temperature
        )
        return response
    except Exception as e:
        logger.error(f"Error in RAG query: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/rag/index")
@limiter.limit("1000 per minute")
async def index_document(request: Request, document: Document):
    """
    Index a document into the vector store.
    """
    try:
        # Generate embedding for the document
        embedding = generate_embedding(document.text)
        
        # Store in Qdrant
        qdrant_client_instance.upsert(
            collection_name="rag_documents",
            points=[PointStruct(
                id=document.id,
                vector=embedding,
                payload={
                    "text": document.text,
                    **document.metadata
                }
            )]
        )
        
        return {"status": "success", "document_id": document.id}
    except Exception as e:
        logger.error(f"Error indexing document: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Utility functions
def initialize_qdrant():
    """Initialize Qdrant client and create collection if not exists.
    
    Returns None if Qdrant is not available (graceful degradation).
    """
    global qdrant_client_instance
    
    try:
        host = os.getenv("QDRANT_HOST", "localhost")
        port = int(os.getenv("QDRANT_PORT", 6333))
        
        qdrant_client_instance = qdrant_client.QdrantClient(host=host, port=port)
        
        # Create collection if it doesn't exist
        collection_name = "rag_documents"
        if not qdrant_client_instance.collection_exists(collection_name):
            qdrant_client_instance.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=768,  # Default embedding dimension
                    distance=Distance.COSINE
                )
            )
        logger.info(f"Initialized Qdrant client at {host}:{port}")
        
        return qdrant_client_instance
    except Exception as e:
        logger.warning(f"Qdrant initialization failed: {str(e)}, running in offline mode")
        qdrant_client_instance = None
        return None


def initialize_embedding_model():
    """Initialize sentence-transformers model."""
    global embedding_model_instance
    
    try:
        from sentence_transformers import SentenceTransformer
        
        model_name = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
        embedding_model_instance = SentenceTransformer(model_name)
        logger.info(f"Initialized embedding model: {model_name}")
        
        return embedding_model_instance
    except Exception as e:
        logger.error(f"Failed to initialize embedding model: {str(e)}")
        raise


def generate_embedding(text: str) -> List[float]:
    """Generate embedding for a single text."""
    if embedding_model_instance is None:
        initialize_embedding_model()
    
    embedding = embedding_model_instance.encode(text)
    return embedding.tolist()


def initialize_llm_model():
    """Initialize GGUF model via llama.cpp."""
    global llm_model_instance
    
    try:
        from llama_cpp import Llama
        
        model_path = os.getenv("LLM_MODEL_PATH", "models/llm/default.gguf")
        
        llm_model_instance = Llama(
            model_path=model_path,
            n_ctx=2048,
            n_threads=4,
            n_gpu_layers=0  # CPU only for now
        )
        
        logger.info(f"Initialized LLM model: {model_path}")
        return llm_model_instance
    except Exception as e:
        logger.error(f"Failed to initialize LLM model: {str(e)}")
        # Fallback to API-based LLM if local model fails
        logger.info("Falling back to API-based LLM")
        return None


def perform_rag_query(query: str, top_k: int = 5, temperature: float = 0.7) -> Dict[str, Any]:
    """
    Perform RAG query: vector search + LLM generation.
    """
    # Search vector store
    if qdrant_client_instance is None:
        initialize_qdrant()
    
    # Generate query embedding
    query_embedding = generate_embedding(query)
    
    # Search Qdrant
    try:
        search_results = qdrant_client_instance.search(
            collection_name="rag_documents",
            query_vector=query_embedding,
            limit=top_k
        )
    except Exception as e:
        logger.warning(f"Qdrant search failed: {str(e)}, returning empty results")
        search_results = []
    
    # Build context from search results
    context = "\n\n".join([hit.payload.get("text", "") for hit in search_results])
    sources = [
        {
            "id": hit.id,
            "score": hit.score,
            "text": hit.payload.get("text", "")[:200] + "..."
        }
        for hit in search_results
    ]
    
    # Generate response with LLM
    if llm_model_instance is None:
        try:
            initialize_llm_model()
        except Exception as e:
            logger.warning(f"Failed to initialize local LLM: {str(e)}, using fallback")
    
    if llm_model_instance:
        # Use local LLM
        prompt = f"""Context: {context}

Question: {query}

Answer:"""
        
        try:
            response = llm_model_instance(
                prompt,
                max_tokens=512,
                temperature=temperature
            )
            answer = response["choices"][0]["text"].strip()
        except Exception as e:
            logger.warning(f"LLM generation failed: {str(e)}, using fallback")
            answer = f"Based on the retrieved documents:\n\n{context}\n\nQuestion: {query}"
    else:
        # Fallback: use retrieved context as answer
        answer = f"Based on the retrieved documents:\n\n{context}\n\nQuestion: {query}"
    
    return {
        "answer": answer,
        "sources": sources,
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "query": query,
            "top_k": top_k
        }
    }


# Startup event (kept for backward compatibility; scanner now uses lifespan)
@app.on_event("startup")
async def startup_event():
    """Initialize services on server startup."""
    logger.info("Starting RAG server...")

    # Initialize Qdrant
    try:
        initialize_qdrant()
        logger.info("Qdrant initialized successfully")
    except Exception as e:
        logger.warning(f"Qdrant initialization failed: {str(e)}")

    # Initialize embedding model
    try:
        initialize_embedding_model()
        logger.info("Embedding model initialized successfully")
    except Exception as e:
        logger.error(f"Embedding model initialization failed: {str(e)}")

    # Initialize LLM model (optional)
    try:
        initialize_llm_model()
        logger.info("LLM model initialized successfully")
    except Exception as e:
        logger.warning(f"LLM model initialization failed: {str(e)}")

    logger.info("RAG server started successfully")


# Shutdown event (kept for backward compatibility; scanner now uses lifespan)
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on server shutdown."""
    logger.info("Shutting down RAG server...")

    if qdrant_client_instance:
        qdrant_client_instance.close()

    logger.info("RAG server shutdown complete")


def _load_scanning_config() -> Optional[Dict[str, Any]]:
    """Load directory_scanning config from default.yaml."""
    config_path = Path(__file__).parent.parent.parent / "config" / "default.yaml"
    if not config_path.exists():
        return None
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        return config.get("directory_scanning")
    except Exception as e:
        logger.warning(f"Failed to load directory_scanning config: {str(e)}")
        return None


def _init_directory_scanner():
    """Initialize DirectoryScannerWorker from config."""
    global directory_scanner_instance
    config = _load_scanning_config()
    if not config:
        logger.info("No directory_scanning config found. Scanning disabled.")
        return

    enabled = config.get("enabled", True)
    if not enabled:
        logger.info("Directory scanning is disabled (enabled: false).")
        return

    watched_dirs = config.get("watched_directories", [])
    if not watched_dirs:
        logger.info("No watched directories configured. Scanning disabled.")
        return

    state_file = config.get("state", {}).get("persistence_file", "./ai_workspace/memory/index_state.json")
    debounce_ms = config.get("scan", {}).get("debounce_ms", 500)
    poll_interval_s = config.get("scan", {}).get("poll_interval_s", 60)
    allowed_exts = config.get("allowed_extensions", [".txt", ".md", ".json", ".csv"])
    chunk_size = config.get("indexing", {}).get("chunk_size", 512)
    chunk_overlap = config.get("indexing", {}).get("chunk_overlap", 50)

    # Initialize MemoryManager and IncrementalIndexManager
    from core.memory_manager import MemoryManager, MemoryConfig
    from core.incremental_index_manager import IncrementalIndexManager

    mem_config = MemoryConfig()
    mem_manager = MemoryManager(mem_config)
    index_mgr = IncrementalIndexManager(
        memory_manager=mem_manager,
        state_file=state_file,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        allowed_extensions=allowed_exts,
    )

    # Create DirectoryScannerWorker
    from core.directory_scanner import DirectoryScannerWorker
    directory_scanner_instance = DirectoryScannerWorker(
        index_manager=index_mgr,
        watched_directories=watched_dirs,
        debounce_ms=debounce_ms,
        poll_interval_s=poll_interval_s,
        enabled=True,
    )

    # Start the scanner
    asyncio.get_event_loop().run_until_complete(directory_scanner_instance.start())
    logger.info("Directory scanner initialized and started")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "rag_server:app",
        host=settings.host,
        port=settings.port,
        reload=True
    )
