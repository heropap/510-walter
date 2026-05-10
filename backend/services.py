from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import httpx

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None

from fastapi import HTTPException, UploadFile

from .config import Settings, get_settings
from .database import as_json, db, from_json, row_to_dict
from .text_processing import (
    chunk_text,
    compact_evidence,
    definition_from_content,
    extract_definition_candidates,
    normalize_name,
    parse_markdown_note,
    stable_id,
)


TEXTBOOK_TITLES = {
    "01_局部解剖学": "局部解剖学",
    "02_组织学与胚胎学": "组织学与胚胎学",
    "03_生理学": "生理学",
    "04_医学微生物学": "医学微生物学",
    "05_病理学": "病理学",
    "06_传染病学": "传染病学",
    "07_病理生理学": "病理生理学",
}

BODY_SYSTEM_KEYWORDS = [
    ("呼吸系统", "肺", "胸部", ["肺", "支气管", "气管", "胸膜", "呼吸", "肺泡"]),
    ("循环系统", "心脏", "胸部", ["心", "血管", "循环", "动脉", "静脉", "血液"]),
    ("消化系统", "胃肠", "腹部", ["胃", "肠", "肝", "胆", "胰", "消化", "腹膜"]),
    ("泌尿系统", "肾", "腹部", ["肾", "尿", "膀胱", "输尿管"]),
    ("神经系统", "脑", "头颈部", ["脑", "神经", "脊髓", "感觉", "运动"]),
    ("免疫系统", "免疫", "全身", ["免疫", "淋巴", "抗体", "抗原", "炎症"]),
    ("生殖系统", "生殖器官", "盆部", ["生殖", "妊娠", "卵巢", "睾丸", "子宫"]),
    ("运动系统", "骨骼肌", "四肢", ["骨", "肌", "关节", "上肢", "下肢"]),
    ("感染病", "病原体", "全身", ["病毒", "细菌", "感染", "传染", "病原", "真菌", "寄生虫"]),
]

CATEGORY_RULES = [
    ("病原体", ["病毒", "细菌", "真菌", "衣原体", "支原体", "螺旋体", "寄生虫"]),
    ("疾病", ["病", "炎", "综合征", "休克", "衰竭", "肿瘤", "癌"]),
    ("治疗预防", ["治疗", "防治", "预防", "疫苗", "药物", "抗菌"]),
    ("诊断检查", ["诊断", "检查", "检测", "实验", "影像", "鉴别"]),
    ("解剖结构", ["部", "区", "管", "膜", "腔", "肌", "骨", "器官"]),
    ("生理功能", ["功能", "调节", "代谢", "循环", "呼吸", "吸收", "排出"]),
    ("病理机制", ["机制", "发病", "损伤", "紊乱", "缺氧", "应激"]),
]

STAGE_RULES = [
    ("正常结构", ["解剖", "组织", "结构", "形态"]),
    ("正常功能", ["生理", "功能", "调节", "代谢"]),
    ("感染传播", ["感染", "传染", "病原", "流行"]),
    ("病理形态", ["病理", "炎症", "肿瘤", "坏死", "变性"]),
    ("病理生理", ["病理生理", "休克", "缺氧", "紊乱", "衰竭"]),
    ("临床应用", ["诊断", "治疗", "预防", "防治", "检查"]),
]

SCALE_RULES = [
    ("宏观解剖", ["局部解剖", "头部", "颈部", "胸部", "腹部", "上肢", "下肢"]),
    ("器官", ["心", "肺", "肝", "肾", "胃", "脑", "脾", "胰"]),
    ("组织", ["组织", "上皮", "结缔", "肌组织", "神经组织"]),
    ("细胞", ["细胞", "红细胞", "白细胞", "巨噬", "淋巴"]),
    ("分子", ["分子", "基因", "蛋白", "受体", "抗体", "酶"]),
    ("病原体", ["病毒", "细菌", "真菌", "寄生虫"]),
    ("疾病/临床", ["疾病", "诊断", "治疗", "临床", "感染"]),
]


def initialize_app_data() -> None:
    settings = get_settings()
    register_sample_textbooks(settings)
    ensure_graphs_for_all()
    ensure_merged_graph()


def list_textbooks() -> list[dict[str, Any]]:
    with db() as conn:
        rows = conn.execute("SELECT * FROM textbooks ORDER BY id").fetchall()
    return [row_to_dict(row) for row in rows if row_to_dict(row)]


def delete_textbook(textbook_id: str) -> dict[str, Any]:
    with db() as conn:
        row = conn.execute("SELECT * FROM textbooks WHERE id = ?", (textbook_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Textbook not found")
        conn.execute("DELETE FROM textbooks WHERE id = ?", (textbook_id,))
    ensure_merged_graph()
    build_rag_index(sync_dify=False)
    return {"deleted": textbook_id}


def get_textbook(textbook_id: str) -> dict[str, Any]:
    with db() as conn:
        row = conn.execute("SELECT * FROM textbooks WHERE id = ?", (textbook_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Textbook not found")
        chapters = conn.execute(
            "SELECT id,title,level,parent_id,path,char_count,sort_order,metadata FROM chapters WHERE textbook_id = ? ORDER BY sort_order",
            (textbook_id,),
        ).fetchall()
    data = row_to_dict(row)
    data["chapters"] = [row_to_dict(chapter) for chapter in chapters]
    return data


def register_sample_textbooks(settings: Settings) -> None:
    if not settings.raw_textbook_dir.exists():
        return
    for source in sorted(settings.raw_textbook_dir.glob("*.md")):
        textbook_id = source.stem
        title = TEXTBOOK_TITLES.get(textbook_id, re.sub(r"^\d+_", "", source.stem))
        split_path = settings.split_dir / textbook_id
        total_chars = source.stat().st_size
        chapters = load_chapters_from_split_dir(textbook_id, split_path)
        with db() as conn:
            conn.execute(
                """
                INSERT INTO textbooks (id,title,filename,source_path,split_path,status,total_chars,chapter_count,metadata,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    title=excluded.title,
                    filename=excluded.filename,
                    source_path=excluded.source_path,
                    split_path=excluded.split_path,
                    status=excluded.status,
                    total_chars=excluded.total_chars,
                    chapter_count=excluded.chapter_count,
                    metadata=excluded.metadata,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    textbook_id,
                    title,
                    source.name,
                    str(source),
                    str(split_path) if split_path.exists() else None,
                    "ready" if chapters else "needs_split",
                    total_chars,
                    len(chapters),
                    as_json({"builtin": True}),
                ),
            )
            conn.execute("DELETE FROM chapters WHERE textbook_id = ?", (textbook_id,))
            for chapter in chapters:
                conn.execute(
                    """
                    INSERT INTO chapters (id,textbook_id,title,level,parent_id,path,content,char_count,sort_order,metadata)
                    VALUES (?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        chapter["id"],
                        textbook_id,
                        chapter["title"],
                        chapter["level"],
                        chapter["parent_id"],
                        chapter["path"],
                        chapter["content"],
                        len(chapter["content"]),
                        chapter["sort_order"],
                        as_json(chapter["metadata"]),
                    ),
                )


def load_chapters_from_split_dir(textbook_id: str, split_path: Path) -> list[dict[str, Any]]:
    if not split_path.exists():
        return []
    files = [path for path in split_path.rglob("*.md") if path.name != "00_总目录.md"]
    files.sort(key=lambda path: tuple("" if part == "index.md" else part for part in path.relative_to(split_path).parts))
    path_to_id: dict[str, str] = {}
    chapters: list[dict[str, Any]] = []
    for order, path in enumerate(files, start=1):
        rel = path.relative_to(split_path)
        note = parse_markdown_note(path)
        level = len(rel.parts)
        if path.name == "index.md":
            level = max(len(rel.parts) - 1, 1)
        parent_rel = rel.parent / "index.md" if path.name != "index.md" else rel.parent.parent / "index.md"
        parent_key = str(parent_rel) if str(parent_rel) != "." else ""
        parent_id = path_to_id.get(parent_key)
        chapter_id = stable_id(textbook_id, rel.as_posix(), prefix="ch_")
        path_to_id[str(rel)] = chapter_id
        chapters.append(
            {
                "id": chapter_id,
                "title": note["title"],
                "level": min(max(level, 1), 4),
                "parent_id": parent_id,
                "path": str(path),
                "content": note["content"],
                "sort_order": order,
                "metadata": {"relative_path": rel.as_posix()},
            }
        )
    return chapters


def fallback_full_text_chapter(textbook_id: str, markdown_path: Path) -> list[dict[str, Any]]:
    content = markdown_path.read_text(encoding="utf-8", errors="ignore").strip()
    if not content:
        raise HTTPException(status_code=400, detail="文件转换后没有可导入的文本内容。")
    title = re.sub(r"^\d+_", "", markdown_path.stem) or "全文"
    return [
        {
            "id": stable_id(textbook_id, "full_text", prefix="ch_"),
            "title": title,
            "level": 1,
            "parent_id": None,
            "path": str(markdown_path),
            "content": content,
            "sort_order": 1,
            "metadata": {"relative_path": markdown_path.name, "fallback": True},
        }
    ]


async def handle_upload(file: UploadFile) -> dict[str, Any]:
    settings = get_settings()
    filename = Path(file.filename or "uploaded.md").name
    safe_stem = re.sub(r"[^\w\u4e00-\u9fff.-]+", "_", Path(filename).stem)
    textbook_id = f"user_{stable_id(filename, prefix='')[:10]}"
    raw_path = settings.uploaded_dir / filename
    with raw_path.open("wb") as fh:
        shutil.copyfileobj(file.file, fh)

    markdown_path = settings.markdown_dir / f"{textbook_id}.md"
    suffix = raw_path.suffix.lower()
    if suffix in {".md", ".markdown", ".txt"}:
        text = raw_path.read_text(encoding="utf-8", errors="ignore")
        markdown_path.write_text(text, encoding="utf-8")
    else:
        convert_with_markitdown(raw_path, markdown_path)

    split_target = settings.runtime_split_dir / textbook_id
    script = settings.root_dir / "scripts" / "mdsplit_obsidian.py"
    subprocess.run(
        [
            sys.executable,
            str(script),
            str(markdown_path),
            "--out",
            str(settings.runtime_split_dir),
            "--mode",
            "auto",
            "--max-level",
            "2",
            "--force",
        ],
        check=True,
        cwd=settings.root_dir,
    )
    if not split_target.exists():
        generated = settings.runtime_split_dir / markdown_path.stem
        if generated.exists() and generated != split_target:
            generated.rename(split_target)

    chapters = load_chapters_from_split_dir(textbook_id, split_target)
    if not chapters:
        chapters = fallback_full_text_chapter(textbook_id, markdown_path)
    with db() as conn:
        conn.execute(
            """
            INSERT INTO textbooks (id,title,filename,source_path,split_path,status,total_chars,chapter_count,metadata)
            VALUES (?,?,?,?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET
              title=excluded.title,filename=excluded.filename,source_path=excluded.source_path,
              split_path=excluded.split_path,status=excluded.status,total_chars=excluded.total_chars,
              chapter_count=excluded.chapter_count,metadata=excluded.metadata,updated_at=CURRENT_TIMESTAMP
            """,
            (
                textbook_id,
                safe_stem,
                filename,
                str(raw_path),
                str(split_target),
                "ready",
                len(markdown_path.read_text(encoding="utf-8", errors="ignore")),
                len(chapters),
                as_json({"builtin": False}),
            ),
        )
        conn.execute("DELETE FROM chapters WHERE textbook_id = ?", (textbook_id,))
        for chapter in chapters:
            conn.execute(
                """
                INSERT INTO chapters (id,textbook_id,title,level,parent_id,path,content,char_count,sort_order,metadata)
                VALUES (?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    chapter["id"],
                    textbook_id,
                    chapter["title"],
                    chapter["level"],
                    chapter["parent_id"],
                    chapter["path"],
                    chapter["content"],
                    len(chapter["content"]),
                    chapter["sort_order"],
                    as_json(chapter["metadata"]),
                ),
            )
    graph = build_textbook_graph(textbook_id)
    merged_graph = ensure_merged_graph()
    rag_index = build_rag_index(sync_dify=False)
    dify_sync = sync_textbook_to_dify(textbook_id)
    return {
        "textbook": get_textbook(textbook_id),
        "graph_stats": graph["stats"],
        "merged_stats": merged_graph["stats"],
        "rag_index": rag_index,
        "dify_sync": dify_sync,
    }


def find_markitdown_bin() -> str | None:
    settings = get_settings()
    candidates = [
        settings.markitdown_bin,
        str(settings.root_dir / ".venv" / "bin" / "markitdown"),
        shutil.which("markitdown"),
        "/Users/walter/.local/bin/markitdown",
    ]
    for candidate in candidates:
        if not candidate:
            continue
        resolved = shutil.which(candidate) if not Path(candidate).is_absolute() else candidate
        if resolved and Path(resolved).exists():
            return resolved
    return None


def convert_with_markitdown(source: Path, target: Path) -> None:
    package_error: Exception | None = None
    try:
        from markitdown import MarkItDown

        result = MarkItDown(enable_plugins=False).convert(source)
        target.write_text(result.text_content, encoding="utf-8")
        return
    except Exception as exc:
        package_error = exc

    markitdown_bin = find_markitdown_bin()
    if not markitdown_bin:
        detail = "当前环境未找到 MarkItDown CLI。请安装 Python 包或设置 MARKITDOWN_BIN 指向本地 markitdown CLI。"
        if package_error:
            detail = f"MarkItDown Python 包转换失败，且未找到 CLI fallback: {str(package_error)[:500]}"
        raise HTTPException(
            status_code=400,
            detail=detail,
        )
    completed = subprocess.run(
        [markitdown_bin, str(source), "-o", str(target)],
        cwd=get_settings().root_dir,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise HTTPException(
            status_code=400,
            detail=f"MarkItDown 转换失败: {(completed.stderr or completed.stdout).strip()[:500]}",
        )
    if not target.exists():
        raise HTTPException(status_code=400, detail="MarkItDown 转换未生成 Markdown 文件。")


def classify_node(title: str, content: str, textbook_title: str) -> dict[str, str]:
    haystack = f"{textbook_title} {title} {content[:500]}"
    body_system, organ, region = "全身/通用", "未知", "未知"
    for system, matched_organ, matched_region, keywords in BODY_SYSTEM_KEYWORDS:
        if any(word in haystack for word in keywords):
            body_system, organ, region = system, matched_organ, matched_region
            break
    category = "核心概念"
    for label, keywords in CATEGORY_RULES:
        if any(word in haystack for word in keywords):
            category = label
            break
    stage = "未知"
    for label, keywords in STAGE_RULES:
        if any(word in haystack for word in keywords):
            stage = label
            break
    scale = "未知"
    for label, keywords in SCALE_RULES:
        if any(word in haystack for word in keywords):
            scale = label
            break
    importance = "high" if len(content) > 4000 or any(k in title for k in ["总论", "概述", "机制", "诊断"]) else "medium"
    return {
        "category": category,
        "body_system": body_system,
        "organ": organ,
        "anatomical_region": region,
        "scale_level": scale,
        "stage": stage,
        "importance": importance,
    }


def build_textbook_graph(textbook_id: str) -> dict[str, Any]:
    with db() as conn:
        textbook = conn.execute("SELECT * FROM textbooks WHERE id = ?", (textbook_id,)).fetchone()
        if not textbook:
            raise HTTPException(status_code=404, detail="Textbook not found")
        chapters = conn.execute(
            "SELECT * FROM chapters WHERE textbook_id = ? ORDER BY sort_order",
            (textbook_id,),
        ).fetchall()
        conn.execute("DELETE FROM nodes WHERE textbook_id = ?", (textbook_id,))
        conn.execute("DELETE FROM edges WHERE textbook_id = ?", (textbook_id,))

        textbook_title = textbook["title"]
        chapter_node_ids: dict[str, str] = {}
        sibling_groups: dict[str, list[str]] = defaultdict(list)
        for chapter in chapters:
            title = chapter["title"]
            content = chapter["content"]
            node_id = stable_id(textbook_id, chapter["id"], title, prefix="node_")
            chapter_node_ids[chapter["id"]] = node_id
            labels = classify_node(title, content, textbook_title)
            definition = definition_from_content(title, content)
            evidence = compact_evidence(content, 180)
            conn.execute(
                """
                INSERT INTO nodes (
                  id,textbook_id,name,definition,category,body_system,organ,anatomical_region,
                  scale_level,stage,importance,frequency,evidence,chapter_id,chapter_title,
                  source_textbooks,method,confidence,metadata
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    node_id,
                    textbook_id,
                    title,
                    definition,
                    labels["category"],
                    labels["body_system"],
                    labels["organ"],
                    labels["anatomical_region"],
                    labels["scale_level"],
                    labels["stage"],
                    labels["importance"],
                    1,
                    evidence,
                    chapter["id"],
                    title,
                    as_json([textbook_title]),
                    "rule_from_chapter",
                    0.74,
                    as_json({"path": chapter["path"], "char_count": chapter["char_count"]}),
                ),
            )
            for index, candidate in enumerate(extract_definition_candidates(title, content, limit=3), start=1):
                candidate_name = candidate["name"]
                candidate_definition = candidate["definition"]
                candidate_evidence = candidate["evidence"]
                candidate_id = stable_id(textbook_id, chapter["id"], candidate_name, index, prefix="node_def_")
                candidate_labels = classify_node(candidate_name, candidate_definition, textbook_title)
                conn.execute(
                    """
                    INSERT INTO nodes (
                      id,textbook_id,name,definition,category,body_system,organ,anatomical_region,
                      scale_level,stage,importance,frequency,evidence,chapter_id,chapter_title,
                      source_textbooks,method,confidence,metadata
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        candidate_id,
                        textbook_id,
                        candidate_name,
                        candidate_definition,
                        candidate_labels["category"],
                        candidate_labels["body_system"],
                        candidate_labels["organ"],
                        candidate_labels["anatomical_region"],
                        candidate_labels["scale_level"],
                        candidate_labels["stage"],
                        "medium",
                        1,
                        candidate_evidence,
                        chapter["id"],
                        title,
                        as_json([textbook_title]),
                        "rule_definition_sentence",
                        0.79,
                        as_json({"path": chapter["path"], "parent_chapter_node": node_id}),
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO edges (id,source,target,relation_type,medical_relation_type,description,confidence,evidence,textbook_id,chapter_title,method)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        stable_id(node_id, candidate_id, "defines", prefix="edge_"),
                        node_id,
                        candidate_id,
                        "defines",
                        "definition_of",
                        "定义句抽取显示该章节解释了该知识点。",
                        0.78,
                        candidate_evidence,
                        textbook_id,
                        title,
                        "definition_sentence_rule",
                    ),
                )
            sibling_groups[chapter["parent_id"] or "root"].append(node_id)

        edge_seen: set[tuple[str, str, str]] = set()
        for chapter in chapters:
            if chapter["parent_id"] and chapter["parent_id"] in chapter_node_ids:
                source = chapter_node_ids[chapter["parent_id"]]
                target = chapter_node_ids[chapter["id"]]
                key = (source, target, "contains")
                if key not in edge_seen:
                    edge_seen.add(key)
                    conn.execute(
                        """
                        INSERT INTO edges (id,source,target,relation_type,medical_relation_type,description,confidence,evidence,textbook_id,chapter_title,method)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?)
                        """,
                        (
                            stable_id(source, target, "contains", prefix="edge_"),
                            source,
                            target,
                            "contains",
                            "part_of",
                            "章节结构显示上级主题包含该知识点。",
                            0.86,
                            "章节目录层级",
                            textbook_id,
                            chapter["title"],
                            "chapter_structure",
                        ),
                    )
        for siblings in sibling_groups.values():
            for left, right in zip(siblings, siblings[1:]):
                key = (left, right, "parallel")
                if key not in edge_seen:
                    edge_seen.add(key)
                    conn.execute(
                        """
                        INSERT INTO edges (id,source,target,relation_type,medical_relation_type,description,confidence,evidence,textbook_id,method)
                        VALUES (?,?,?,?,?,?,?,?,?,?)
                        """,
                        (
                            stable_id(left, right, "parallel", prefix="edge_"),
                            left,
                            right,
                            "parallel",
                            "",
                            "同一上级目录下的并列知识点。",
                            0.64,
                            "章节目录并列关系",
                            textbook_id,
                            "chapter_structure",
                        ),
                    )
    return get_graph(textbook_id)


def ensure_graphs_for_all() -> None:
    for textbook in list_textbooks():
        with db() as conn:
            count = conn.execute("SELECT COUNT(*) FROM nodes WHERE textbook_id = ?", (textbook["id"],)).fetchone()[0]
            parent_count = conn.execute("SELECT COUNT(*) FROM chapters WHERE textbook_id = ? AND parent_id IS NOT NULL", (textbook["id"],)).fetchone()[0]
            contains_count = conn.execute("SELECT COUNT(*) FROM edges WHERE textbook_id = ? AND relation_type = 'contains'", (textbook["id"],)).fetchone()[0]
        if textbook.get("chapter_count", 0) > 0 and (count == 0 or (parent_count > 0 and contains_count == 0)):
            build_textbook_graph(textbook["id"])


def _graph_from_rows(nodes: list[Any], edges: list[Any], stats: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "nodes": [row_to_dict(row) for row in nodes],
        "edges": [row_to_dict(row) for row in edges],
        "stats": stats or {},
    }


def get_graph(textbook_id: str, limit: int = 900) -> dict[str, Any]:
    with db() as conn:
        textbook = conn.execute("SELECT * FROM textbooks WHERE id = ?", (textbook_id,)).fetchone()
        if not textbook:
            raise HTTPException(status_code=404, detail="Textbook not found")
        nodes = conn.execute(
            "SELECT * FROM nodes WHERE textbook_id = ? ORDER BY importance DESC, name LIMIT ?",
            (textbook_id, limit),
        ).fetchall()
        node_ids = [row["id"] for row in nodes]
        if node_ids:
            placeholders = ",".join("?" for _ in node_ids)
            edges = conn.execute(
                f"SELECT * FROM edges WHERE textbook_id = ? AND source IN ({placeholders}) AND target IN ({placeholders}) LIMIT ?",
                [textbook_id, *node_ids, *node_ids, limit * 2],
            ).fetchall()
        else:
            edges = []
    return _graph_from_rows(
        nodes,
        edges,
        {
            "textbook_id": textbook_id,
            "textbook_title": textbook["title"],
            "node_count": len(nodes),
            "edge_count": len(edges),
        },
    )


def decision_overrides(conn: Any) -> dict[str, dict[str, str | None]]:
    rows = conn.execute("SELECT id,status,reason FROM decision_overrides").fetchall()
    return {row["id"]: {"status": row["status"], "reason": row["reason"]} for row in rows}


def apply_decision_override(
    overrides: dict[str, dict[str, str | None]],
    decision_id: str,
    default_status: str,
    default_reason: str,
) -> tuple[str, str]:
    override = overrides.get(decision_id, {})
    status = override.get("status") or default_status
    reason = override.get("reason") or default_reason
    return status, reason


def insert_merged_node(
    conn: Any,
    merged_id: str,
    base: Any,
    source_books: list[str],
    frequency: int,
    method: str,
    confidence: float,
    metadata: dict[str, Any],
) -> None:
    conn.execute(
        """
        INSERT INTO nodes (
          id,textbook_id,name,definition,category,body_system,organ,anatomical_region,
          scale_level,stage,importance,frequency,evidence,chapter_id,chapter_title,
          source_textbooks,method,confidence,metadata
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            merged_id,
            None,
            base["name"],
            base["definition"],
            base["category"],
            base["body_system"],
            base["organ"],
            base["anatomical_region"],
            base["scale_level"],
            base["stage"],
            "high" if frequency > 1 or base["importance"] == "high" else base["importance"],
            frequency,
            base["evidence"],
            base["chapter_id"],
            base["chapter_title"],
            as_json(source_books),
            method,
            confidence,
            as_json(metadata),
        ),
    )


def ensure_merged_graph() -> dict[str, Any]:
    with db() as conn:
        raw_nodes = conn.execute("SELECT * FROM nodes WHERE textbook_id IS NOT NULL").fetchall()
        raw_edges = conn.execute("SELECT * FROM edges WHERE textbook_id IS NOT NULL").fetchall()
        overrides = decision_overrides(conn)
        conn.execute("DELETE FROM nodes WHERE textbook_id IS NULL")
        conn.execute("DELETE FROM edges WHERE textbook_id IS NULL")
        conn.execute("DELETE FROM integration_decisions")

        groups: dict[str, list[Any]] = defaultdict(list)
        for node in raw_nodes:
            normalized = normalize_name(node["name"])
            if not normalized or normalized in {"概述", "总论", "正文"}:
                normalized = f"{node['textbook_id']}_{node['id']}"
            groups[normalized].append(node)

        node_map: dict[str, str] = {}
        merged_nodes: list[str] = []
        source_chars = conn.execute("SELECT COALESCE(SUM(total_chars),0) FROM textbooks").fetchone()[0]
        total_chars = source_chars or sum(len(node["definition"] or "") + len(node["evidence"] or "") for node in raw_nodes)
        merged_chars = 0

        for normalized, nodes in groups.items():
            nodes_sorted = sorted(nodes, key=lambda row: (row["importance"] == "high", len(row["definition"] or "")), reverse=True)
            base = nodes_sorted[0]
            merged_id = stable_id("merged", normalized, prefix="merged_")
            source_books = sorted({book for row in nodes for book in from_json(row["source_textbooks"], [])})
            frequency = len(nodes)
            source_count = len(source_books) or frequency
            if frequency > 1 and source_count <= 1:
                for row in nodes_sorted:
                    preserved_id = stable_id("preserved", row["id"], prefix="merged_")
                    row_books = from_json(row["source_textbooks"], []) or [row["textbook_id"]]
                    insert_merged_node(
                        conn,
                        preserved_id,
                        row,
                        row_books,
                        1,
                        "same_textbook_duplicate_preserved",
                        row["confidence"],
                        {"normalized_name": normalized, "source_node_ids": [row["id"]]},
                    )
                    merged_chars += len(row["definition"] or "") + len(row["evidence"] or "")
                    merged_nodes.append(preserved_id)
                    node_map[row["id"]] = preserved_id
                continue
            if frequency > 1:
                decision_id = stable_id("merge", normalized, prefix="decision_")
                saved = sum(len(row["definition"] or "") + len(row["evidence"] or "") for row in nodes[1:])
                default_reason = f"{frequency} 个来源节点（覆盖 {source_count} 本教材）出现“{base['name']}”或近似标题，保留证据更完整的版本并合并来源。"
                status, reason = apply_decision_override(overrides, decision_id, "active", default_reason)
                if status == "rejected":
                    saved = 0
                    for row in nodes_sorted:
                        preserved_id = stable_id("preserved", row["id"], prefix="merged_")
                        row_books = from_json(row["source_textbooks"], []) or [row["textbook_id"]]
                        insert_merged_node(
                            conn,
                            preserved_id,
                            row,
                            row_books,
                            1,
                            "teacher_rejected_merge",
                            row["confidence"],
                            {
                                "normalized_name": normalized,
                                "source_node_ids": [row["id"]],
                                "rejected_decision_id": decision_id,
                            },
                        )
                        merged_chars += len(row["definition"] or "") + len(row["evidence"] or "")
                        merged_nodes.append(preserved_id)
                        node_map[row["id"]] = preserved_id
                    result_node = None
                else:
                    insert_merged_node(
                        conn,
                        merged_id,
                        base,
                        source_books,
                        frequency,
                        "merged_semantic_rule",
                        min(0.96, 0.72 + frequency * 0.05),
                        {"normalized_name": normalized, "source_node_ids": [row["id"] for row in nodes]},
                    )
                    merged_chars += len(base["definition"] or "") + len(base["evidence"] or "")
                    merged_nodes.append(merged_id)
                    for row in nodes:
                        node_map[row["id"]] = merged_id
                    result_node = merged_id
                conn.execute(
                    """
                    INSERT INTO integration_decisions (id,action,affected_nodes,result_node,reason,confidence,char_saved,status)
                    VALUES (?,?,?,?,?,?,?,?)
                    """,
                    (
                        decision_id,
                        "merge",
                        as_json([row["id"] for row in nodes]),
                        result_node,
                        reason,
                        min(0.95, 0.72 + frequency * 0.04),
                        saved,
                        status,
                    ),
                )
            else:
                insert_merged_node(
                    conn,
                    merged_id,
                    base,
                    source_books,
                    frequency,
                    "merged_semantic_rule",
                    min(0.96, 0.72 + frequency * 0.05),
                    {"normalized_name": normalized, "source_node_ids": [row["id"] for row in nodes]},
                )
                merged_chars += len(base["definition"] or "") + len(base["evidence"] or "")
                merged_nodes.append(merged_id)
                for row in nodes:
                    node_map[row["id"]] = merged_id

        edge_seen: set[tuple[str, str, str]] = set()
        for edge in raw_edges:
            source = node_map.get(edge["source"])
            target = node_map.get(edge["target"])
            if not source or not target or source == target:
                continue
            key = (source, target, edge["relation_type"])
            if key in edge_seen:
                continue
            edge_seen.add(key)
            conn.execute(
                """
                INSERT INTO edges (id,source,target,relation_type,medical_relation_type,description,confidence,evidence,textbook_id,chapter_title,method)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    stable_id(source, target, edge["relation_type"], prefix="medge_"),
                    source,
                    target,
                    edge["relation_type"],
                    edge["medical_relation_type"] or "",
                    edge["description"],
                    edge["confidence"],
                    edge["evidence"],
                    None,
                    edge["chapter_title"],
                    "merged_from_source_edges",
                ),
            )
        ratio = (merged_chars / total_chars) if total_chars else 0
        if ratio > 0.3:
            decision_id = stable_id("compress", "target", prefix="decision_")
            default_reason = f"当前规则整合后摘要字符比约 {ratio:.1%}，后续可通过 DeepSeek 重要性排序进一步压缩到 30%。"
            status, reason = apply_decision_override(overrides, decision_id, "active", default_reason)
            conn.execute(
                """
                INSERT INTO integration_decisions (id,action,affected_nodes,result_node,reason,confidence,char_saved,status)
                VALUES (?,?,?,?,?,?,?,?)
                """,
                (
                    decision_id,
                    "compress",
                    as_json([]),
                    None,
                    reason,
                    0.7,
                    max(total_chars - int(total_chars * 0.3), 0) if status != "rejected" else 0,
                    status,
                ),
            )
    return get_merged_graph()


def get_merged_graph(limit: int = 900) -> dict[str, Any]:
    with db() as conn:
        nodes = conn.execute(
            "SELECT * FROM nodes WHERE textbook_id IS NULL ORDER BY frequency DESC, importance DESC, name LIMIT ?",
            (limit,),
        ).fetchall()
        node_ids = [row["id"] for row in nodes]
        if node_ids:
            placeholders = ",".join("?" for _ in node_ids)
            edges = conn.execute(
                f"SELECT * FROM edges WHERE textbook_id IS NULL AND source IN ({placeholders}) AND target IN ({placeholders}) LIMIT ?",
                [*node_ids, *node_ids, limit * 2],
            ).fetchall()
        else:
            edges = []
        decisions = conn.execute("SELECT COUNT(*), COALESCE(SUM(char_saved),0) FROM integration_decisions").fetchone()
        textbook_count = conn.execute("SELECT COUNT(*) FROM textbooks").fetchone()[0]
    return _graph_from_rows(
        nodes,
        edges,
        {
            "textbook_count": textbook_count,
            "node_count": len(nodes),
            "edge_count": len(edges),
            "decision_count": decisions[0],
            "char_saved": decisions[1],
        },
    )


def integration_stats() -> dict[str, Any]:
    with db() as conn:
        raw_node_count = conn.execute("SELECT COUNT(*) FROM nodes WHERE textbook_id IS NOT NULL").fetchone()[0]
        merged_node_count = conn.execute("SELECT COUNT(*) FROM nodes WHERE textbook_id IS NULL").fetchone()[0]
        source_chars = conn.execute("SELECT COALESCE(SUM(total_chars),0) FROM textbooks").fetchone()[0]
        merged_chars = conn.execute(
            "SELECT COALESCE(SUM(LENGTH(definition)+LENGTH(evidence)),0) FROM nodes WHERE textbook_id IS NULL"
        ).fetchone()[0]
        decision_count = conn.execute("SELECT COUNT(*) FROM integration_decisions").fetchone()[0]
        char_saved = conn.execute("SELECT COALESCE(SUM(char_saved),0) FROM integration_decisions").fetchone()[0]
        chunks = conn.execute("SELECT COUNT(*) FROM rag_chunks").fetchone()[0]
    ratio = merged_chars / source_chars if source_chars else 0
    return {
        "source_chars": source_chars,
        "merged_chars": merged_chars,
        "compression_ratio": ratio,
        "target_ratio": 0.3,
        "target_met": ratio <= 0.3 if source_chars else False,
        "raw_node_count": raw_node_count,
        "merged_node_count": merged_node_count,
        "decision_count": decision_count,
        "char_saved": char_saved,
        "rag_chunks": chunks,
    }


def list_decisions() -> list[dict[str, Any]]:
    with db() as conn:
        rows = conn.execute("SELECT * FROM integration_decisions ORDER BY confidence DESC, created_at DESC").fetchall()
    return [row_to_dict(row) for row in rows if row_to_dict(row)]


def update_decision(decision_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    with db() as conn:
        row = conn.execute("SELECT * FROM integration_decisions WHERE id = ?", (decision_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Decision not found")
        status = payload.get("status") or row["status"]
        reason = payload["reason"] if "reason" in payload and payload["reason"] is not None else row["reason"]
        conn.execute(
            """
            INSERT INTO decision_overrides (id,status,reason,updated_at)
            VALUES (?,?,?,CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET
              status=excluded.status,
              reason=excluded.reason,
              updated_at=CURRENT_TIMESTAMP
            """,
            (decision_id, status, reason),
        )
    ensure_merged_graph()
    with db() as conn:
        updated = conn.execute("SELECT * FROM integration_decisions WHERE id = ?", (decision_id,)).fetchone()
    result = row_to_dict(updated)
    if result is None:
        raise HTTPException(status_code=404, detail="Decision no longer exists after refresh")
    result["graph_stats"] = integration_stats()
    return result


def reject_merge_decision_from_message(message: str) -> dict[str, Any] | None:
    decisions = [item for item in list_decisions() if item["action"] == "merge" and item["status"] == "active"]
    if not decisions:
        return None
    cjk_terms = [term for term in re.findall(r"[\u4e00-\u9fff]{2,12}", message) if term not in {"不要合并", "不应该合并"}]
    scored: list[tuple[int, dict[str, Any]]] = []
    for decision in decisions:
        reason = decision["reason"]
        score = sum(1 for term in cjk_terms if term in reason)
        scored.append((score, decision))
    scored.sort(key=lambda item: (item[0], item[1]["confidence"]), reverse=True)
    target = scored[0][1]
    reason = target["reason"]
    if "教师通过对话要求撤销" not in reason:
        reason = f"{reason} 教师通过对话要求撤销该合并，系统已恢复对应来源节点。"
    return update_decision(target["id"], {"status": "rejected", "reason": reason})


class DeepSeekClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    @property
    def ready(self) -> bool:
        return bool(self.settings.deepseek_ready and OpenAI)

    def status(self) -> dict[str, Any]:
        return {
            "configured": bool(self.settings.deepseek_ready),
            "client_available": bool(OpenAI),
            "model": self.settings.model_name,
            "base_url": self.settings.openai_base_url if self.settings.openai_base_url else None,
        }

    def verify_candidates(self, textbook_title: str, candidates: list[dict[str, Any]]) -> dict[str, Any]:
        """Ask DeepSeek to keep evidence-backed medical concepts and enrich graph labels."""
        if not self.ready:
            return {"used_llm": False, "nodes": candidates, "error": "DeepSeek is not configured"}
        prompt = {
            "textbook": textbook_title,
            "candidates": [
                {
                    "id": item["id"],
                    "name": item["name"],
                    "definition": item["definition"],
                    "evidence": item["evidence"][:220],
                }
                for item in candidates[:12]
            ],
        }
        client = OpenAI(api_key=self.settings.openai_api_key, base_url=self.settings.openai_base_url)
        response = client.chat.completions.create(
            model=self.settings.model_name,
            temperature=0.1,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是医学教材知识图谱构建专家。只返回严格 JSON，不要输出解释或 Markdown。"
                        "必须遵守防幻觉规则：definition、category、body_system、scale_level、stage 都只能根据 evidence 判断；"
                        "如果 evidence 不足以支持候选是医学知识点，keep=false；不要补写证据外的新事实。"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "请审核候选知识点，补全 category/body_system/scale_level/stage/importance。\n"
                        "输出格式 {\"nodes\":[{\"id\":\"...\",\"keep\":true,\"definition\":\"...\","
                        "\"category\":\"...\",\"body_system\":\"...\",\"scale_level\":\"...\","
                        "\"stage\":\"...\",\"importance\":\"high|medium|low\",\"reason\":\"...\"}]}。\n\n"
                        "Few-shot 示例：\n"
                        "输入：{\"textbook\":\"组织学与胚胎学\",\"candidates\":[{\"id\":\"n1\",\"name\":\"肺泡\","
                        "\"definition\":\"肺泡是肺进行气体交换的基本结构。\",\"evidence\":\"肺泡是肺进行气体交换的基本结构，由肺泡上皮和毛细血管共同参与气体交换。\"}]}\n"
                        "输出：{\"nodes\":[{\"id\":\"n1\",\"keep\":true,\"definition\":\"肺泡是肺进行气体交换的基本结构。\","
                        "\"category\":\"解剖结构\",\"body_system\":\"呼吸系统\",\"scale_level\":\"组织\","
                        "\"stage\":\"正常结构\",\"importance\":\"high\",\"reason\":\"evidence 明确给出定义和功能。\"}]}\n\n"
                        "反例：若 evidence 只是章节标题或无法支撑定义，输出 keep=false。\n\n"
                        "现在请处理：\n"
                        + json.dumps(prompt, ensure_ascii=False)
                    ),
                },
            ],
        )
        content = response.choices[0].message.content or "{}"
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            parsed = {"raw": content}
        return {"used_llm": True, "result": parsed}


async def extract_knowledge(textbook_id: str, use_llm: bool = True) -> dict[str, Any]:
    graph = build_textbook_graph(textbook_id)
    llm_result: dict[str, Any] = {"used_llm": False}
    if use_llm:
        textbook = get_textbook(textbook_id)
        client = DeepSeekClient()
        candidates = graph["nodes"][:12]
        try:
            llm_result = client.verify_candidates(textbook["title"], candidates)
        except Exception as exc:  # Keep the product usable even when provider rejects a call.
            llm_result = {"used_llm": False, "error": str(exc)}
    ensure_merged_graph()
    return {"status": "ready", "graph": graph, "llm": llm_result}


def build_rag_index(
    sync_dify: bool = True,
    sync_all: bool = True,
    limit: int | None = None,
    batch_size: int = 5000,
) -> dict[str, Any]:
    with db() as conn:
        conn.execute("DELETE FROM rag_chunks")
        textbooks = conn.execute("SELECT id,title FROM textbooks ORDER BY id").fetchall()
        count = 0
        for textbook in textbooks:
            chapters = conn.execute(
                "SELECT id,title,content FROM chapters WHERE textbook_id = ? ORDER BY sort_order",
                (textbook["id"],),
            ).fetchall()
            for chapter in chapters:
                prefix = f"[来源: 《{textbook['title']}》, {chapter['title']}]\n\n"
                for start, end, text in chunk_text(chapter["content"]):
                    chunk_id = stable_id(textbook["id"], chapter["id"], start, end, prefix="chunk_")
                    conn.execute(
                        """
                        INSERT INTO rag_chunks (id,textbook_id,chapter_id,text,char_start,char_end,metadata)
                        VALUES (?,?,?,?,?,?,?)
                        """,
                        (
                            chunk_id,
                            textbook["id"],
                            chapter["id"],
                            prefix + text,
                            start,
                            end,
                            as_json({"textbook": textbook["title"], "chapter": chapter["title"]}),
                        ),
                    )
                    count += 1
    settings = get_settings()
    dify_sync = {"status": "skipped", "reason": "Dify sync was not requested"}
    if sync_dify:
        if settings.dify_knowledge_ready:
            sync_limit = None if sync_all else limit or 80
            dify_sync = sync_chunks_to_dify(limit=sync_limit, batch_size=batch_size)
        else:
            dify_sync = {"status": "skipped", "reason": "Dify knowledge API is not configured"}
    return {
        "status": "indexed",
        "chunks": count,
        "dify_chat_configured": settings.dify_chat_ready,
        "dify_knowledge_configured": settings.dify_knowledge_ready,
        "dify_sync": dify_sync,
        "message": "本地 chunk 已生成；Dify 已配置时会按批次同步到知识库。",
    }


def dify_exception_message(exc: Exception) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        text = exc.response.text.strip()
        return f"{exc.response.status_code} {exc.response.reason_phrase}: {text[:500]}"
    return str(exc)


def sync_textbook_to_dify(textbook_id: str, batch_size: int = 5000) -> dict[str, Any]:
    with db() as conn:
        textbook = conn.execute("SELECT id,title FROM textbooks WHERE id = ?", (textbook_id,)).fetchone()
        if not textbook:
            raise HTTPException(status_code=404, detail="Textbook not found")
        rows = conn.execute(
            "SELECT * FROM rag_chunks WHERE textbook_id = ? ORDER BY chapter_id, char_start",
            (textbook_id,),
        ).fetchall()
    return sync_rows_to_dify(
        rows=rows,
        batch_size=batch_size,
        name_prefix=f"学科知识整合智能体-导入教材-{textbook['title']}",
    )


def sync_chunks_to_dify(limit: int | None = None, batch_size: int = 5000) -> dict[str, Any]:
    settings = get_settings()
    if not settings.dify_knowledge_ready:
        return {"status": "skipped", "reason": "Dify knowledge API is not configured"}
    with db() as conn:
        if limit is None:
            rows = conn.execute("SELECT * FROM rag_chunks ORDER BY textbook_id, chapter_id, char_start").fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM rag_chunks ORDER BY textbook_id, chapter_id, char_start LIMIT ?",
                (limit,),
            ).fetchall()
    return sync_rows_to_dify(rows=rows, batch_size=batch_size, name_prefix="学科知识整合智能体-教材全量")


def sync_rows_to_dify(rows: list[Any], batch_size: int = 5000, name_prefix: str = "学科知识整合智能体-教材分块") -> dict[str, Any]:
    settings = get_settings()
    if not settings.dify_knowledge_ready:
        return {"status": "skipped", "reason": "Dify knowledge API is not configured"}
    batch_size = min(max(batch_size, 1), 10000)
    if not rows:
        return {"status": "skipped", "reason": "No local chunks to sync"}
    batches = [rows[index : index + batch_size] for index in range(0, len(rows), batch_size)]
    synced: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    with httpx.Client(timeout=120) as client:
        for batch_index, batch in enumerate(batches, start=1):
            text = "\n\n---\n\n".join(row["text"] for row in batch)
            payload = {
                "name": f"{name_prefix}-{batch_index:03d}",
                "text": text,
                "indexing_technique": "high_quality",
                "process_rule": {"mode": "automatic"},
            }
            first_meta = from_json(batch[0]["metadata"], {})
            last_meta = from_json(batch[-1]["metadata"], {})
            batch_summary = {
                "batch": batch_index,
                "chunks": len(batch),
                "first": f"{first_meta.get('textbook', batch[0]['textbook_id'])}/{first_meta.get('chapter', batch[0]['chapter_id'])}",
                "last": f"{last_meta.get('textbook', batch[-1]['textbook_id'])}/{last_meta.get('chapter', batch[-1]['chapter_id'])}",
            }
            try:
                response = client.post(
                    f"{settings.dify_base_url}/datasets/{settings.dify_dataset_id}/document/create-by-text",
                    headers={"Authorization": f"Bearer {settings.dify_knowledge_api_key}"},
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                document = data.get("document", {}) if isinstance(data, dict) else {}
                synced.append(
                    {
                        **batch_summary,
                        "document_id": document.get("id"),
                        "indexing_status": document.get("indexing_status"),
                    }
                )
            except Exception as exc:
                failed.append({**batch_summary, "error": dify_exception_message(exc)})
    status = "synced" if not failed else "partial_failed" if synced else "failed"
    return {
        "status": status,
        "chunks_sent": sum(item["chunks"] for item in synced),
        "chunks_failed": sum(item["chunks"] for item in failed),
        "batches_total": len(batches),
        "batches_synced": len(synced),
        "batches_failed": len(failed),
        "documents": synced[:20],
        "errors": failed[:10],
    }


def rag_status() -> dict[str, Any]:
    settings = get_settings()
    with db() as conn:
        chunks = conn.execute("SELECT COUNT(*) FROM rag_chunks").fetchone()[0]
        books = conn.execute("SELECT COUNT(DISTINCT textbook_id) FROM rag_chunks").fetchone()[0]
    return {
        "chunks": chunks,
        "indexed_textbooks": books,
        "dify_chat_configured": settings.dify_chat_ready,
        "dify_knowledge_configured": settings.dify_knowledge_ready,
    }


def search_terms(question: str) -> list[str]:
    terms = [term for term in re.split(r"\s+|，|。|,|？|\?", question) if 2 <= len(term) <= 12]
    cjk = "".join(re.findall(r"[\u4e00-\u9fff]+", question))
    priority_terms = [term for term in ["肺炎", "低氧血症", "低氧", "血氧", "肺泡", "通气", "血流", "炎症", "机制"] if term in question]
    stop = {"什么", "如何", "为何", "为什么", "导致", "机制", "的是", "怎么", "请问"}
    for size in (2, 3, 4):
        for index in range(0, max(len(cjk) - size + 1, 0)):
            term = cjk[index : index + size]
            if term not in stop:
                terms.append(term)
    terms = list(dict.fromkeys(terms))[:80]
    if not terms and question:
        terms = [question[:8]]
    return [*priority_terms, *terms]


def bm25_tokens(text: str) -> list[str]:
    cjk = "".join(re.findall(r"[\u4e00-\u9fff]+", text))
    tokens = re.findall(r"[a-zA-Z0-9]{2,}", text.lower())
    for size in (2, 3):
        tokens.extend(cjk[index : index + size] for index in range(0, max(len(cjk) - size + 1, 0)))
    return tokens


def bm25_score_rows(question: str, rows: list[Any]) -> dict[str, float]:
    query_tokens = bm25_tokens(question)
    if not query_tokens or not rows:
        return {}
    documents = [bm25_tokens(f"{from_json(row['metadata'], {}).get('chapter', '')} {row['text']}") for row in rows]
    try:
        from rank_bm25 import BM25Okapi

        scores = BM25Okapi(documents).get_scores(query_tokens)
        return {row["id"]: float(score) for row, score in zip(rows, scores) if score > 0}
    except Exception:
        doc_freq: Counter[str] = Counter()
        for tokens in documents:
            doc_freq.update(set(tokens))
        avg_len = sum(len(tokens) for tokens in documents) / max(len(documents), 1)
        k1 = 1.5
        b = 0.75
        scores: dict[str, float] = {}
        for row, tokens in zip(rows, documents):
            counts = Counter(tokens)
            doc_len = len(tokens) or 1
            score = 0.0
            for token in query_tokens:
                freq = counts[token]
                if not freq:
                    continue
                idf = math.log(1 + (len(documents) - doc_freq[token] + 0.5) / (doc_freq[token] + 0.5))
                score += idf * (freq * (k1 + 1)) / (freq + k1 * (1 - b + b * doc_len / max(avg_len, 1)))
            if score > 0:
                scores[row["id"]] = score
        return scores


def citation_from_row(row: Any, score: float, method: str) -> dict[str, Any]:
    meta = from_json(row["metadata"], {})
    return {
        "textbook": meta.get("textbook", row["textbook_id"]),
        "chapter": meta.get("chapter", row["chapter_id"]),
        "relevance_score": min(0.99, 0.45 + score * 0.5),
        "retrieval_method": method,
        "chunk_preview": compact_evidence(row["text"], 220),
    }


def local_search_bm25(question: str, limit: int = 5) -> list[dict[str, Any]]:
    """Return BM25-ranked citations for the local RAG fallback path."""
    with db() as conn:
        rows = conn.execute("SELECT * FROM rag_chunks LIMIT 2500").fetchall()
    scores = bm25_score_rows(question, rows)
    by_id = {row["id"]: row for row in rows}
    max_score = max(scores.values(), default=1.0)
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)[:limit]
    return [citation_from_row(by_id[row_id], score / max_score, "bm25") for row_id, score in ranked]


def local_search(question: str, limit: int = 5) -> list[dict[str, Any]]:
    """Hybrid local retrieval: keyword evidence count + BM25 ranking over RAG chunks."""
    terms = search_terms(question)
    priority_terms = [term for term in ["肺炎", "低氧血症", "低氧", "血氧", "肺泡", "通气", "血流", "炎症", "机制"] if term in question]
    with db() as conn:
        rows = conn.execute("SELECT * FROM rag_chunks LIMIT 2500").fetchall()
    keyword_scores: dict[str, int] = {}
    for row in rows:
        meta = from_json(row["metadata"], {})
        scoped = f"{meta.get('chapter', '')} {row['text']}"
        score = sum(scoped.count(term) for term in terms)
        score += sum(scoped.count(term) * 12 for term in priority_terms)
        if score:
            keyword_scores[row["id"]] = score
    bm25_scores = bm25_score_rows(question, rows)
    max_keyword = max(keyword_scores.values(), default=1)
    max_bm25 = max(bm25_scores.values(), default=1.0)
    combined: list[tuple[float, Any, str]] = []
    for row in rows:
        keyword_score = keyword_scores.get(row["id"], 0) / max_keyword
        bm25_score = bm25_scores.get(row["id"], 0.0) / max_bm25
        score = keyword_score * 0.55 + bm25_score * 0.45
        if score:
            method = "keyword+bm25" if keyword_score and bm25_score else "keyword" if keyword_score else "bm25"
            combined.append((score, row, method))
    combined.sort(key=lambda item: item[0], reverse=True)
    return [citation_from_row(row, score, method) for score, row, method in combined[:limit]]


async def rag_query(question: str, conversation_id: str | None = None) -> dict[str, Any]:
    settings = get_settings()
    if settings.dify_chat_ready:
        payload: dict[str, Any] = {
            "inputs": {},
            "query": question,
            "response_mode": "blocking",
            "user": "teacher_001",
        }
        if conversation_id:
            payload["conversation_id"] = conversation_id
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(
                    f"{settings.dify_base_url}/chat-messages",
                    headers={"Authorization": f"Bearer {settings.dify_api_key}"},
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
            return {
                "answer": data.get("answer", ""),
                "citations": data.get("metadata", {}).get("retriever_resources", []),
                "conversation_id": data.get("conversation_id"),
                "provider": "dify",
            }
        except httpx.HTTPStatusError as exc:
            try:
                error_payload = exc.response.json()
            except Exception:
                error_payload = {"message": exc.response.text[:300]}
            citations = local_search(question)
            message = error_payload.get("message") or str(exc)
            answer = (
                f"Dify 已配置但调用失败：{message}。"
                "当前已回退到本地教材 chunk 检索。若要启用真实 Dify RAG，请在 Dify 控制台发布应用，"
                "并确认该 API Key 属于已发布的 Chatflow/Chat 应用。\n\n"
            )
            if citations:
                answer += "\n".join(
                    f"- 《{item['textbook']}》{item['chapter']}: {item['chunk_preview']}"
                    for item in citations[:3]
                )
            else:
                answer += "本地索引未找到明显匹配。"
            return {
                "answer": answer,
                "citations": citations,
                "conversation_id": conversation_id,
                "provider": "dify_error_fallback",
                "dify_error": {
                    "status_code": exc.response.status_code,
                    "code": error_payload.get("code"),
                    "message": message,
                },
            }
        except httpx.RequestError as exc:
            citations = local_search(question)
            return {
                "answer": f"Dify 网络请求失败：{exc}。当前已回退到本地教材 chunk 检索。",
                "citations": citations,
                "conversation_id": conversation_id,
                "provider": "dify_error_fallback",
                "dify_error": {"message": str(exc)},
            }

    citations = local_search(question)
    if citations:
        answer = "Dify 尚未配置，以下是本地教材 chunk 检索结果。配置 Dify 后将切换为真实 RAG 生成回答。\n\n"
        answer += "\n".join(f"- 《{item['textbook']}》{item['chapter']}: {item['chunk_preview']}" for item in citations[:3])
    else:
        answer = "Dify 尚未配置，且本地索引未找到明显匹配。请先建立索引或补充 Dify 凭证。"
    return {"answer": answer, "citations": citations, "conversation_id": conversation_id, "provider": "local_waiting_dify"}


async def chat_message(session_id: str, message: str) -> dict[str, Any]:
    with db() as conn:
        conn.execute("INSERT INTO chat_messages (session_id,role,content) VALUES (?,?,?)", (session_id, "user", message))
    normalized = message.strip()
    if any(word in normalized for word in ["为什么", "为何", "为啥"]) and "合并" in normalized:
        decisions = list_decisions()[:3]
        content = "当前主要合并理由：\n" + "\n".join(f"- {item['reason']}" for item in decisions) if decisions else "当前还没有合并决策。"
        result = {"answer": content, "citations": [], "conversation_id": session_id, "provider": "decision_intent"}
    elif any(word in normalized for word in ["分开", "不要合并", "不应该合并"]):
        updated = reject_merge_decision_from_message(normalized)
        if updated:
            content = f"已撤销一条合并决策并刷新整合图谱：{updated['reason']}"
        else:
            content = "已识别为撤销合并意图，但当前没有可撤销的 active 合并决策。"
        result = {"answer": content, "citations": [], "conversation_id": session_id, "provider": "decision_intent"}
    elif any(word in normalized for word in ["保留", "不要删", "恢复"]):
        content = "已识别为保留知识点意图。当前版本会记录反馈，并建议在整合决策列表中保留对应节点。"
        result = {"answer": content, "citations": [], "conversation_id": session_id, "provider": "decision_intent"}
    else:
        result = await rag_query(message, session_id)
    with db() as conn:
        conn.execute(
            "INSERT INTO chat_messages (session_id,role,content,citations) VALUES (?,?,?,?)",
            (session_id, "assistant", result["answer"], as_json(result.get("citations", []))),
        )
    return result


def chat_history(session_id: str) -> list[dict[str, Any]]:
    with db() as conn:
        rows = conn.execute(
            "SELECT role,content,citations,created_at FROM chat_messages WHERE session_id = ? ORDER BY id",
            (session_id,),
        ).fetchall()
    return [row_to_dict(row) for row in rows if row_to_dict(row)]


GAME_STAGES = [
    {
        "id": "level_1",
        "title": "病原体登场",
        "knowledgeNodeId": "sample_capsule",
        "isKeyLevel": True,
        "prerequisites": [],
        "questions": [
            {
                "id": "q1",
                "type": "multiple_choice",
                "difficulty": "easy",
                "question": "肺炎链球菌荚膜的主要致病作用是什么？",
                "options": ["产生外毒素", "抗吞噬", "长期体外存活", "穿透血脑屏障"],
                "correctAnswer": 1,
                "explanation": "荚膜阻止吞噬细胞清除，是重要毒力因子。",
                "xpReward": 10,
            }
        ],
    },
    {
        "id": "level_2",
        "title": "突破呼吸道防线",
        "knowledgeNodeId": "sample_bronchus",
        "isKeyLevel": True,
        "prerequisites": ["level_1"],
        "questions": [
            {
                "id": "q2",
                "type": "multiple_choice",
                "difficulty": "easy",
                "question": "吸入性病原体更容易进入哪侧主支气管？",
                "options": ["左侧", "右侧", "两侧相同", "取决于肺容量"],
                "correctAnswer": 1,
                "explanation": "右主支气管更粗、短、陡直。",
                "xpReward": 10,
            }
        ],
    },
    {
        "id": "level_3",
        "title": "肺泡气体交换告急",
        "knowledgeNodeId": "sample_vq",
        "isKeyLevel": True,
        "prerequisites": ["level_2"],
        "questions": [
            {
                "id": "q3",
                "type": "multiple_choice",
                "difficulty": "medium",
                "question": "炎症渗出物充满肺泡时，V/Q 比值通常如何变化？",
                "options": ["升高", "降低", "不变", "血流停止"],
                "correctAnswer": 1,
                "explanation": "通气下降而血流仍在，形成低 V/Q 和功能性分流。",
                "xpReward": 20,
            }
        ],
    },
]


def game_skill_tree() -> dict[str, Any]:
    return {
        "levels": GAME_STAGES,
        "playerProgress": {"currentXP": 0, "streak": 0, "completedLevels": [], "starsByLevel": {}},
    }


def game_level(level_id: str) -> dict[str, Any]:
    for level in GAME_STAGES:
        if level["id"] == level_id:
            return level
    raise HTTPException(status_code=404, detail="Level not found")


def generate_report() -> str:
    stats = integration_stats()
    textbooks = list_textbooks()
    decisions = list_decisions()[:12]
    status_labels = {"active": "已应用", "hidden": "已隐藏", "rejected": "已撤销"}
    lines = [
        "# 学科知识整合报告",
        "",
        "> 本报告由当前 7 本医学教材样例和运行时整合图谱生成，可作为评审交付物和课堂复核清单。",
        "",
        "## 数据概览",
        "",
        f"- 教材数量：{len(textbooks)}",
        f"- 原始字符数：{stats['source_chars']:,}",
        f"- 整合摘要字符数：{stats['merged_chars']:,}",
        f"- 当前压缩比：{stats['compression_ratio']:.2%}",
        f"- 图谱节点：{stats['raw_node_count']} → {stats['merged_node_count']}",
        f"- 整合决策：{stats['decision_count']} 条，累计节省字符约 {stats['char_saved']:,}",
        f"- RAG 分块：{stats['rag_chunks']:,} 个",
        "",
        "## 教材清单",
        "",
    ]
    for textbook in textbooks:
        lines.append(f"- 《{textbook['title']}》：{textbook['chapter_count']} 个章节节点")
    lines.extend(["", "## 主要整合决策", ""])
    if decisions:
        for decision in decisions:
            status = status_labels.get(decision["status"], decision["status"])
            lines.append(
                f"- [{status}] {decision['action']}：{decision['reason']}（置信度 {decision['confidence']:.2f}，节省 {decision['char_saved']:,} 字符）"
            )
    else:
        lines.append("- 当前暂无整合决策。")
    lines.extend(
        [
            "",
            "## 教学使用建议",
            "",
            "- 先用医学导航按器官系统筛选，再进入图谱查看跨教材来源。",
            "- 对高频节点优先生成课堂讲解材料，低置信度合并项由教师复核。",
            "- RAG 问答必须展示教材和章节引用，避免脱离教材自由发挥。",
            "",
            "## 已知局限与复核项",
            "",
            "- PDF/DOCX 转 Markdown 依赖原文件版式质量；扫描版或复杂表格需要 OCR/人工校对兜底。",
            "- 当前语义整合以章节标题、定义句和来源频次为主，医学同义词、缩写和跨层级关系仍需要教师复核。",
            "- Dify 未配置时系统使用本地 chunk 检索降级，能展示引用片段，但不等同于完整混合检索生成链路。",
            "- 30% 压缩目标按字符和节点规模估算，最终教学完整性需要结合课程大纲和课堂目标再次确认。",
            "- NotebookLM 和闯关游戏属于可选创新层；核心 P0 不依赖这些第三方或样例输出。",
        ]
    )
    report = "\n".join(lines)
    settings = get_settings()
    for path in [settings.output_dir / "整合报告.md", settings.root_dir / "report" / "整合报告.md"]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(report, encoding="utf-8")
    return report


def config_status() -> dict[str, Any]:
    settings = get_settings()
    return {
        "deepseek": DeepSeekClient(settings).status(),
        "dify": {
            "chat_configured": settings.dify_chat_ready,
            "knowledge_configured": settings.dify_knowledge_ready,
            "base_url_configured": bool(settings.dify_base_url),
            "dataset_configured": bool(settings.dify_dataset_id),
        },
        "database": {"path": str(settings.database_path), "exists": settings.database_path.exists()},
        "data": {
            "textbooks": len(list_textbooks()),
            "stats": integration_stats(),
        },
    }
