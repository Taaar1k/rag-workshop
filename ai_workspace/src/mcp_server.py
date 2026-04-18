"""
FastMCP RAG Server - MCP protocol implementation with LangChain and ChromaDB
"""
import os
import asyncio
from typing import Optional
from pathlib import Path

from fastmcp import FastMCP
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from pydantic import BaseModel, Field

# MCP Server initialization
mcp = FastMCP("rag-mcp-server")

# Configuration
CHROMA_PERSIST_DIR = "./chroma_db"
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL_NAME", "nomic-ai/nomic-embed-text-v1.5")
LLM_ENDPOINT = os.getenv("LLM_ENDPOINT", "http://localhost:8080/v1/chat/completions")
LLM_MODEL = os.getenv("LLM_MODEL_NAME", "Llama-3-8B-Instruct")

# Global variables
vector_store: Optional[Chroma] = None
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=512,
    chunk_overlap=50,
    separators=["\n\n", "\n", " ", ""]
)


class DocumentManager:
    """Manages document loading and vector storage"""
    
    def __init__(self):
        self.documents = []
        self.vector_store = None
        
    def load_documents(self, file_path: str) -> list[str]:
        """Load documents from file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                self.documents.append(content)
                return [content]
        except Exception as e:
            raise ValueError(f"Error loading document: {e}")
    
    def create_vector_store(self) -> Chroma:
        """Create ChromaDB vector store from documents"""
        if not self.documents:
            raise ValueError("No documents loaded")
        
        # Split documents into chunks
        chunks = []
        for doc in self.documents:
            chunks.extend(text_splitter.split_text(doc))
        
        # Initialize embeddings
        embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
        
        # Create vector store
        self.vector_store = Chroma.from_texts(
            texts=chunks,
            embedding=embeddings,
            persist_directory=CHROMA_PERSIST_DIR
        )
        
        return self.vector_store
    
    def search(self, query: str, top_k: int = 5) -> list[str]:
        """Search for relevant documents"""
        if not self.vector_store:
            raise ValueError("Vector store not initialized")
        
        embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
        results = self.vector_store.similarity_search_with_score(
            query=query,
            k=top_k
        )
        
        return [doc.page_content for doc, score in results]


# Initialize document manager
doc_manager = DocumentManager()


@mcp.tool()
async def search(query: str, top_k: int = 5) -> str:
    """
    Search for relevant documents in the knowledge base.
    
    Args:
        query: Search query string
        top_k: Number of results to return (default: 5)
    
    Returns:
        Formatted string with search results
    """
    try:
        # Initialize vector store if not exists
        if not doc_manager.vector_store:
            doc_manager.create_vector_store()
        
        # Perform search
        results = doc_manager.search(query, top_k)
        
        # Format results
        formatted_results = []
        for i, result in enumerate(results, 1):
            formatted_results.append(f"Result {i}:\n{result}\n")
        
        return "\n---\n".join(formatted_results)
    
    except Exception as e:
        return f"Search error: {str(e)}"


@mcp.tool()
async def ask(question: str, context: str = "") -> str:
    """
    Generate an answer to a question using the LLM.
    
    Args:
        question: The question to answer
        context: Optional context to include in the prompt
    
    Returns:
        Generated answer from the LLM
    """
    try:
        # Prepare prompt
        if context:
            prompt = f"""
You are a helpful assistant. Answer the question using ONLY the provided context.
If the answer is not in the context, say "I don't know".

CONTEXT:
{context}

QUESTION:
{question}

ANSWER:
"""
        else:
            prompt = f"""
You are a helpful assistant. Answer the following question:

QUESTION:
{question}

ANSWER:
"""
        
        # Call LLM via HTTP
        import requests
        response = requests.post(
            LLM_ENDPOINT,
            json={
                "model": LLM_MODEL,
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 512,
                "temperature": 0.1
            },
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code != 200:
            return f"LLM error: {response.status_code} - {response.text}"
        
        result = response.json()
        answer = result['choices'][0]['message']['content'].strip()
        
        return answer
    
    except Exception as e:
        return f"Answer error: {str(e)}"


@mcp.tool()
async def add_document(file_path: str) -> str:
    """
    Add a document to the knowledge base.
    
    Args:
        file_path: Path to the document file
    
    Returns:
        Status message
    """
    try:
        doc_manager.load_documents(file_path)
        
        if doc_manager.vector_store:
            # Rebuild vector store with new document
            doc_manager.create_vector_store()
        
        return f"Document added successfully from {file_path}"
    
    except Exception as e:
        return f"Error adding document: {str(e)}"


@mcp.tool()
async def list_documents() -> str:
    """
    List all documents in the knowledge base.
    
    Returns:
        Formatted list of documents
    """
    try:
        if not doc_manager.documents:
            return "No documents loaded"
        
        formatted_list = []
        for i, doc in enumerate(doc_manager.documents, 1):
            formatted_list.append(f"Document {i}: {len(doc)} characters")
        
        return "\n".join(formatted_list)
    
    except Exception as e:
        return f"Error listing documents: {str(e)}"


@mcp.tool()
async def health_check() -> dict:
    """
    Check the health of the RAG system.
    
    Returns:
        Health status dictionary
    """
    try:
        health_status = {
            "status": "healthy",
            "vector_store_initialized": doc_manager.vector_store is not None,
            "documents_loaded": len(doc_manager.documents) > 0,
            "llm_endpoint": LLM_ENDPOINT,
            "embedding_model": EMBEDDING_MODEL
        }
        
        return health_status
    
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }


if __name__ == "__main__":
    # Run the MCP server
    mcp.run()
