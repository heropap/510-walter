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
    local_search,
    local_search_bm25,
    list_textbooks,
    update_decision,
)
from backend.text_processing import extract_definition_candidates


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


def test_local_search_returns_citations_with_hybrid_method(tmp_path: Path) -> None:
    init_db(tmp_path / "app.db")
    initialize_app_data()
    build_rag_index(sync_dify=False)

    citations = local_search("肺炎链球菌为什么会导致肺泡炎症和低氧血症？")
    bm25_citations = local_search_bm25("肺炎链球菌")

    assert citations
    assert citations[0]["chunk_preview"]
    assert citations[0]["retrieval_method"] in {"keyword", "bm25", "keyword+bm25"}
    assert bm25_citations


def test_definition_sentence_candidates_are_extracted() -> None:
    candidates = extract_definition_candidates(
        "肺泡",
        "肺泡隔是相邻肺泡之间的薄层结缔组织。肺泡是肺进行气体交换的基本结构，由肺泡上皮和毛细血管共同参与气体交换。",
    )
    assert any(item["name"] == "肺泡" or item["name"] == "肺泡隔" for item in candidates)


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
