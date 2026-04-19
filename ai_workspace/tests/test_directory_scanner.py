"""
Unit tests for DirectoryScannerWorker.

Tests cover:
- Start/stop lifecycle
- enabled: false disables scanner
- Change resolution (added, modified, deleted)
- _process_changes with debouncing
- Status reporting
- Mocked watchfiles.awatch
"""

import asyncio
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from watchfiles import Change

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.directory_scanner import DirectoryScannerWorker
from core.incremental_index_manager import IncrementalIndexManager


@pytest.fixture
def temp_dir():
    """Create a temporary directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def mock_index_manager(temp_dir):
    """Create a mock IncrementalIndexManager."""
    mock = MagicMock(spec=IncrementalIndexManager)
    mock.allowed_extensions = [".txt", ".md", ".json", ".csv"]
    mock.initial_scan = MagicMock(return_value=5)
    mock.handle_file_change = MagicMock(return_value=1)
    mock.get_stats = MagicMock(return_value={
        "tracked_files": 10,
        "vector_count": 50,
        "last_scan": "2024-01-01T00:00:00",
        "state_file": "/tmp/state.json",
    })
    return mock


@pytest.fixture
def scanner(mock_index_manager, temp_dir):
    """Create a DirectoryScannerWorker instance."""
    watched_dirs = [
        {"path": temp_dir, "recursive": True},
    ]
    return DirectoryScannerWorker(
        index_manager=mock_index_manager,
        watched_directories=watched_dirs,
        debounce_ms=500,
        poll_interval_s=1,
        enabled=True,
    )


# ==================================================================== #
# Lifecycle tests
# ==================================================================== #

class TestLifecycle:
    @pytest.mark.asyncio
    async def test_start_disabled_scanner(self, mock_index_manager, temp_dir):
        watched_dirs = [{"path": temp_dir, "recursive": True}]
        disabled_scanner = DirectoryScannerWorker(
            index_manager=mock_index_manager,
            watched_directories=watched_dirs,
            enabled=False,
        )
        # Should not raise, just log and return
        await disabled_scanner.start()
        assert disabled_scanner.is_running() is False
        # initial_scan should NOT be called
        mock_index_manager.initial_scan.assert_not_called()

    @pytest.mark.asyncio
    async def test_start_enabled_scanner(self, scanner, mock_index_manager):
        """Starting an enabled scanner should call initial_scan."""
        with patch("core.directory_scanner.awatch") as mock_awatch:
            mock_awatch.return_value = AsyncMock(__aiter__=MagicMock(return_value=iter([])))
            await scanner.start()
            # initial_scan should be called
            mock_index_manager.initial_scan.assert_called_once()
            assert scanner.is_running() is True

    @pytest.mark.asyncio
    async def test_stop_running_scanner(self, scanner):
        scanner._running = True
        scanner._watch_task = AsyncMock()
        scanner._watch_task.cancel = MagicMock()
        scanner._watch_task.done = MagicMock(return_value=True)
        scanner._watch_task.__await__ = MagicMock(return_value=iter([]))

        await scanner.stop()
        assert scanner.is_running() is False

    async def test_stop_non_running_scanner(self, scanner):
        result = await scanner.stop()
        # Should not raise
        assert scanner.is_running() is False


# ==================================================================== #
# Change resolution tests
# ==================================================================== #

class TestChangeResolution:
    def test_resolve_deleted_priority(self):
        changes = [
            (Change.modified, "/path/file.txt"),
            (Change.deleted, "/path/file.txt"),
            (Change.added, "/path/file.txt"),
        ]
        result = DirectoryScannerWorker._resolve_change_type(changes)
        assert result == "deleted"

    def test_resolve_modified_priority(self):
        changes = [
            (Change.modified, "/path/file.txt"),
            (Change.added, "/path/file.txt"),
        ]
        result = DirectoryScannerWorker._resolve_change_type(changes)
        assert result == "modified"

    def test_resolve_added_only(self):
        changes = [
            (Change.added, "/path/file.txt"),
        ]
        result = DirectoryScannerWorker._resolve_change_type(changes)
        assert result == "added"

    def test_resolve_single_modified(self):
        changes = [
            (Change.modified, "/path/file.txt"),
        ]
        result = DirectoryScannerWorker._resolve_change_type(changes)
        assert result == "modified"


# ==================================================================== #
# Filter tests
# ==================================================================== #

class TestWatchFilter:
    def test_filter_allows_txt(self, scanner, mock_index_manager):
        mock_index_manager.allowed_extensions = [".txt"]
        changes = {
            (Change.added, "/path/file.txt"),
            (Change.added, "/path/file.py"),
        }
        filt = scanner._get_watch_filter()
        filtered = filt(changes)
        assert len(filtered) == 1
        assert (Change.added, "/path/file.txt") in filtered

    def test_filter_allows_multiple_extensions(self, scanner, mock_index_manager):
        mock_index_manager.allowed_extensions = [".txt", ".md"]
        changes = {
            (Change.added, "/path/file.txt"),
            (Change.added, "/path/file.md"),
            (Change.added, "/path/file.py"),
        }
        filt = scanner._get_watch_filter()
        filtered = filt(changes)
        assert len(filtered) == 2

    def test_filter_case_insensitive(self, scanner, mock_index_manager):
        mock_index_manager.allowed_extensions = [".TXT"]
        changes = {
            (Change.added, "/path/file.TXT"),
            (Change.added, "/path/file.txt"),
        }
        filt = scanner._get_watch_filter()
        filtered = filt(changes)
        # .TXT matches .TXT (exact), .txt does not match .TXT
        # But the filter uses lowercase comparison
        assert len(filtered) == 2


# ==================================================================== #
# Process changes tests
# ==================================================================== #

class TestProcessChanges:
    @pytest.mark.asyncio
    async def test_process_changes_calls_handle_file_change(
        self, scanner, mock_index_manager, temp_dir
    ):
        mock_index_manager.handle_file_change = AsyncMock(return_value=1)
        changes = {
            (Change.added, os.path.join(temp_dir, "file.txt")),
            (Change.modified, os.path.join(temp_dir, "file2.md")),
        }
        await scanner._process_changes(changes)
        assert mock_index_manager.handle_file_change.call_count == 2

    @pytest.mark.asyncio
    async def test_process_changes_groups_same_file(
        self, scanner, mock_index_manager, temp_dir
    ):
        """Multiple changes for the same file should be resolved to one."""
        mock_index_manager.handle_file_change = AsyncMock(return_value=1)
        filepath = os.path.join(temp_dir, "file.txt")
        changes = {
            (Change.added, filepath),
            (Change.modified, filepath),
            (Change.deleted, filepath),
        }
        await scanner._process_changes(changes)
        # Should be called once with 'deleted' (highest priority)
        mock_index_manager.handle_file_change.assert_called_once_with(
            filepath, "deleted"
        )

    @pytest.mark.asyncio
    async def test_process_changes_handles_error_gracefully(
        self, scanner, mock_index_manager, temp_dir
    ):
        """Errors should be logged, not raised."""
        mock_index_manager.handle_file_change = MagicMock(
            side_effect=Exception("Indexing failed")
        )
        changes = {
            (Change.added, os.path.join(temp_dir, "file.txt")),
        }
        # Should not raise
        await scanner._process_changes(changes)


# ==================================================================== #
# Status tests
# ==================================================================== #

class TestStatus:
    def test_is_running(self, scanner):
        assert scanner.is_running() is False
        scanner._running = True
        assert scanner.is_running() is True

    def test_get_status(self, scanner):
        scanner._running = True
        status = scanner.get_status()
        assert status["scanner_running"] is True
        assert status["scanner_enabled"] is True
        assert status["watched_directories"] == 1
        assert status["debounce_ms"] == 500
        assert status["tracked_files"] == 10
