"""
Incremental Index Manager for RAG System.

Handles SHA256-based file hashing, state persistence, and incremental
indexing of documents into ChromaDB via MemoryManager.

Features:
- SHA256 file hashing for change detection
- JSON-based state persistence
- Incremental indexing (add, update, delete)
- Initial full scan support
- Integration with existing MemoryManager / VectorMemory
"""

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain_community.document_loaders import (
    TextLoader,
    JSONLoader,
    CSVLoader,
)
try:
    from langchain_community.document_loaders import UnstructuredMarkdownLoader as MarkdownLoader
except ImportError:
    MarkdownLoader = None
from langchain_core.documents import Document

from .memory_manager import MemoryManager, MemoryConfig

logger = logging.getLogger(__name__)

# Supported loaders mapping (lowercase extensions)
SUPPORTED_LOADERS = {
    ".txt": TextLoader,
    ".md": MarkdownLoader,
    ".json": JSONLoader,
    ".csv": CSVLoader,
}


class IncrementalIndexManager:
    """
    Manages incremental indexing of files into ChromaDB.

    Tracks file state via SHA256 hashes stored in a JSON file.
    On each run, compares current file hashes against stored state
    and performs add / re-index / delete operations as needed.
    """

    def __init__(
        self,
        memory_manager: MemoryManager,
        state_file: str,
        model_id: str = "directory_scanner",
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        allowed_extensions: Optional[List[str]] = None,
    ):
        """
        Args:
            memory_manager: Existing MemoryManager instance.
            state_file: Path to JSON file for persisting index state.
            model_id: Model ID used for VectorMemory lookups.
            chunk_size: Document chunk size for text splitting.
            chunk_overlap: Overlap between chunks.
            allowed_extensions: List of allowed file extensions (with dot).
        """
        self.memory_manager = memory_manager
        self.state_file = Path(state_file)
        self.model_id = model_id
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.allowed_extensions = (
            [e.lower() for e in allowed_extensions]
            if allowed_extensions
            else list(SUPPORTED_LOADERS.keys())
        )

        # Ensure state file directory exists
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

        # Get vector memory for this model_id
        self.vector_memory = self.memory_manager.get_vector_memory(model_id)
        # Update text splitter with configured chunk settings
        self.vector_memory.text_splitter = self._create_text_splitter()

    def _create_text_splitter(self):
        """Create a RecursiveCharacterTextSplitter with configured settings."""
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        return RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=["\n\n", "\n", " ", ""],
        )

    # ------------------------------------------------------------------ #
    # Hashing
    # ------------------------------------------------------------------ #

    @staticmethod
    def compute_file_hash(filepath: str) -> str:
        """
        Compute SHA256 hash of a file.

        Args:
            filepath: Path to the file.

        Returns:
            Hex digest string of the SHA256 hash.
        """
        sha256 = hashlib.sha256()
        try:
            with open(filepath, "rb") as f:
                while True:
                    chunk = f.read(8192)
                    if not chunk:
                        break
                    sha256.update(chunk)
        except (OSError, IOError) as e:
            logger.error("Failed to hash file %s: %s", filepath, e)
            return ""
        return sha256.hexdigest()

    # ------------------------------------------------------------------ #
    # State persistence
    # ------------------------------------------------------------------ #

    def load_state(self) -> Dict[str, Any]:
        """
        Load index state from JSON file.

        Returns:
            Dict with structure: {"files": {filepath: hash, ...}, "last_scan": ISO timestamp}
        """
        if self.state_file.exists():
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    state = json.load(f)
                logger.info("Loaded index state from %s (%d files tracked)", self.state_file, len(state.get("files", {})))
                return state
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to load index state from %s: %s. Starting fresh.", self.state_file, e)
        return {"files": {}, "last_scan": None}

    def save_state(self, state: Dict[str, Any]) -> None:
        """
        Save index state to JSON file.

        Args:
            state: State dict with 'files' and 'last_scan' keys.
        """
        try:
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
            logger.debug("Saved index state to %s", self.state_file)
        except OSError as e:
            logger.error("Failed to save index state to %s: %s", self.state_file, e)

    # ------------------------------------------------------------------ #
    # File extension helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _is_allowed_extension(filepath: str, allowed_extensions: List[str]) -> bool:
        """
        Case-insensitive check if file extension is allowed.

        Args:
            filepath: Path to check.
            allowed_extensions: List of extensions like [".txt", ".md"].

        Returns:
            True if the file extension matches (case-insensitive).
        """
        ext = Path(filepath).suffix.lower()
        return ext in allowed_extensions

    # ------------------------------------------------------------------ #
    # Indexing operations
    # ------------------------------------------------------------------ #

    def _load_document(self, filepath: str) -> Optional[List[Document]]:
        """
        Load a document using the appropriate LangChain loader.

        Args:
            filepath: Path to the file.

        Returns:
            List of Document objects, or None on failure.
        """
        ext = Path(filepath).suffix.lower()
        loader_class = SUPPORTED_LOADERS.get(ext)
        if loader_class is None:
            logger.warning("No loader found for extension '%s' in %s", ext, filepath)
            return None

        try:
            if ext == ".json":
                # JSON loader needs a jq_schema; use default
                loader = loader_class(filepath, jq_schema=".")
            else:
                loader = loader_class(filepath)
            docs = loader.load()
            # Set source metadata
            for doc in docs:
                doc.metadata["source"] = str(filepath)
                doc.metadata["model_id"] = self.model_id
                doc.metadata["type"] = "vector"
            return docs
        except Exception as e:
            logger.error("Failed to load document %s: %s", filepath, e)
            return None

    def index_file(self, filepath: str) -> int:
        """
        Index a new file into ChromaDB.

        Args:
            filepath: Path to the file to index.

        Returns:
            Number of chunks added, or 0 on failure.
        """
        if not os.path.isfile(filepath):
            logger.warning("File not found: %s", filepath)
            return 0

        if not self._is_allowed_extension(filepath, self.allowed_extensions):
            logger.info("Skipping disallowed extension: %s", filepath)
            return 0

        logger.info("Indexing new file: %s", filepath)
        docs = self._load_document(filepath)
        if not docs:
            return 0

        try:
            # Add documents to vector memory (handles chunking internally)
            for doc in docs:
                self.vector_memory.add(doc)
            count = len(docs)
            logger.info("Indexed %d chunk(s) from %s", count, filepath)
            return count
        except Exception as e:
            logger.error("Failed to index file %s: %s", filepath, e)
            return 0

    def reindex_file(self, filepath: str) -> int:
        """
        Re-index an existing file: delete old chunks and add new ones.

        Args:
            filepath: Path to the file to re-index.

        Returns:
            Number of new chunks added, or 0 on failure.
        """
        logger.info("Re-indexing file: %s", filepath)
        # Delete old chunks for this source
        self.delete_from_index(filepath)
        # Index the updated file
        return self.index_file(filepath)

    def delete_from_index(self, filepath: str) -> int:
        """
        Delete all chunks from ChromaDB that have `source == filepath`.

        Note: ChromaDB's delete() by metadata requires iterating because
        ChromaDB does not support delete-by-where directly in all versions.
        This implementation uses the collection's delete with a where filter.

        Args:
            filepath: Source file path to delete.

        Returns:
            Number of chunks deleted.
        """
        try:
            # Use ChromaDB's delete with where filter
            result = self.vector_memory.collection.delete(where={"source": filepath})
            logger.info("Deleted chunks for source: %s", filepath)
            return result  # May return None or count depending on ChromaDB version
        except Exception as e:
            logger.error("Failed to delete from index for %s: %s", filepath, e)
            return 0

    # ------------------------------------------------------------------ #
    # Initial scan
    # ------------------------------------------------------------------ #

    def _collect_files(self, directories: List[str]) -> List[str]:
        """
        Collect all eligible files from the given directories.

        Args:
            directories: List of directory paths to scan.

        Returns:
            List of absolute file paths.
        """
        files = []
        for dir_path in directories:
            p = Path(dir_path)
            if not p.exists():
                logger.warning("Directory does not exist, skipping: %s", dir_path)
                continue
            if not p.is_dir():
                logger.warning("Path is not a directory, skipping: %s", dir_path)
                continue

            if self.vector_memory.text_splitter:
                recursive = True  # Always recursive for directory scanning
            else:
                recursive = True

            if recursive:
                candidate_files = list(p.rglob("*"))
            else:
                candidate_files = list(p.glob("*"))

            for f in candidate_files:
                if f.is_file() and self._is_allowed_extension(str(f), self.allowed_extensions):
                    files.append(str(f))

        logger.info("Collected %d eligible files from %d directories", len(files), len(directories))
        return files

    def initial_scan(self, directories: List[str]) -> int:
        """
        Perform a full initial scan of all watched directories.

        Compares current files against stored state and indexes any
        new or modified files.

        Args:
            directories: List of directory paths to scan.

        Returns:
            Total number of files indexed.
        """
        logger.info("Starting initial scan of directories: %s", directories)
        state = self.load_state()
        current_files = state.get("files", {})
        total_indexed = 0

        eligible_files = self._collect_files(directories)

        for filepath in eligible_files:
            current_hash = self.compute_file_hash(filepath)
            if not current_hash:
                continue

            if filepath not in current_files:
                # New file
                chunks = self.index_file(filepath)
                if chunks > 0:
                    total_indexed += 1
                    current_files[filepath] = current_hash
            else:
                # Check if modified
                if current_files[filepath] != current_hash:
                    chunks = self.reindex_file(filepath)
                    if chunks > 0:
                        total_indexed += 1
                        current_files[filepath] = current_hash

        # Mark files that no longer exist for deletion
        files_to_delete = []
        for filepath in current_files:
            if not os.path.isfile(filepath):
                files_to_delete.append(filepath)

        for filepath in files_to_delete:
            logger.info("File no longer exists, removing from index: %s", filepath)
            self.delete_from_index(filepath)
            del current_files[filepath]

        # Update state
        state["files"] = current_files
        from datetime import datetime
        state["last_scan"] = datetime.now().isoformat()
        self.save_state(state)

        logger.info("Initial scan complete. Indexed %d file(s). Total tracked: %d", total_indexed, len(current_files))
        return total_indexed

    # ------------------------------------------------------------------ #
    # Incremental update (called by DirectoryScannerWorker on events)
    # ------------------------------------------------------------------ #

    def handle_file_change(self, filepath: str, change_type: str) -> int:
        """
        Handle a file change event (added, modified, deleted).

        Args:
            filepath: Path to the changed file.
            change_type: One of 'added', 'modified', 'deleted'.

        Returns:
            Number of chunks affected, or 0.
        """
        state = self.load_state()
        current_files = state.get("files", {})

        if change_type == "added":
            if not os.path.isfile(filepath):
                logger.warning("Added event for non-existent file: %s", filepath)
                return 0
            current_hash = self.compute_file_hash(filepath)
            if not current_hash:
                return 0
            if filepath in current_files and current_files[filepath] == current_hash:
                logger.info("File %s unchanged, skipping", filepath)
                return 0
            chunks = self.index_file(filepath)
            if chunks > 0:
                current_files[filepath] = current_hash
                state["files"] = current_files
                self.save_state(state)
            return chunks

        elif change_type == "modified":
            if not os.path.isfile(filepath):
                # File was deleted after modification event
                return self.handle_file_change(filepath, "deleted")
            current_hash = self.compute_file_hash(filepath)
            if not current_hash:
                return 0
            if filepath not in current_files:
                # New file (missed the added event)
                return self.handle_file_change(filepath, "added")
            if current_files[filepath] == current_hash:
                logger.info("File %s content unchanged, skipping re-index", filepath)
                return 0
            chunks = self.reindex_file(filepath)
            if chunks >= 0:
                current_files[filepath] = current_hash
                state["files"] = current_files
                self.save_state(state)
            return chunks

        elif change_type == "deleted":
            if filepath in current_files:
                self.delete_from_index(filepath)
                del current_files[filepath]
                state["files"] = current_files
                self.save_state(state)
                return 1
            return 0

        else:
            logger.warning("Unknown change type: %s", change_type)
            return 0

    # ------------------------------------------------------------------ #
    # Stats
    # ------------------------------------------------------------------ #

    def get_stats(self) -> Dict[str, Any]:
        """
        Get indexing statistics.

        Returns:
            Dict with indexing stats.
        """
        state = self.load_state()
        vector_stats = self.vector_memory.get_stats()
        return {
            "model_id": self.model_id,
            "tracked_files": len(state.get("files", {})),
            "vector_count": vector_stats.get("vector_count", 0),
            "last_scan": state.get("last_scan"),
            "state_file": str(self.state_file),
        }
