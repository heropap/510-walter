from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class Textbook(BaseModel):
    id: str
    title: str
    filename: str
    source_path: str
    split_path: str | None = None
    status: str
    total_chars: int
    chapter_count: int
    metadata: dict[str, Any] = Field(default_factory=dict)


class Chapter(BaseModel):
    id: str
    textbook_id: str
    title: str
    level: int
    parent_id: str | None = None
    path: str
    content: str
    char_count: int
    sort_order: int
    metadata: dict[str, Any] = Field(default_factory=dict)


class GraphNode(BaseModel):
    id: str
    name: str
    definition: str = ""
    category: str = "核心概念"
    body_system: str = "全身/通用"
    organ: str = "未知"
    anatomical_region: str = "未知"
    scale_level: str = "未知"
    stage: str = "未知"
    importance: str = "medium"
    frequency: int = 1
    evidence: str = ""
    textbook_id: str | None = None
    chapter_id: str | None = None
    chapter_title: str | None = None
    source_textbooks: list[str] = Field(default_factory=list)
    method: str = "rule"
    confidence: float = 0.72


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    relation_type: str
    medical_relation_type: str = ""
    description: str = ""
    confidence: float = 0.7
    evidence: str = ""
    textbook_id: str | None = None
    chapter_title: str | None = None
    method: str = "rule"


class KnowledgeGraph(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    stats: dict[str, Any] = Field(default_factory=dict)


class RagQuery(BaseModel):
    question: str
    conversation_id: str | None = None


class ChatMessageIn(BaseModel):
    message: str
    session_id: str = "default"


class DecisionUpdate(BaseModel):
    status: Literal["active", "hidden", "rejected"] | None = None
    reason: str | None = None

