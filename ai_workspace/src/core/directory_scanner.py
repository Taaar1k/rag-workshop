"""
Directory Scanner Worker for RAG System.

Monitors directories for file changes using watchfiles and triggers
incremental indexing via IncrementalIndexManager.

Features:
- Async file watching via watchfiles.awatch()
- Event filtering (Change.added, Change.modified, Change.deleted)
- Debouncing to avoid duplicate processing
- Non-blocking asyncio daemon task
- Graceful start/stop lifecycle
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from watchfiles import Change, awatch

from .incremental_index_manager import IncrementalIndexManager

logger = logging.getLogger(__name__)


class DirectoryScannerWorker:
    """
    Background worker that watches directories for file changes
    and triggers incremental indexing.
    """

    def __init__(
        self,
        index_manager: IncrementalIndexManager,
        watched_directories: List[Dict[str, Any]],
        debounce_ms: int = 500,
        poll_interval_s: int = 60,
        enabled: bool = True,
    ):
        """
        Args:
            index_manager: IncrementalIndexManager instance for indexing operations.
            watched_directories: List of dicts with 'path' and 'recursive' keys.
            debounce_ms: Debounce time in milliseconds before processing changes.
            poll_interval_s: Polling interval in seconds when no changes detected.
            enabled: Whether scanning is enabled.
        """
        self.index_manager = index_manager
        self.watched_directories = watched_directories
        self.debounce_ms = debounce_ms
        self.poll_interval_s = poll_interval_s
        self.enabled = enabled

        self._watch_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        self._running = False

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    async def start(self) -> None:
        """
        Start the directory scanner as a background asyncio task.

        If enabled is False, logs and returns without starting.
        Performs an initial scan before starting the watcher.
        """
        if not self.enabled:
            logger.info("Directory scanning is disabled in configuration. Skipping startup.")
            return

        if self._running:
            logger.warning("Directory scanner is already running.")
            return

        logger.info("Starting DirectoryScannerWorker with %d watched directories", len(self.watched_directories))

        # Extract pure paths for watchfiles
        paths_to_watch = []
        for dir_config in self.watched_directories:
            dir_path = dir_config.get("path", "")
            if dir_path:
                paths_to_watch.append(dir_path)

        # Create default directories if they don't exist
        for dir_path in paths_to_watch:
            p = Path(dir_path)
            if not p.exists():
                p.mkdir(parents=True, exist_ok=True)
                logger.info("Created watched directory: %s", dir_path)

        # Perform initial scan
        logger.info("Performing initial scan...")
        try:
            initial_count = self.index_manager.initial_scan(paths_to_watch)
            logger.info("Initial scan complete: %d files indexed", initial_count)
        except Exception as e:
            logger.error("Initial scan failed: %s", e)

        # Start async watcher task
        self._stop_event.clear()
        self._watch_task = asyncio.create_task(self._watch_loop(paths_to_watch), name="directory_scanner_watch")
        self._running = True
        logger.info("DirectoryScannerWorker started successfully")

    async def stop(self) -> None:
        """
        Stop the directory scanner gracefully.
        """
        if not self._running:
            logger.warning("Directory scanner is not running.")
            return

        logger.info("Stopping DirectoryScannerWorker...")
        self._stop_event.set()

        if self._watch_task:
            try:
                # Give the task time to finish
                await asyncio.wait_for(self._watch_task, timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("Directory scanner task did not finish in time, cancelling...")
                self._watch_task.cancel()
                try:
                    await self._watch_task
                except asyncio.CancelledError:
                    pass
            except Exception as e:
                logger.error("Error stopping directory scanner task: %s", e)

        self._running = False
        self._watch_task = None
        logger.info("DirectoryScannerWorker stopped")

    # ------------------------------------------------------------------ #
    # Watch loop
    # ------------------------------------------------------------------ #

    async def _watch_loop(self, paths: List[str]) -> None:
        """
        Main async loop that watches for file changes.

        Uses watchfiles.awatch() with debounce and change filtering.
        """
        logger.info("File watch loop started for paths: %s", paths)

        # Build watch filters
        watch_filters = []
        for dir_config in self.watched_directories:
            path = dir_config.get("path", "")
            recursive = dir_config.get("recursive", True)
            watch_filters.append((path, recursive))

        while not self._stop_event.is_set():
            try:
                # awatch yields sets of FileChange tuples on each debounce period
                changes = await asyncio.wait_for(
                    self._get_changes(watch_filters),
                    timeout=self.poll_interval_s
                )

                if changes:
                    await self._process_changes(changes)

            except asyncio.TimeoutError:
                # No changes during poll interval, continue watching
                continue
            except asyncio.CancelledError:
                logger.info("Watch loop cancelled")
                break
            except Exception as e:
                logger.error("Error in watch loop: %s", e, exc_info=True)
                # Wait before retrying
                await asyncio.sleep(self.poll_interval_s)

        logger.info("File watch loop ended")

    async def _get_changes(self, watch_filters: List[tuple]):
        """
        Wrapper around awatch that respects the stop event.

        Args:
            watch_filters: List of (path, recursive) tuples.

        Returns:
            Set of FileChange tuples.
        """
        # Build arguments for awatch
        args = list(watch_filters[0][0]) if watch_filters else []
        # awatch expects paths as positional args
        awatch_args = tuple(cfg[0] for cfg in watch_filters)
        awatch_kwargs = {
            "watch_filter": self._get_watch_filter(),
            "raise_interrupt": False,
            "recursive": True,
        }

        # Use awatch with a single iteration
        async for changes in awatch(*awatch_args, **awatch_kwargs):
            return changes
        return set()

    def _get_watch_filter(self):
        """
        Create a watch filter that only allows allowed extensions.

        Returns:
            Callable that filters FileChange tuples.
        """
        # Store lowercase versions for case-insensitive comparison
        allowed_exts = set(ext.lower() for ext in self.index_manager.allowed_extensions)

        def filter_changes(changes: set) -> set:
            """Filter changes to only include allowed extensions."""
            filtered = set()
            for change in changes:
                # change is a tuple: (Change enum, path string)
                change_type, filepath = change
                ext = Path(filepath).suffix.lower()
                if ext in allowed_exts:
                    filtered.add(change)
            return filtered

        return filter_changes

    # ------------------------------------------------------------------ #
    # Change processing
    # ------------------------------------------------------------------ #

    async def _process_changes(self, changes: set) -> None:
        """
        Process a batch of file changes with debouncing.

        Groups changes by file path and processes each file once.

        Args:
            changes: Set of FileChange tuples from watchfiles.
        """
        # Group by filepath to handle debouncing
        file_changes: Dict[str, List[tuple]] = {}
        for change_type, filepath in changes:
            if filepath not in file_changes:
                file_changes[filepath] = []
            file_changes[filepath].append((change_type, filepath))

        logger.info("Processing %d unique file change(s)", len(file_changes))

        for filepath, change_list in file_changes.items():
            try:
                # Use the most significant change type
                # Priority: deleted > modified > added
                final_change = self._resolve_change_type(change_list)
                chunks = await self._handle_change_async(filepath, final_change)
                if chunks > 0:
                    logger.info("Processed %s for %s (%d chunks)", final_change, filepath, chunks)
                else:
                    logger.info("Processed %s for %s", final_change, filepath)
            except Exception as e:
                # Error handling: log but don't crash the watcher
                logger.error("Failed to process change for %s: %s", filepath, e, exc_info=True)

    @staticmethod
    def _resolve_change_type(change_list: List[tuple]) -> str:
        """
        Resolve multiple change types for the same file to a single type.

        Priority: deleted > modified > added

        Args:
            change_list: List of (Change, filepath) tuples.

        Returns:
            String: 'added', 'modified', or 'deleted'.
        """
        change_types = {ct for ct, _ in change_list}

        if Change.deleted in change_types:
            return "deleted"
        if Change.modified in change_types:
            return "modified"
        if Change.added in change_types:
            return "added"

        # Fallback: return 'modified' for any other change
        return "modified"

    async def _handle_change_async(self, filepath: str, change_type: str) -> int:
        """
        Handle a file change asynchronously.

        Args:
            filepath: Path to the changed file.
            change_type: One of 'added', 'modified', 'deleted'.

        Returns:
            Number of chunks affected.
        """
        # Run in executor to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self.index_manager.handle_file_change,
            filepath,
            change_type
        )

    # ------------------------------------------------------------------ #
    # Status
    # ------------------------------------------------------------------ #

    def is_running(self) -> bool:
        """Check if the scanner is currently running."""
        return self._running

    def get_status(self) -> Dict[str, Any]:
        """
        Get the current status of the scanner.

        Returns:
            Dict with status information.
        """
        index_stats = self.index_manager.get_stats()
        return {
            "scanner_running": self._running,
            "scanner_enabled": self.enabled,
            "watched_directories": len(self.watched_directories),
            "debounce_ms": self.debounce_ms,
            **index_stats,
        }
