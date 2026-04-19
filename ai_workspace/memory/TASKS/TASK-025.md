# TASK-025: Directory Scanning & Incremental Indexing

## Summary

Реалізувати автоматичне сканування директорій та інкрементальне індексування файлів в RAG-системі.

## DoD (Definition of Done)

### DoD-1: Користувач може додати шляхи в `default.yaml`
- [x] **Status:** COMPLETED
- **Evidence:** `ai_workspace/config/default.yaml` містить секцію `directory_scanning` з `watched_directories`, `allowed_extensions`, `scan`, `indexing`, `state` конфігураціями.

### DoD-2: При старті — автоматичне сканування
- [x] **Status:** COMPLETED
- **Evidence:** `DirectoryScannerWorker.start()` викликає `initial_scan()` перед запуском `awatch()`. `rag_server.py` lifecycle hooks ініціалізують сканер при `startup`.

### DoD-3: Додавання файлу → автоматична індексація
- [x] **Status:** COMPLETED
- **Evidence:** `handle_file_change(filepath, "added")` викликає `index_file()`. Тест: `test_handle_added_new_file` в `test_incremental_index_manager.py`.

### DoD-4: Зміна файлу → переіндексація
- [x] **Status:** COMPLETED
- **Evidence:** `handle_file_change(filepath, "modified")` викликає `reindex_file()` (delete + index). Тест: `test_handle_modified_changed`.

### DoD-5: Видалення файлу → видалення чанків з ChromaDB
- [x] **Status:** COMPLETED
- **Evidence:** `handle_file_change(filepath, "deleted")` викликає `delete_from_index()` з `where={"source": filepath}`. Тест: `test_handle_deleted_existing`.

### DoD-6: Підтримка .txt, .md, .json, .csv (case-insensitive)
- [x] **Status:** COMPLETED
- **Evidence:** `_is_allowed_extension()` використовує `.lower()` для порівняння. Тести: `test_allowed_extension_uppercase`, `test_case_insensitive_Md`, `test_filter_case_insensitive`.

### DoD-7: Рекурсивні директорії
- [x] **Status:** COMPLETED
- **Evidence:** `initial_scan()` використовує `Path.rglob("*")` для рекурсивного збору файлів. Конфігурація: `recursive: true` в `watched_directories`.

### DoD-8: Стан зберігається в JSON
- [x] **Status:** COMPLETED
- **Evidence:** `save_state()` зберігає `{"files": {filepath: hash}, "last_scan": ISO}` в JSON. Тести: `test_save_and_load_state`, `test_initial_scan_creates_state_file`.

### DoD-9: Non-blocking asyncio
- [x] **Status:** COMPLETED
- **Evidence:** `DirectoryScannerWorker` працює як `asyncio.create_task()`. `handle_file_change` виконується через `run_in_executor()`.

### DoD-10: Debouncing
- [x] **Status:** COMPLETED
- **Evidence:** `watchfiles.awatch()` з `debounce_ms=500` (за замовчуванням). `_process_changes()` групує зміни по filepath. Тест: `test_process_changes_groups_same_file`.

### DoD-11: Error handling + logging
- [x] **Status:** COMPLETED
- **Evidence:** `_process_changes()` має `try/except` з `logger.error(..., exc_info=True)`. Тест: `test_process_changes_handles_error_gracefully`.

### DoD-12: enabled: false вимикає сканер
- [x] **Status:** COMPLETED
- **Evidence:** `start()` перевіряє `if not self.enabled: return`. Тест: `test_start_disabled_scanner`.

### DoD-13-16: Тести
- [x] **Status:** COMPLETED
- **Evidence:** 
  - `test_incremental_index_manager.py`: 29 тестів (hashing, state, extensions, indexing, file changes, initial scan, stats)
  - `test_directory_scanner.py`: 15 тестів (lifecycle, change resolution, watch filter, process changes, status)
  - **Всього: 44 тести, всі пройдено**

### DoD-17-18: Документація
- [x] **Status:** COMPLETED
- **Evidence:** `ai_workspace/docs/DIRECTORY_SCANNING.md` містить повну документацію з архітектурою, конфігурацією, API, прикладами використання.

## Files Created/Modified

| File | Action | Description |
|------|--------|-------------|
| `ai_workspace/requirements_mcp.txt` | Modified | Додано `watchfiles>=0.21.0` |
| `ai_workspace/config/default.yaml` | Modified | Додано секцію `directory_scanning` |
| `ai_workspace/src/core/incremental_index_manager.py` | Created | IncrementalIndexManager клас |
| `ai_workspace/src/core/directory_scanner.py` | Created | DirectoryScannerWorker клас |
| `ai_workspace/src/core/memory_manager.py` | Modified | Додано `delete_documents_by_source()`, `get_stats_by_source()` |
| `ai_workspace/src/api/rag_server.py` | Modified | Додано lifecycle hooks для сканера |
| `ai_workspace/tests/test_incremental_index_manager.py` | Created | 29 unit тестів |
| `ai_workspace/tests/test_directory_scanner.py` | Created | 15 unit тестів |
| `ai_workspace/pytest.ini` | Modified | Додано `asyncio_mode = auto` |
| `ai_workspace/docs/DIRECTORY_SCANNING.md` | Created | Документація |

## Test Results

```
======================== 44 passed, 5 warnings in 2.43s ========================
```

## Task Status: COMPLETED
