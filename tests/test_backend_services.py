from __future__ import annotations

from backend.database import init_db
from backend.services import (
    build_rag_index,
    ensure_merged_graph,
    initialize_app_data,
    integration_stats,
    list_textbooks,
)


def test_sample_textbooks_and_graphs_load() -> None:
    init_db()
    initialize_app_data()
    textbooks = list_textbooks()
    assert len(textbooks) >= 7
    assert all(book["chapter_count"] > 0 for book in textbooks[:7])
    graph = ensure_merged_graph()
    assert graph["nodes"]
    assert graph["stats"]["node_count"] > 0


def test_rag_chunks_are_generated() -> None:
    init_db()
    initialize_app_data()
    result = build_rag_index()
    assert result["status"] == "indexed"
    assert result["chunks"] > 0
    stats = integration_stats()
    assert stats["rag_chunks"] > 0

