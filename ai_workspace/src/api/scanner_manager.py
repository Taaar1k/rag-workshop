"""
Scanner Manager for RAG API Server.

Manages the DirectoryScannerWorker lifecycle and provides
API endpoints for scanner control.
"""

import asyncio
import logging
from typing import Optional, Dict, Any
from pathlib import Path
from fastapi import APIRouter

from ..core.directory_scanner import DirectoryScannerWorker
from ..core.incremental_index_manager import IncrementalIndexManager
from ..core.memory_manager import MemoryManager, MemoryConfig

logger = logging.getLogger(__name__)

router = APIRouter()

# Global scanner instances
_scanner: Optional[DirectoryScannerWorker] = None
_index_manager: Optional[IncrementalIndexManager] = None


async def initialize_scanner(config: Dict[str, Any]) -> None:
    """Initialize the directory scanner from config."""
    global _scanner, _index_manager

    if not config.get("enabled", False):
        logger.info("Directory scanning disabled in config.")
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

    # Initialize MemoryManager
    mem_config = MemoryConfig()
    mem_manager = MemoryManager(mem_config)

    # Initialize IncrementalIndexManager
    _index_manager = IncrementalIndexManager(
        memory_manager=mem_manager,
        state_file=state_file,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        allowed_extensions=allowed_exts,
    )

    # Initialize DirectoryScannerWorker
    _scanner = DirectoryScannerWorker(
        index_manager=_index_manager,
        watched_directories=watched_dirs,
        debounce_ms=debounce_ms,
        poll_interval_s=poll_interval_s,
        enabled=True,
    )

    logger.info("Directory scanner initialized with %d watched directories", len(watched_dirs))


async def start_scanner() -> None:
    """Start the directory scanner (called on FastAPI startup)."""
    global _scanner
    if _scanner and not _scanner.is_running():
        await _scanner.start()
        logger.info("Directory scanner started.")


async def stop_scanner() -> None:
    """Stop the directory scanner (called on FastAPI shutdown)."""
    global _scanner
    if _scanner and _scanner.is_running():
        await _scanner.stop()
        logger.info("Directory scanner stopped.")


def get_scanner_status() -> Dict[str, Any]:
    """Get current scanner status."""
    global _scanner
    if _scanner is None:
        return {"enabled": False, "running": False, "message": "Scanner not initialized"}

    return _scanner.get_status()


@router.get("/status")
async def scanner_status():
    """Get current directory scanner status."""
    return get_scanner_status()


@router.post("/start")
async def scanner_start():
    """Start the directory scanner."""
    global _scanner
    if _scanner is None:
        return {"error": "Scanner not initialized"}
    await _scanner.start()
    return {"message": "Scanner started", "status": get_scanner_status()}


@router.post("/stop")
async def scanner_stop():
    """Stop the directory scanner."""
    global _scanner
    if _scanner is None:
        return {"error": "Scanner not initialized"}
    await _scanner.stop()
    return {"message": "Scanner stopped", "status": get_scanner_status()}
