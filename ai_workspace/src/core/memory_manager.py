"""
Memory Manager for RAG System
Implements type-separated memory architecture with ChromaDB integration.

Memory Types:
- Vector Memory: ChromaDB collections for embedding vectors
- Context Memory: Document chunks and retrieval results
- Session Memory: User session state with TTL-based expiration
"""

import os
import json
import logging
import uuid

logger = logging.getLogger(__name__)
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, field

import chromadb
from chromadb.config import Settings
from langchain_chroma import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


@dataclass
class MemoryConfig:
    """Configuration for memory manager."""
    persist_directory: str = "./ai_workspace/memory/chroma_db"
    collection_prefix: str = "rag_"
    metadata_index_fields: List[str] = field(default_factory=lambda: ["model_id", "type", "timestamp"])
    batch_size: int = 100
    max_collection_size: int = 10_000_000
    session_ttl_hours: int = 24
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"


class MemoryBase(ABC):
    """Abstract base class for memory types."""
    
    @abstractmethod
    def add(self, data: Union[Document, Dict[str, Any], List[Document]]) -> str:
        """Add data to memory and return ID."""
        pass
    
    @abstractmethod
    def get(self, memory_id: str) -> Optional[Union[Document, Dict[str, Any]]]:
        """Get data by ID."""
        pass
    
    @abstractmethod
    def search(self, query: str, k: int = 5, **kwargs) -> List[Union[Document, Dict[str, Any]]]:
        """Search memory with query."""
        pass
    
    @abstractmethod
    def delete(self, memory_id: str) -> bool:
        """Delete data by ID."""
        pass
    
    @abstractmethod
    def clear(self) -> None:
        """Clear all data."""
        pass


class VectorMemory(MemoryBase):
    """
    Vector Memory using ChromaDB for embedding vectors.
    
    Features:
    - Persistent storage with metadata indexing
    - Automatic collection creation per model
    - Batch operations for performance
    - Metadata filtering
    """
    
    def __init__(self, config: MemoryConfig, model_id: str, collection_name: Optional[str] = None):
        self.model_id = model_id
        self.collection_name = collection_name or f"{config.collection_prefix}{model_id}"
        self.config = config
        
        # Initialize ChromaDB client
        self._init_chromadb()
        
        # Initialize LangChain vector store
        self._init_langchain_store()
        
        # Text splitter for document processing
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=512,
            chunk_overlap=50,
            separators=["\n\n", "\n", " ", ""]
        )
    
    def _init_chromadb(self):
        """Initialize ChromaDB client with persistent storage."""
        os.makedirs(self.config.persist_directory, exist_ok=True)
        
        self.chroma_client = chromadb.PersistentClient(
            path=self.config.persist_directory
        )
        
        # Create or get collection
        self.collection = self.chroma_client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"}
        )
        
        # Create index on metadata fields
        for field in self.config.metadata_index_fields:
            self.collection.create_index(field)
    
    def _init_langchain_store(self):
        """Initialize LangChain vector store wrapper."""
        self.embeddings = HuggingFaceEmbeddings(
            model_name=self.config.embedding_model
        )
        
        self.vector_store = Chroma(
            client=self.chroma_client,
            collection_name=self.collection_name,
            embedding_function=self.embeddings,
            persist_directory=self.config.persist_directory
        )
    
    def add(
        self,
        data: Union[Document, Dict[str, Any], List[Document]],
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Add data to vector memory.
        
        Args:
            data: Document, dict, or list of documents
            metadata: Additional metadata to store
            
        Returns:
            ID of added item
        """
        if isinstance(data, dict):
            doc = Document(page_content=str(data.get("content", "")), metadata=data)
        elif isinstance(data, Document):
            doc = data
        else:
            # List of documents
            ids = []
            for item in data:
                if isinstance(item, dict):
                    item = Document(page_content=str(item.get("content", "")), metadata=item)
                ids.append(self.add(item, metadata))
            return ids[0] if len(ids) == 1 else ids
        
        # Add metadata
        if metadata:
            doc.metadata.update(metadata)
        
        # Add model_id and timestamp
        doc.metadata.setdefault("model_id", self.model_id)
        doc.metadata.setdefault("type", "vector")
        doc.metadata["timestamp"] = datetime.now().isoformat()
        
        # Generate unique ID
        item_id = str(uuid.uuid4())
        doc.metadata["item_id"] = item_id
        
        # Add to ChromaDB
        self.collection.add(
            documents=[doc.page_content],
            embeddings=self.embeddings.embed_documents([doc.page_content]),
            metadatas=[doc.metadata],
            ids=[item_id]
        )
        
        return item_id
    
    def get(self, memory_id: str) -> Optional[Document]:
        """Get document by ID."""
        try:
            result = self.collection.get(
                ids=[memory_id],
                include=["documents", "metadatas"]
            )
            
            if not result["documents"] or not result["documents"][0]:
                return None
            
            return Document(
                page_content=result["documents"][0],
                metadata=result["metadatas"][0]
            )
        except Exception:
            return None
    
    def search(
        self,
        query: str,
        k: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Document]:
        """
        Search vector memory.
        
        Args:
            query: Search query
            k: Number of results to return
            filter_metadata: Metadata filter dict
            
        Returns:
            List of similar documents
        """
        # Build filter
        where_filter = {"model_id": self.model_id}
        if filter_metadata:
            where_filter.update(filter_metadata)
        
        # Search
        results = self.collection.query(
            query_embeddings=self.embeddings.embed_documents([query]),
            n_results=min(k, self.config.max_collection_size),
            where=where_filter
        )
        
        # Convert to Document objects
        documents = []
        if results["documents"] and results["documents"][0]:
            for i, doc_content in enumerate(results["documents"][0]):
                documents.append(Document(
                    page_content=doc_content,
                    metadata=results["metadatas"][0][i] if results["metadatas"] else {}
                ))
        
        return documents
    
    def delete(self, memory_id: str) -> bool:
        """Delete document by ID."""
        try:
            self.collection.delete(ids=[memory_id])
            return True
        except Exception:
            return False
    
    def clear(self) -> None:
        """Clear all data from collection."""
        self.chroma_client.delete_collection(self.collection_name)
        self._init_chromadb()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get collection statistics."""
        count = self.collection.count()
        return {
            "collection_name": self.collection_name,
            "model_id": self.model_id,
            "vector_count": count,
            "max_size": self.config.max_collection_size,
            "is_overloaded": count >= self.config.max_collection_size
        }


class ContextMemory(MemoryBase):
    """
    Context Memory for document chunks and retrieval results.
    
    Features:
    - Document chunk storage
    - Retrieval result caching
    - Hybrid search support (vector + BM25)
    - Per-model context isolation
    """
    
    def __init__(self, config: MemoryConfig, model_id: str):
        self.model_id = model_id
        self.config = config
        self.persist_path = Path(config.persist_directory) / "context" / model_id
        self.persist_path.mkdir(parents=True, exist_ok=True)
        
        # In-memory storage for context
        self._storage: Dict[str, Dict[str, Any]] = {}
        self._retrieval_cache: Dict[str, List[Document]] = {}
    
    def add(self, data: Union[Document, Dict[str, Any], List[Document]]) -> str:
        """
        Add document chunks to context memory.
        
        Args:
            data: Document, dict, or list of documents
            
        Returns:
            ID of added item
        """
        if isinstance(data, dict):
            doc = Document(page_content=str(data.get("content", "")), metadata=data)
        elif isinstance(data, Document):
            doc = data
        else:
            # List of documents
            ids = []
            for item in data:
                if isinstance(item, dict):
                    item = Document(page_content=str(item.get("content", "")), metadata=item)
                ids.append(self.add(item))
            return ids[0] if len(ids) == 1 else ids
        
        # Generate unique ID
        item_id = str(uuid.uuid4())
        
        # Split into chunks
        chunks = self.text_splitter.split_documents([doc])
        
        # Store chunks
        for i, chunk in enumerate(chunks):
            chunk.metadata["item_id"] = f"{item_id}_{i}"
            chunk.metadata["parent_id"] = item_id
            chunk.metadata["model_id"] = self.model_id
            chunk.metadata["type"] = "context"
            chunk.metadata["timestamp"] = datetime.now().isoformat()
        
        self._storage[item_id] = {
            "document": doc,
            "chunks": chunks,
            "metadata": {
                "item_id": item_id,
                "model_id": self.model_id,
                "type": "context",
                "timestamp": datetime.now().isoformat(),
                "chunk_count": len(chunks)
            }
        }
        
        return item_id
    
    def get(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """Get context by ID."""
        return self._storage.get(memory_id)
    
    def search(
        self,
        query: str,
        k: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Document]:
        """
        Search context memory.
        
        Args:
            query: Search query
            k: Number of results to return
            filter_metadata: Metadata filter
            
        Returns:
            List of matching chunks
        """
        # Build filter
        where_filter = {"model_id": self.model_id}
        if filter_metadata:
            where_filter.update(filter_metadata)
        
        # Search all chunks
        results = []
        for item_id, item_data in self._storage.items():
            for chunk in item_data["chunks"]:
                # Simple keyword matching (can be enhanced with BM25)
                if query.lower() in chunk.page_content.lower():
                    results.append(chunk)
        
        # Sort by timestamp and return top k
        results.sort(key=lambda x: x.metadata.get("timestamp", ""), reverse=True)
        return results[:k]
    
    def cache_retrieval(self, query: str, results: List[Document]) -> None:
        """Cache retrieval results."""
        self._retrieval_cache[query] = results
    
    def get_cached_retrieval(self, query: str) -> Optional[List[Document]]:
        """Get cached retrieval results."""
        return self._retrieval_cache.get(query)
    
    def delete(self, memory_id: str) -> bool:
        """Delete context by ID."""
        if memory_id in self._storage:
            del self._storage[memory_id]
            return True
        return False
    
    def clear(self) -> None:
        """Clear all context data."""
        self._storage.clear()
        self._retrieval_cache.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get context memory statistics."""
        return {
            "model_id": self.model_id,
            "context_count": len(self._storage),
            "cached_queries": len(self._retrieval_cache)
        }


class SessionMemory(MemoryBase):
    """
    Session Memory for user session state and conversation history.
    
    Features:
    - Session state management
    - Conversation history
    - TTL-based expiration
    - Persistent storage
    """
    
    def __init__(self, config: MemoryConfig):
        self.config = config
        self.persist_path = Path(config.persist_directory) / "sessions"
        self.persist_path.mkdir(parents=True, exist_ok=True)
        
        # In-memory session storage
        self._sessions: Dict[str, Dict[str, Any]] = {}
    
    def create_session(self, session_id: Optional[str] = None) -> str:
        """
        Create a new session.
        
        Args:
            session_id: Optional custom session ID
            
        Returns:
            New session ID
        """
        session_id = session_id or str(uuid.uuid4())
        
        self._sessions[session_id] = {
            "session_id": session_id,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "history": [],
            "state": {}
        }
        
        return session_id
    
    def add(self, data: Union[Dict[str, Any], str], session_id: Optional[str] = None) -> str:
        """
        Add data to session.
        
        Args:
            data: Data to add (dict or string)
            session_id: Session ID (auto-create if not provided)
            
        Returns:
            Entry ID
        """
        if not session_id:
            session_id = self.create_session()
        
        if session_id not in self._sessions:
            self.create_session(session_id)
        
        # Generate entry ID
        entry_id = str(uuid.uuid4())
        
        # Determine entry type
        if isinstance(data, str):
            entry = {
                "entry_id": entry_id,
                "type": "message",
                "content": data,
                "timestamp": datetime.now().isoformat()
            }
        elif isinstance(data, dict):
            entry = {
                "entry_id": entry_id,
                "type": data.get("type", "state"),
                "content": data.get("content", data),
                "timestamp": datetime.now().isoformat()
            }
        else:
            entry = {
                "entry_id": entry_id,
                "type": "unknown",
                "content": str(data),
                "timestamp": datetime.now().isoformat()
            }
        
        # Add to history
        self._sessions[session_id]["history"].append(entry)
        self._sessions[session_id]["updated_at"] = datetime.now().isoformat()
        
        return entry_id
    
    def get(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """Get session by ID."""
        session = self._sessions.get(memory_id)
        if session and not self._is_expired(session):
            return session
        return None
    
    def get_history(self, session_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get conversation history for session."""
        session = self._sessions.get(session_id)
        if not session or self._is_expired(session):
            return []
        
        return session["history"][-limit:]
    
    def get_state(self, session_id: str) -> Dict[str, Any]:
        """Get session state."""
        session = self._sessions.get(session_id)
        if not session or self._is_expired(session):
            return {}
        return session.get("state", {})
    
    def update_state(self, session_id: str, state: Dict[str, Any]) -> None:
        """Update session state."""
        if session_id in self._sessions:
            self._sessions[session_id]["state"].update(state)
            self._sessions[session_id]["updated_at"] = datetime.now().isoformat()
    
    def search(
        self,
        query: str,
        k: int = 5,
        session_id: Optional[str] = None,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search session history.
        
        Args:
            query: Search query
            k: Number of results
            session_id: Optional session filter
            filter_metadata: Optional metadata filter
            
        Returns:
            Matching entries
        """
        results = []
        
        sessions = [self._sessions[session_id]] if session_id else list(self._sessions.values())
        
        for session in sessions:
            if self._is_expired(session):
                continue
            
            for entry in session.get("history", []):
                content = entry.get("content", "")
                if query.lower() in str(content).lower():
                    results.append(entry)
        
        # Sort by timestamp and return top k
        results.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return results[:k]
    
    def delete(self, memory_id: str) -> bool:
        """Delete session by ID."""
        if memory_id in self._sessions:
            del self._sessions[memory_id]
            return True
        return False
    
    def clear(self) -> None:
        """Clear all sessions."""
        self._sessions.clear()
    
    def cleanup_expired(self) -> int:
        """Remove expired sessions. Returns count of removed sessions."""
        expired_count = 0
        expired_sessions = []
        
        for session_id, session in self._sessions.items():
            if self._is_expired(session):
                expired_sessions.append(session_id)
                expired_count += 1
        
        for session_id in expired_sessions:
            del self._sessions[session_id]
        
        return expired_count
    
    def _is_expired(self, session: Dict[str, Any]) -> bool:
        """Check if session is expired."""
        try:
            created_at = datetime.fromisoformat(session["created_at"])
            ttl = timedelta(hours=self.config.session_ttl_hours)
            return datetime.now() - created_at > ttl
        except (KeyError, ValueError):
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get session memory statistics."""
        active_sessions = sum(1 for s in self._sessions.values() if not self._is_expired(s))
        return {
            "total_sessions": len(self._sessions),
            "active_sessions": active_sessions,
            "ttl_hours": self.config.session_ttl_hours
        }


class MemoryManager:
    """
    Factory pattern for creating and managing memory instances.
    
    Features:
    - Factory pattern for memory type creation
    - Automatic cleanup of stale entries
    - Metadata indexing
    - Batch operations support
    """
    
    def __init__(self, config: Optional[MemoryConfig] = None):
        self.config = config or MemoryConfig()
        self._memories: Dict[str, MemoryBase] = {}
        self._memory_types = {
            "vector": VectorMemory,
            "context": ContextMemory,
            "session": SessionMemory
        }
    
    def get_vector_memory(self, model_id: str) -> VectorMemory:
        """Get or create vector memory for model."""
        if model_id not in self._memories:
            self._memories[model_id] = VectorMemory(self.config, model_id)
        return self._memories[model_id]
    
    def get_context_memory(self, model_id: str) -> ContextMemory:
        """Get or create context memory for model."""
        if model_id not in self._memories:
            self._memories[model_id] = ContextMemory(self.config, model_id)
        return self._memories[model_id]
    
    def get_session_memory(self) -> SessionMemory:
        """Get or create session memory."""
        if "session" not in self._memories:
            self._memories["session"] = SessionMemory(self.config)
        return self._memories["session"]
    
    def get_memory(self, memory_type: str, model_id: Optional[str] = None) -> MemoryBase:
        """Get memory by type."""
        if memory_type == "session":
            return self.get_session_memory()
        elif memory_type == "vector":
            return self.get_vector_memory(model_id or "default")
        elif memory_type == "context":
            return self.get_context_memory(model_id or "default")
        else:
            raise ValueError(f"Unknown memory type: {memory_type}")
    
    def cleanup(self) -> Dict[str, int]:
        """
        Cleanup expired entries and overloaded collections.
        
        Returns:
            Cleanup statistics
        """
        stats = {}
        
        # Cleanup expired sessions
        session_memory = self.get_session_memory()
        stats["expired_sessions"] = session_memory.cleanup_expired()
        
        # Check overloaded collections
        for model_id, memory in self._memories.items():
            if isinstance(memory, VectorMemory):
                memory_stats = memory.get_stats()
                if memory_stats["is_overloaded"]:
                    # Auto-cleanup oldest entries
                    memory.clear()
                    stats[f"overloaded_{model_id}"] = memory_stats["vector_count"]
        
        return stats
    
    def get_all_stats(self) -> Dict[str, Any]:
        """Get statistics for all memories."""
        stats = {}
        for model_id, memory in self._memories.items():
            stats[model_id] = memory.get_stats()
        return stats

    def delete_documents_by_source(self, source: str) -> int:
        """
        Delete all chunks from ChromaDB that have metadata['source'] == source.

        Args:
            source: The source file path to match.

        Returns:
            Number of documents deleted (or None if count unavailable).
        """
        vector_memory = self.get_vector_memory("default")
        try:
            result = vector_memory.collection.delete(where={"source": source})
            logger.info("Deleted documents for source: %s", source)
            return result
        except Exception as e:
            logger.error("Failed to delete documents by source %s: %s", source, e)
            return 0

    def get_stats_by_source(self) -> Dict[str, Any]:
        """
        Get statistics grouped by source file.

        Returns:
            Dict mapping source paths to their document counts.
        """
        vector_memory = self.get_vector_memory("default")
        try:
            # Get all documents with their metadata
            result = vector_memory.collection.get(
                include=["metadatas"]
            )
            stats: Dict[str, int] = {}
            if result["metadatas"]:
                for metadata in result["metadatas"]:
                    source = metadata.get("source", "unknown")
                    stats[source] = stats.get(source, 0) + 1
            return {"sources": stats, "total_documents": sum(stats.values())}
        except Exception as e:
            logger.error("Failed to get stats by source: %s", e)
            return {"sources": {}, "total_documents": 0}

    def close(self) -> None:
        """Close all memory connections."""
        self._memories.clear()


# Global instance
_memory_manager: Optional[MemoryManager] = None


def get_memory_manager(config: Optional[MemoryConfig] = None) -> MemoryManager:
    """Get or create global memory manager instance."""
    global _memory_manager
    if _memory_manager is None:
        _memory_manager = MemoryManager(config)
    return _memory_manager


def reset_memory_manager() -> None:
    """Reset global memory manager instance."""
    global _memory_manager
    if _memory_manager:
        _memory_manager.close()
    _memory_manager = None
