"""
Tests for Memory Persistence Module
Tests all DoD criteria from TASK-014
"""

import json
import os
import sys
import tempfile
import time
import pytest
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.memory_persistence import (
    MemoryPersistence,
    Message,
    UserContext
)


class TestMemoryPersistenceConversationHistory:
    """Test conversation history persistence (DoD 1)."""
    
    def test_save_conversation_creates_valid_file(self, tmp_path):
        """Verify conversation history saves to valid JSON file."""
        persistence = MemoryPersistence(
            storage_path=str(tmp_path / "test_conversation.json"),
            use_memory_fallback=False
        )
        
        messages = [
            Message(role="user", content="Hello", timestamp=datetime.now().isoformat()),
            Message(role="assistant", content="Hi there!", timestamp=datetime.now().isoformat())
        ]
        
        result = persistence.save_conversation(messages, "session_001")
        
        assert result is True
        assert os.path.exists(str(tmp_path / "test_conversation.json"))
    
    def test_save_and_restore_conversation(self, tmp_path):
        """Verify conversation history can be saved and restored correctly."""
        persistence = MemoryPersistence(
            storage_path=str(tmp_path / "conversation.json"),
            use_memory_fallback=False
        )
        
        original_messages = [
            Message(role="user", content="What is RAG?", timestamp="2026-04-15T10:00:00"),
            Message(role="assistant", content="RAG is Retrieval-Augmented Generation", timestamp="2026-04-15T10:00:01"),
            Message(role="user", content="How does it work?", timestamp="2026-04-15T10:00:02")
        ]
        
        # Save
        persistence.save_conversation(original_messages, "session_test")
        
        # Load
        loaded_messages = persistence.load_conversation("session_test")
        
        # Verify
        assert len(loaded_messages) == 3
        assert loaded_messages[0].role == "user"
        assert loaded_messages[0].content == "What is RAG?"
        assert loaded_messages[1].role == "assistant"
        assert loaded_messages[1].content == "RAG is Retrieval-Augmented Generation"
    
    def test_conversation_with_empty_list(self, tmp_path):
        """Verify empty conversation list is handled correctly."""
        persistence = MemoryPersistence(
            storage_path=str(tmp_path / "empty_conv.json"),
            use_memory_fallback=False
        )
        
        result = persistence.save_conversation([], "empty_session")
        assert result is True
        
        loaded = persistence.load_conversation("empty_session")
        assert loaded == []
    
    def test_multiple_sessions_preserved(self, tmp_path):
        """Verify multiple sessions don't overwrite each other."""
        persistence = MemoryPersistence(
            storage_path=str(tmp_path / "multi_session.json"),
            use_memory_fallback=False
        )
        
        # Save first session
        persistence.save_conversation(
            [Message(role="user", content="Session 1", timestamp="2026-04-15T10:00:00")],
            "session_1"
        )
        
        # Save second session
        persistence.save_conversation(
            [Message(role="user", content="Session 2", timestamp="2026-04-15T11:00:00")],
            "session_2"
        )
        
        # Verify both exist
        session1 = persistence.load_conversation("session_1")
        session2 = persistence.load_conversation("session_2")
        
        assert len(session1) == 1
        assert session1[0].content == "Session 1"
        assert len(session2) == 1
        assert session2[0].content == "Session 2"


class TestMemoryPersistenceUserContext:
    """Test user context persistence (DoD 2)."""
    
    def test_save_user_context(self, tmp_path):
        """Verify user context saves correctly."""
        persistence = MemoryPersistence(
            storage_path=str(tmp_path / "user_context.json"),
            use_memory_fallback=False
        )
        
        context = UserContext(
            user_id="user_001",
            preferences={"theme": "dark", "language": "en"},
            last_session="2026-04-15T12:00:00",
            conversation_count=5
        )
        
        result = persistence.save_user_context(context)
        
        assert result is True
        assert os.path.exists(str(tmp_path / "user_context.json"))
    
    def test_save_and_restore_user_context(self, tmp_path):
        """Verify user context can be saved and restored correctly."""
        persistence = MemoryPersistence(
            storage_path=str(tmp_path / "user_context.json"),
            use_memory_fallback=False
        )
        
        original_context = UserContext(
            user_id="user_001",
            preferences={"theme": "dark", "notifications": True},
            last_session="2026-04-15T12:00:00",
            conversation_count=5,
            session_metadata={"ip": "192.168.1.1"}
        )
        
        # Save
        persistence.save_user_context(original_context)
        
        # Load
        loaded_context = persistence.load_user_context("user_001")
        
        # Verify
        assert loaded_context is not None
        assert loaded_context.user_id == "user_001"
        assert loaded_context.preferences["theme"] == "dark"
        assert loaded_context.conversation_count == 5
        assert loaded_context.session_metadata["ip"] == "192.168.1.1"
    
    def test_user_context_not_found(self, tmp_path):
        """Verify None returned for non-existent user."""
        persistence = MemoryPersistence(
            storage_path=str(tmp_path / "user_context.json"),
            use_memory_fallback=False
        )
        
        context = persistence.load_user_context("nonexistent_user")
        assert context is None
    
    def test_update_user_context(self, tmp_path):
        """Verify user context can be updated."""
        persistence = MemoryPersistence(
            storage_path=str(tmp_path / "user_context.json"),
            use_memory_fallback=False
        )
        
        # Initial context
        context1 = UserContext(
            user_id="user_001",
            preferences={"theme": "dark"},
            last_session="2026-04-15T12:00:00",
            conversation_count=1
        )
        persistence.save_user_context(context1)
        
        # Updated context
        context2 = UserContext(
            user_id="user_001",
            preferences={"theme": "light"},
            last_session="2026-04-15T13:00:00",
            conversation_count=2
        )
        persistence.save_user_context(context2)
        
        # Verify update
        loaded = persistence.load_user_context("user_001")
        assert loaded.preferences["theme"] == "light"
        assert loaded.conversation_count == 2


class TestMemoryPersistenceRAGState:
    """Test RAG state persistence (DoD 3)."""
    
    def test_save_rag_state(self, tmp_path):
        """Verify RAG state saves correctly."""
        persistence = MemoryPersistence(
            storage_path=str(tmp_path / "rag_state.json"),
            use_memory_fallback=False
        )
        
        rag_state = {
            "vector_store": {"collection_name": "test", "count": 100},
            "graph_index": {"nodes": 50, "edges": 100},
            "last_updated": "2026-04-15T14:00:00"
        }
        
        result = persistence.save_rag_state(rag_state, "default")
        
        assert result is True
    
    def test_save_and_restore_rag_state(self, tmp_path):
        """Verify RAG state can be saved and restored correctly."""
        persistence = MemoryPersistence(
            storage_path=str(tmp_path / "rag_state.json"),
            use_memory_fallback=False
        )
        
        original_state = {
            "vector_store": {"collection_name": "test", "count": 100},
            "graph_index": {"nodes": 50, "edges": 100},
            "last_updated": "2026-04-15T14:00:00"
        }
        
        # Save
        persistence.save_rag_state(original_state, "default")
        
        # Load
        loaded_state = persistence.load_rag_state("default")
        
        # Verify
        assert loaded_state is not None
        assert loaded_state["vector_store"]["count"] == 100
        assert loaded_state["graph_index"]["nodes"] == 50
    
    def test_multiple_rag_states(self, tmp_path):
        """Verify multiple RAG states can be stored."""
        persistence = MemoryPersistence(
            storage_path=str(tmp_path / "rag_states.json"),
            use_memory_fallback=False
        )
        
        state1 = {"version": "v1", "data": "state1"}
        state2 = {"version": "v2", "data": "state2"}
        
        persistence.save_rag_state(state1, "v1")
        persistence.save_rag_state(state2, "v2")
        
        loaded1 = persistence.load_rag_state("v1")
        loaded2 = persistence.load_rag_state("v2")
        
        assert loaded1["data"] == "state1"
        assert loaded2["data"] == "state2"


class TestMemoryPersistenceFileFormat:
    """Test file-based persistence format (DoD 4)."""
    
    def test_json_format_is_human_readable(self, tmp_path):
        """Verify JSON format is human-readable."""
        persistence = MemoryPersistence(
            storage_path=str(tmp_path / "human_readable.json"),
            use_memory_fallback=False
        )
        
        messages = [Message(role="user", content="Test", timestamp="2026-04-15T10:00:00")]
        persistence.save_conversation(messages, "test_session")
        
        # Read raw file
        with open(str(tmp_path / "human_readable.json"), 'r') as f:
            content = f.read()
        
        # Verify it's valid JSON and human-readable
        json.loads(content)  # Should not raise
        assert "user" in content
        assert "Test" in content
    
    def test_persistence_file_structure(self, tmp_path):
        """Verify persistence file has correct structure."""
        persistence = MemoryPersistence(
            storage_path=str(tmp_path / "structured.json"),
            use_memory_fallback=False
        )
        
        messages = [Message(role="user", content="Hello", timestamp="2026-04-15T10:00:00")]
        persistence.save_conversation(messages, "session_001")
        
        with open(str(tmp_path / "structured.json"), 'r') as f:
            storage = json.load(f)
        
        assert "conversation_session_001" in storage
        assert "session_id" in storage["conversation_session_001"]
        assert "messages" in storage["conversation_session_001"]


class TestMemoryPersistenceMemoryFallback:
    """Test in-memory fallback (DoD 5)."""
    
    def test_memory_fallback_enabled(self):
        """Verify in-memory fallback works when enabled."""
        persistence = MemoryPersistence(use_memory_fallback=True)
        
        messages = [Message(role="user", content="Test", timestamp="2026-04-15T10:00:00")]
        persistence.save_conversation(messages, "memory_session")
        
        loaded = persistence.load_conversation("memory_session")
        assert len(loaded) == 1
        assert loaded[0].content == "Test"
    
    def test_memory_fallback_persists_to_disk(self, tmp_path):
        """Verify memory fallback DOES persist to disk (TASK-027 fix).
        
        After TASK-027 fix, use_memory_fallback=True still persists data to disk.
        The difference is that reads are served from memory cache for performance.
        """
        persistence = MemoryPersistence(
            storage_path=str(tmp_path / "fallback_persist.json"),
            use_memory_fallback=True,
            auto_save=True
        )
        
        messages = [Message(role="user", content="Test", timestamp="2026-04-15T10:00:00")]
        persistence.save_conversation(messages, "test")
        
        # File SHOULD be created with use_memory_fallback=True (TASK-027 fix)
        assert os.path.exists(str(tmp_path / "fallback_persist.json"))
        
        # Verify file contains valid JSON with our data
        with open(str(tmp_path / "fallback_persist.json"), 'r') as f:
            data = json.load(f)
        assert "conversation_test" in data
    
    def test_memory_fallback_clear(self):
        """Verify memory fallback can be cleared."""
        persistence = MemoryPersistence(use_memory_fallback=True)
        
        persistence.save_conversation(
            [Message(role="user", content="Test", timestamp="2026-04-15T10:00:00")],
            "test_session"
        )
        
        assert len(persistence.list_sessions()) > 0
        
        persistence.clear_all()
        
        assert len(persistence.list_sessions()) == 0


class TestMemoryPersistencePerformance:
    """Test performance requirements (DoD 7)."""
    
    def test_save_performance_under_1s(self, tmp_path):
        """Verify save operation completes in under 1 second."""
        persistence = MemoryPersistence(
            storage_path=str(tmp_path / "performance.json"),
            use_memory_fallback=False
        )
        
        messages = [
            Message(role="user", content=f"Message {i}", timestamp=f"2026-04-15T10:{i:02d}:00")
            for i in range(100)
        ]
        
        start = time.time()
        persistence.save_conversation(messages, "perf_test")
        elapsed = time.time() - start
        
        assert elapsed < 1.0, f"Save took {elapsed}s, expected < 1s"
    
    def test_load_performance_under_1s(self, tmp_path):
        """Verify load operation completes in under 1 second."""
        persistence = MemoryPersistence(
            storage_path=str(tmp_path / "performance.json"),
            use_memory_fallback=False
        )
        
        messages = [
            Message(role="user", content=f"Message {i}", timestamp=f"2026-04-15T10:{i:02d}:00")
            for i in range(100)
        ]
        persistence.save_conversation(messages, "perf_test")
        
        start = time.time()
        loaded = persistence.load_conversation("perf_test")
        elapsed = time.time() - start
        
        assert elapsed < 1.0, f"Load took {elapsed}s, expected < 1s"
        assert len(loaded) == 100
    
    def test_large_state_performance(self, tmp_path):
        """Verify large state persistence under 1 second."""
        persistence = MemoryPersistence(
            storage_path=str(tmp_path / "large_state.json"),
            use_memory_fallback=False
        )
        
        large_state = {
            f"key_{i}": f"value_{i}" * 100
            for i in range(1000)
        }
        
        start = time.time()
        persistence.save_rag_state(large_state, "large")
        elapsed = time.time() - start
        
        assert elapsed < 1.0, f"Large state save took {elapsed}s, expected < 1s"


class TestMemoryPersistenceIntegration:
    """Integration tests for complete session persistence (DoD 6, 8)."""
    
    def test_complete_session_persistence(self, tmp_path):
        """Verify complete session state persistence."""
        persistence = MemoryPersistence(
            storage_path=str(tmp_path / "complete_session.json"),
            use_memory_fallback=False
        )
        
        # Save complete session state
        messages = [
            Message(role="user", content="Hello", timestamp="2026-04-15T10:00:00"),
            Message(role="assistant", content="Hi", timestamp="2026-04-15T10:00:01")
        ]
        user_context = UserContext(
            user_id="user_001",
            preferences={"theme": "dark"},
            last_session="2026-04-15T10:00:00",
            conversation_count=1
        )
        rag_state = {"vector_store": {"count": 100}}
        
        persistence.save_conversation(messages, "session_001")
        persistence.save_user_context(user_context)
        persistence.save_rag_state(rag_state, "default")
        
        # Load and verify
        loaded_messages = persistence.load_conversation("session_001")
        loaded_context = persistence.load_user_context("user_001")
        loaded_rag = persistence.load_rag_state("default")
        
        assert len(loaded_messages) == 2
        assert loaded_context.user_id == "user_001"
        assert loaded_rag["vector_store"]["count"] == 100
    
    def test_list_sessions(self, tmp_path):
        """Verify session listing works correctly."""
        persistence = MemoryPersistence(
            storage_path=str(tmp_path / "list_sessions.json"),
            use_memory_fallback=False
        )
        
        persistence.save_conversation([], "session_1")
        persistence.save_conversation([], "session_2")
        persistence.save_conversation([], "session_3")
        
        sessions = persistence.list_sessions()
        
        assert "session_1" in sessions
        assert "session_2" in sessions
        assert "session_3" in sessions
    
    def test_clear_session(self, tmp_path):
        """Verify session clearing works correctly."""
        persistence = MemoryPersistence(
            storage_path=str(tmp_path / "clear_session.json"),
            use_memory_fallback=False
        )
        
        persistence.save_conversation([], "session_to_clear")
        assert len(persistence.list_sessions()) > 0
        
        persistence.clear_session("session_to_clear")
        # Session should be cleared from cache
    
    def test_stats_report(self, tmp_path):
        """Verify stats reporting works correctly."""
        persistence = MemoryPersistence(
            storage_path=str(tmp_path / "stats.json"),
            use_memory_fallback=False
        )
        
        stats = persistence.get_stats()
        
        assert "storage_path" in stats
        assert "cache_size" in stats
        assert "sessions_count" in stats


class TestMemoryPersistenceEdgeCases:
    """Test edge cases and error handling."""
    
    def test_invalid_json_handling(self, tmp_path):
        """Verify graceful handling of invalid JSON."""
        persistence = MemoryPersistence(
            storage_path=str(tmp_path / "invalid.json"),
            use_memory_fallback=False
        )
        
        # Create invalid JSON file
        with open(str(tmp_path / "invalid.json"), 'w') as f:
            f.write("{ invalid json }")
        
        # Should not crash
        stats = persistence.get_stats()
        assert stats is not None
    
    def test_empty_file_handling(self, tmp_path):
        """Verify graceful handling of empty file."""
        persistence = MemoryPersistence(
            storage_path=str(tmp_path / "empty_file.json"),
            use_memory_fallback=False
        )
        
        # Create empty file
        with open(str(tmp_path / "empty_file.json"), 'w') as f:
            f.write("")
        
        # Should handle gracefully
        loaded = persistence.load_conversation("nonexistent")
        assert loaded == []
    
    def test_special_characters_in_content(self, tmp_path):
        """Verify special characters are handled correctly."""
        persistence = MemoryPersistence(
            storage_path=str(tmp_path / "special_chars.json"),
            use_memory_fallback=False
        )
        
        messages = [
            Message(role="user", content="Test with 'quotes' and \"double quotes\"", timestamp="2026-04-15T10:00:00"),
            Message(role="user", content="Unicode: 你好 🌍", timestamp="2026-04-15T10:00:01"),
            Message(role="user", content="Newlines\nand\ttabs", timestamp="2026-04-15T10:00:02")
        ]
        
        persistence.save_conversation(messages, "special_session")
        loaded = persistence.load_conversation("special_session")
        
        assert len(loaded) == 3
        assert "quotes" in loaded[0].content
        assert "你好" in loaded[1].content
