from __future__ import annotations

from pathlib import Path

from backend.database import init_db
from backend.services import (
    build_rag_index,
    ensure_merged_graph,
    get_graph,
    initialize_app_data,
    integration_stats,
    list_decisions,
    list_textbooks,
    update_decision,
)


def test_sample_textbooks_and_graphs_load(tmp_path: Path) -> None:
    init_db(tmp_path / "app.db")
    initialize_app_data()
    textbooks = list_textbooks()
    assert len(textbooks) >= 7
    assert all(book["chapter_count"] > 0 for book in textbooks[:7])
    source_graph = get_graph(textbooks[0]["id"])
    assert any(edge["relation_type"] == "contains" for edge in source_graph["edges"])
    graph = ensure_merged_graph()
    assert graph["nodes"]
    assert graph["stats"]["node_count"] > 0
    assert any(edge["relation_type"] == "contains" for edge in graph["edges"])


def test_rag_chunks_are_generated(tmp_path: Path) -> None:
    init_db(tmp_path / "app.db")
    initialize_app_data()
    result = build_rag_index(sync_dify=False)
    assert result["status"] == "indexed"
    assert result["chunks"] > 0
    stats = integration_stats()
    assert stats["rag_chunks"] > 0


def test_rejecting_merge_decision_updates_graph_and_persists(tmp_path: Path) -> None:
    init_db(tmp_path / "app.db")
    initialize_app_data()
    graph_before = ensure_merged_graph()
    decisions = [item for item in list_decisions() if item["action"] == "merge" and item["status"] == "active"]
    assert decisions

    updated = update_decision(decisions[0]["id"], {"status": "rejected", "reason": "教师复核：暂不合并该知识点。"})

    assert updated["status"] == "rejected"
    assert "教师复核" in updated["reason"]
    graph_after = ensure_merged_graph()
    assert graph_after["stats"]["node_count"] >= graph_before["stats"]["node_count"]
    refreshed = next(item for item in list_decisions() if item["id"] == decisions[0]["id"])
    assert refreshed["status"] == "rejected"
    assert refreshed["char_saved"] == 0
