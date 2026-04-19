"""
Unit tests for IncrementalIndexManager.

Tests cover:
- SHA256 file hashing
- State persistence (load/save)
- File extension filtering (case-insensitive)
- Index, re-index, and delete operations
- Initial scan
- handle_file_change for added/modified/deleted events
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, MagicMock as Mock

import pytest

# Ensure src is in path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.incremental_index_manager import IncrementalIndexManager
from core.memory_manager import MemoryManager, MemoryConfig


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def sample_text_file(temp_dir):
    """Create a sample .txt file."""
    filepath = os.path.join(temp_dir, "sample.txt")
    with open(filepath, "w") as f:
        f.write("This is a test document for RAG indexing.")
    return filepath


@pytest.fixture
def sample_md_file(temp_dir):
    """Create a sample .md file."""
    filepath = os.path.join(temp_dir, "sample.md")
    with open(filepath, "w") as f:
        f.write("# Test Document\n\nThis is a markdown file.")
    return filepath


@pytest.fixture
def sample_json_file(temp_dir):
    """Create a sample .json file."""
    filepath = os.path.join(temp_dir, "sample.json")
    with open(filepath, "w") as f:
        f.write('{"title": "Test", "content": "JSON content"}')
    return filepath


@pytest.fixture
def sample_csv_file(temp_dir):
    """Create a sample .csv file."""
    filepath = os.path.join(temp_dir, "sample.csv")
    with open(filepath, "w") as f:
        f.write("name,value\nitem1,100\nitem2,200")
    return filepath


@pytest.fixture
def sample_uppercase_txt(temp_dir):
    """Create a file with uppercase extension."""
    filepath = os.path.join(temp_dir, "sample.TXT")
    with open(filepath, "w") as f:
        f.write("Uppercase extension file.")
    return filepath


@pytest.fixture
def mock_vector_memory():
    """Create a mock VectorMemory."""
    mock = MagicMock()
    mock.collection = MagicMock()
    mock.collection.delete = MagicMock(return_value=1)
    mock.collection.get = MagicMock(return_value={
        "documents": ["test content"],
        "metadatas": [{"source": "test.txt", "model_id": "test"}],
        "ids": ["test-id"],
    })
    mock.collection.count = MagicMock(return_value=1)
    mock.collection.create_index = MagicMock()
    mock.get_stats = MagicMock(return_value={"vector_count": 0, "collection_name": "test", "model_id": "test", "max_size": 10000000, "is_overloaded": False})
    mock.add = MagicMock(return_value="test-item-id")
    mock.text_splitter = MagicMock()
    mock.text_splitter.split_documents = MagicMock(return_value=[
        MagicMock(page_content="test content", metadata={"source": "test.txt"})
    ])
    return mock


@pytest.fixture
def mock_memory_manager(mock_vector_memory):
    """Create a mock MemoryManager."""
    mock = MagicMock(spec=MemoryManager)
    mock.get_vector_memory = MagicMock(return_value=mock_vector_memory)
    return mock


@pytest.fixture
def index_manager(temp_dir, mock_memory_manager):
    """Create an IncrementalIndexManager instance."""
    state_file = os.path.join(temp_dir, "index_state.json")
    return IncrementalIndexManager(
        memory_manager=mock_memory_manager,
        state_file=state_file,
        model_id="test_scanner",
        chunk_size=512,
        chunk_overlap=50,
        allowed_extensions=[".txt", ".md", ".json", ".csv"],
    )


# ==================================================================== #
# Hashing tests
# ==================================================================== #

class TestComputeFileHash:
    def test_compute_hash_returns_64_char_hex(self, sample_text_file):
        hash_val = IncrementalIndexManager.compute_file_hash(sample_text_file)
        assert len(hash_val) == 64
        # Should be valid hex
        int(hash_val, 16)

    def test_same_file_same_hash(self, sample_text_file):
        h1 = IncrementalIndexManager.compute_file_hash(sample_text_file)
        h2 = IncrementalIndexManager.compute_file_hash(sample_text_file)
        assert h1 == h2

    def test_different_files_different_hash(self, sample_text_file, sample_md_file):
        h1 = IncrementalIndexManager.compute_file_hash(sample_text_file)
        h2 = IncrementalIndexManager.compute_file_hash(sample_md_file)
        assert h1 != h2

    def test_nonexistent_file_returns_empty(self, temp_dir):
        hash_val = IncrementalIndexManager.compute_file_hash(
            os.path.join(temp_dir, "nonexistent.txt")
        )
        assert hash_val == ""


# ==================================================================== #
# State persistence tests
# ==================================================================== #

class TestStatePersistence:
    def test_load_state_empty_file(self, index_manager, temp_dir):
        state = index_manager.load_state()
        assert state == {"files": {}, "last_scan": None}

    def test_load_state_existing_file(self, index_manager, temp_dir):
        state_file = index_manager.state_file
        test_state = {
            "files": {"/path/to/file.txt": "abc123"},
            "last_scan": "2024-01-01T00:00:00",
        }
        with open(state_file, "w") as f:
            json.dump(test_state, f)

        loaded = index_manager.load_state()
        assert loaded["files"]["/path/to/file.txt"] == "abc123"
        assert loaded["last_scan"] == "2024-01-01T00:00:00"

    def test_save_and_load_state(self, index_manager, temp_dir):
        state = {
            "files": {"/path/to/file.txt": "hash123"},
            "last_scan": "2024-06-01T12:00:00",
        }
        index_manager.save_state(state)
        loaded = index_manager.load_state()
        assert loaded["files"]["/path/to/file.txt"] == "hash123"
        assert loaded["last_scan"] == "2024-06-01T12:00:00"

    def test_load_corrupted_json(self, index_manager, temp_dir):
        state_file = index_manager.state_file
        with open(state_file, "w") as f:
            f.write("not valid json {{{")

        # Should return empty state on error
        loaded = index_manager.load_state()
        assert loaded == {"files": {}, "last_scan": None}


# ==================================================================== #
# Extension filtering tests
# ==================================================================== #

class TestExtensionFiltering:
    def test_allowed_extension_txt(self, index_manager, sample_text_file):
        assert index_manager._is_allowed_extension(
            sample_text_file, [".txt", ".md"]
        ) is True

    def test_allowed_extension_uppercase(self, sample_uppercase_txt):
        # Case-insensitive: .TXT should match .txt
        assert IncrementalIndexManager(
            MagicMock(), "/tmp/state.json",
            allowed_extensions=[".txt"]
        )._is_allowed_extension(sample_uppercase_txt, [".txt"]) is True

    def test_disallowed_extension(self, temp_dir):
        filepath = os.path.join(temp_dir, "file.py")
        with open(filepath, "w") as f:
            f.write("print('hello')")
        assert IncrementalIndexManager(
            MagicMock(), "/tmp/state.json",
            allowed_extensions=[".txt"]
        )._is_allowed_extension(filepath, [".txt"]) is False

    def test_case_insensitive_Md(self, temp_dir):
        filepath = os.path.join(temp_dir, "file.MD")
        with open(filepath, "w") as f:
            f.write("# Title")
        mgr = IncrementalIndexManager(
            MagicMock(), "/tmp/state.json",
            allowed_extensions=[".md"]
        )
        assert mgr._is_allowed_extension(filepath, [".md"]) is True


# ==================================================================== #
# Indexing tests
# ==================================================================== #

class TestIndexing:
    def test_index_file_calls_vector_memory_add(
        self, index_manager, sample_text_file, mock_vector_memory
    ):
        # Mock compute_file_hash to return a valid hash
        with patch.object(
            IncrementalIndexManager, "compute_file_hash", return_value="abc123"
        ):
            with patch.object(
                IncrementalIndexManager, "_load_document",
                return_value=[MagicMock(page_content="test", metadata={"source": sample_text_file})]
            ):
                count = index_manager.index_file(sample_text_file)
                # add() was called
                assert mock_vector_memory.add.called

    def test_index_nonexistent_file(self, index_manager, temp_dir):
        count = index_manager.index_file(os.path.join(temp_dir, "nonexistent.txt"))
        assert count == 0

    def test_index_disallowed_extension(self, index_manager, temp_dir):
        filepath = os.path.join(temp_dir, "file.py")
        with open(filepath, "w") as f:
            f.write("x = 1")
        count = index_manager.index_file(filepath)
        assert count == 0

    def test_reindex_file_deletes_then_indexes(
        self, index_manager, sample_text_file, mock_vector_memory
    ):
        with patch.object(
            IncrementalIndexManager, "compute_file_hash", return_value="newhash"
        ):
            with patch.object(
                IncrementalIndexManager, "_load_document",
                return_value=[MagicMock(page_content="updated", metadata={"source": sample_text_file})]
            ):
                index_manager.reindex_file(sample_text_file)
                # delete should have been called
                assert mock_vector_memory.collection.delete.called

    def test_delete_from_index_calls_collection_delete(
        self, index_manager, sample_text_file, mock_vector_memory
    ):
        index_manager.delete_from_index(sample_text_file)
        mock_vector_memory.collection.delete.assert_called_once_with(
            where={"source": sample_text_file}
        )


# ==================================================================== #
# handle_file_change tests
# ==================================================================== #

class TestHandleFileChange:
    def test_handle_added_new_file(
        self, index_manager, sample_text_file, mock_vector_memory, temp_dir
    ):
        state_file = index_manager.state_file
        # Ensure no prior state
        if os.path.exists(state_file):
            os.remove(state_file)

        with patch.object(
            IncrementalIndexManager, "compute_file_hash", return_value="hash1"
        ):
            with patch.object(
                IncrementalIndexManager, "index_file", return_value=1
            ) as mock_index:
                result = index_manager.handle_file_change(sample_text_file, "added")
                assert result == 1
                mock_index.assert_called_once()
                # State should be saved
                assert os.path.exists(state_file)

    def test_handle_added_existing_unmodified(
        self, index_manager, sample_text_file, temp_dir
    ):
        state_file = index_manager.state_file
        # Create state with existing file
        state = {
            "files": {sample_text_file: "samehash"},
            "last_scan": None,
        }
        with open(state_file, "w") as f:
            json.dump(state, f)

        with patch.object(
            IncrementalIndexManager, "compute_file_hash", return_value="samehash"
        ):
            result = index_manager.handle_file_change(sample_text_file, "added")
            assert result == 0

    def test_handle_modified_changed(
        self, index_manager, sample_text_file, mock_vector_memory, temp_dir
    ):
        state_file = index_manager.state_file
        state = {
            "files": {sample_text_file: "oldhash"},
            "last_scan": None,
        }
        with open(state_file, "w") as f:
            json.dump(state, f)

        with patch.object(
            IncrementalIndexManager, "compute_file_hash", return_value="newhash"
        ):
            with patch.object(
                IncrementalIndexManager, "reindex_file", return_value=2
            ) as mock_reindex:
                result = index_manager.handle_file_change(sample_text_file, "modified")
                assert result == 2
                mock_reindex.assert_called_once()

    def test_handle_deleted_existing(
        self, index_manager, sample_text_file, mock_vector_memory, temp_dir
    ):
        state_file = index_manager.state_file
        state = {
            "files": {sample_text_file: "hash123"},
            "last_scan": None,
        }
        with open(state_file, "w") as f:
            json.dump(state, f)

        result = index_manager.handle_file_change(sample_text_file, "deleted")
        assert result == 1
        # Verify file was removed from state
        loaded = index_manager.load_state()
        assert sample_text_file not in loaded["files"]

    def test_handle_deleted_nonexistent_in_state(
        self, index_manager, temp_dir
    ):
        result = index_manager.handle_file_change(
            os.path.join(temp_dir, "not_tracked.txt"), "deleted"
        )
        assert result == 0

    def test_handle_unknown_change_type(
        self, index_manager, sample_text_file
    ):
        with patch("core.incremental_index_manager.logger") as mock_logger:
            result = index_manager.handle_file_change(sample_text_file, "unknown_type")
            assert result == 0


# ==================================================================== #
# Initial scan tests
# ==================================================================== #

class TestInitialScan:
    def test_initial_scan_indexes_new_files(
        self, index_manager, temp_dir, mock_vector_memory
    ):
        # Create test files
        file1 = os.path.join(temp_dir, "doc1.txt")
        file2 = os.path.join(temp_dir, "doc2.md")
        with open(file1, "w") as f:
            f.write("Document 1")
        with open(file2, "w") as f:
            f.write("# Document 2")

        dirs = [temp_dir]
        with patch.object(
            IncrementalIndexManager, "compute_file_hash", side_effect=lambda f: "hash_" + os.path.basename(f)
        ):
            with patch.object(
                IncrementalIndexManager, "_load_document",
                return_value=[MagicMock(page_content="content", metadata={"source": f})]
            ):
                count = index_manager.initial_scan(dirs)
                # Both files should be indexed
                assert count == 2

    def test_initial_scan_skips_unallowed_extensions(
        self, index_manager, temp_dir, mock_vector_memory
    ):
        filepath = os.path.join(temp_dir, "script.py")
        with open(filepath, "w") as f:
            f.write("print('hello')")

        count = index_manager.initial_scan([temp_dir])
        assert count == 0

    def test_initial_scan_creates_state_file(
        self, index_manager, temp_dir, mock_vector_memory
    ):
        file1 = os.path.join(temp_dir, "doc.txt")
        with open(file1, "w") as f:
            f.write("Content")

        with patch.object(
            IncrementalIndexManager, "compute_file_hash", return_value="h1"
        ):
            with patch.object(
                IncrementalIndexManager, "index_file", return_value=1
            ):
                index_manager.initial_scan([temp_dir])

        assert os.path.exists(index_manager.state_file)
        state = index_manager.load_state()
        assert len(state["files"]) == 1

    def test_initial_scan_with_nonexistent_directory(
        self, index_manager, temp_dir, mock_vector_memory
    ):
        nonexistent = os.path.join(temp_dir, "does_not_exist")
        count = index_manager.initial_scan([nonexistent])
        assert count == 0


# ==================================================================== #
# Stats tests
# ==================================================================== #

class TestStats:
    def test_get_stats(self, index_manager, temp_dir):
        state_file = index_manager.state_file
        state = {"files": {"/path/file.txt": "hash1"}, "last_scan": "2024-01-01"}
        with open(state_file, "w") as f:
            json.dump(state, f)

        stats = index_manager.get_stats()
        assert stats["tracked_files"] == 1
        assert stats["state_file"] == str(state_file)
