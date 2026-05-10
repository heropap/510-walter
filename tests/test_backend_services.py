from __future__ import annotations

from pathlib import Path

from backend.database import init_db
from backend.services import (
    build_textbook_graph,
    build_rag_index,
    DeepSeekClient,
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
from backend.config import get_settings
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


def test_deepseek_keywords_are_written_as_primary_nodes(tmp_path: Path, monkeypatch) -> None:
    init_db(tmp_path / "app.db")
    initialize_app_data()
    textbook = list_textbooks()[0]

    def fake_extract_keywords(self, textbook_title, chapters, limit=60):
        return {
            "used_llm": True,
            "provider": "deepseek",
            "model": "fake-deepseek",
            "keywords": [
                {
                    "keyword": "肺泡",
                    "aliases": ["alveolus"],
                    "definition": "肺泡是气体交换相关结构。",
                    "category": "解剖结构",
                    "body_system": "呼吸系统",
                    "scale_level": "组织",
                    "stage": "正常结构",
                    "importance": "high",
                    "chapter_refs": [chapters[0]["title"]],
                    "evidence_hint": "肺泡是肺进行气体交换的基本结构",
                    "reason": "用于验证 DeepSeek 主提取写入节点。",
                }
            ],
            "themes": ["呼吸结构"],
        }

    monkeypatch.setattr("backend.services.DeepSeekClient.extract_keywords", fake_extract_keywords)
    graph = build_textbook_graph(textbook["id"], use_deepseek=True)

    nodes = [node for node in graph["nodes"] if node["method"] == "deepseek_primary_keyword"]
    assert nodes
    assert nodes[0]["name"] == "肺泡"
    assert graph["stats"]["extraction_provider"] == "deepseek"


def test_deepseek_keyword_cache_is_used_without_api(tmp_path: Path, monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "root_dir", tmp_path)
    monkeypatch.setattr(settings, "output_dir", tmp_path / "data" / "outputs")
    monkeypatch.setattr(settings, "openai_api_key", "")
    cache_dir = tmp_path / "deepseek_keyword_cache"
    cache_dir.mkdir(parents=True)
    (cache_dir / "01_局部解剖学.json").write_text(
        """
        {
          "textbook_id": "01_局部解剖学",
          "textbook_title": "局部解剖学",
          "keywords": [
            {
              "keyword": "翼点",
              "aliases": ["pterion"],
              "category": "解剖结构",
              "body_system": "头部",
              "importance": "high",
              "chapter_refs": ["概述"],
              "evidence_hint": "位于颧弓中点上方约二横指处",
              "reason": "离线导出验证"
            }
          ]
        }
        """.strip(),
        encoding="utf-8",
    )

    result = DeepSeekClient(settings).extract_keywords(
        "局部解剖学",
        [{"textbook_id": "01_局部解剖学", "title": "概述", "content": ""}],
    )

    assert result["used_llm"] is True
    assert result["provider"] == "deepseek_export"
    assert result["from_cache"] is True
    assert result["keywords"][0]["keyword"] == "翼点"


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
