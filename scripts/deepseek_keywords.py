from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from openai import OpenAI

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.config import get_settings
from backend.database import db
from backend.text_processing import compact_evidence, extract_definition_candidates


MAX_DIGEST_CHARS = 18_000
PER_BOOK_KEYWORDS = 30
GLOBAL_KEYWORDS = 60


def strip_json(content: str) -> dict[str, Any]:
    text = content.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.S)
    if fenced:
        text = fenced.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start : end + 1])
        raise


def load_textbooks(include_user: bool = False) -> list[dict[str, str]]:
    with db() as conn:
        rows = conn.execute("SELECT id,title FROM textbooks ORDER BY id").fetchall()
    textbooks = [dict(row) for row in rows]
    if not include_user:
        textbooks = [item for item in textbooks if not item["id"].startswith("user_")]
    return textbooks


def load_chapters(textbook_id: str) -> list[dict[str, Any]]:
    with db() as conn:
        rows = conn.execute(
            """
            SELECT id,title,content
            FROM chapters
            WHERE textbook_id = ?
            ORDER BY sort_order,id
            """,
            (textbook_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def build_textbook_digest(textbook: dict[str, str], chapters: list[dict[str, Any]]) -> str:
    lines = [f"教材：{textbook['title']}（{textbook['id']}）", f"章节数：{len(chapters)}", ""]
    for index, chapter in enumerate(chapters, start=1):
        content = chapter["content"] or ""
        candidates = extract_definition_candidates(chapter["title"], content, limit=2)
        candidate_text = "；".join(
            f"{item['name']}：{compact_evidence(item['definition'], 72)}" for item in candidates
        )
        if not candidate_text:
            candidate_text = compact_evidence(content, 96)
        lines.append(f"{index}. {chapter['title']} | 线索：{candidate_text}")
        if sum(len(line) + 1 for line in lines) >= MAX_DIGEST_CHARS:
            lines.append("（后续章节因上下文长度限制已省略，请基于已给章节线索做保守整理。）")
            break
    return "\n".join(lines)


def chat_json(client: OpenAI, model: str, messages: list[dict[str, str]], max_tokens: int) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "model": model,
        "temperature": 0.1,
        "max_tokens": max_tokens,
        "messages": messages,
        "response_format": {"type": "json_object"},
    }
    try:
        response = client.chat.completions.create(**kwargs)
    except Exception as exc:
        if "response_format" not in str(exc):
            raise
        kwargs.pop("response_format", None)
        response = client.chat.completions.create(**kwargs)
    content = response.choices[0].message.content or "{}"
    try:
        return strip_json(content)
    except json.JSONDecodeError:
        repair_messages = [
            {
                "role": "system",
                "content": "你只负责修复 JSON。只返回合法 JSON 对象，不要输出解释或 Markdown。",
            },
            {
                "role": "user",
                "content": (
                    "下面内容不是合法 JSON。请尽量保留已出现字段，修复为合法 JSON。"
                    "如果末尾被截断，可以删掉不完整条目。\n\n"
                    + content[:20_000]
                ),
            },
        ]
        repair_kwargs: dict[str, Any] = {
            "model": model,
            "temperature": 0,
            "max_tokens": max_tokens,
            "messages": repair_messages,
            "response_format": {"type": "json_object"},
        }
        try:
            repaired = client.chat.completions.create(**repair_kwargs)
        except Exception as exc:
            if "response_format" not in str(exc):
                raise
            repair_kwargs.pop("response_format", None)
            repaired = client.chat.completions.create(**repair_kwargs)
        return strip_json(repaired.choices[0].message.content or "{}")


def extract_book_keywords(client: OpenAI, model: str, textbook: dict[str, str], chapters: list[dict[str, Any]]) -> dict[str, Any]:
    digest = build_textbook_digest(textbook, chapters)
    system = (
        "你是医学教材知识图谱关键词整理专家。只返回严格 JSON，不要输出 Markdown。"
        "必须基于输入的教材、章节标题和线索整理关键词，不要编造输入外的新章节或证据。"
    )
    user = f"""
请为这本医学教材梳理核心关键词。

要求：
1. 输出约 {PER_BOOK_KEYWORDS} 个关键词，覆盖 high/medium/low 三档重要性。
2. 关键词应适合知识图谱节点、RAG 检索和教学目录导航。
3. 合并同义或近义表达，把别名放入 aliases。
4. category 从以下集合中选择：解剖结构、生理机制、病理过程、病原体、疾病、诊断治疗、药物治疗、免疫机制、细胞分子、基础概念、教学章节。
5. body_system 无法判断时写“全身/通用”。
6. chapter_refs 最多 3 个，使用输入中的章节标题。
7. evidence_hint 用输入线索中的短语，不要写长段落。

返回 JSON Schema：
{{
  "textbook_id": "{textbook['id']}",
  "textbook_title": "{textbook['title']}",
  "keywords": [
    {{
      "keyword": "关键词",
      "aliases": ["别名"],
      "category": "分类",
      "body_system": "系统",
      "importance": "high|medium|low",
      "chapter_refs": ["章节标题"],
      "evidence_hint": "输入中的证据短语",
      "reason": "一句话说明为什么保留"
    }}
  ],
  "themes": ["跨章节主题"]
}}

输入：
{digest}
""".strip()
    result = chat_json(
        client,
        model,
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        max_tokens=6500,
    )
    result.setdefault("textbook_id", textbook["id"])
    result.setdefault("textbook_title", textbook["title"])
    return result


def consolidate_keywords(client: OpenAI, model: str, per_book: list[dict[str, Any]]) -> dict[str, Any]:
    compact_books = []
    for book in per_book:
        compact_books.append(
            {
                "textbook_id": book.get("textbook_id"),
                "textbook_title": book.get("textbook_title"),
                "themes": book.get("themes", []),
                "keywords": [
                    {
                        "keyword": item.get("keyword"),
                        "aliases": item.get("aliases", []),
                        "category": item.get("category"),
                        "body_system": item.get("body_system"),
                        "importance": item.get("importance"),
                        "chapter_refs": item.get("chapter_refs", [])[:2],
                    }
                    for item in book.get("keywords", [])
                ],
            }
        )
    system = "你是医学课程整合专家。只返回严格 JSON，不要输出 Markdown。"
    user = f"""
下面是 DeepSeek 已按教材整理出的关键词。请做全局去重、归并和课程级关键词梳理。

要求：
1. 输出约 {GLOBAL_KEYWORDS} 个 global_keywords。
2. 将同义词、缩写、上下位近义词合并到 aliases，不要重复列出。
3. 统计出现教材 source_textbooks。
4. importance 以跨教材覆盖、教学核心度、检索价值综合判断。
5. clusters 给出 8-12 个跨学科主题簇，每簇 5-10 个关键词。

返回 JSON Schema：
{{
  "global_keywords": [
    {{
      "keyword": "关键词",
      "aliases": ["别名"],
      "category": "分类",
      "body_system": "系统",
      "importance": "high|medium|low",
      "source_textbooks": ["教材名"],
      "reason": "一句话说明"
    }}
  ],
  "clusters": [
    {{
      "name": "主题簇",
      "keywords": ["关键词"],
      "source_textbooks": ["教材名"],
      "teaching_value": "教学价值"
    }}
  ]
}}

输入：
{json.dumps(compact_books, ensure_ascii=False)}
""".strip()
    return chat_json(
        client,
        model,
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        max_tokens=7500,
    )


def fallback_consolidate_keywords(per_book: list[dict[str, Any]], limit: int = GLOBAL_KEYWORDS) -> dict[str, Any]:
    merged: dict[str, dict[str, Any]] = {}
    importance_weight = {"high": 3, "medium": 2, "low": 1}
    for book in per_book:
        title = book.get("textbook_title", "")
        for item in book.get("keywords", []):
            keyword = item.get("keyword")
            if not keyword:
                continue
            key = re.sub(r"[^\w\u4e00-\u9fff]+", "", keyword.lower())
            if not key:
                continue
            current = merged.setdefault(
                key,
                {
                    "keyword": keyword,
                    "aliases": [],
                    "category": item.get("category", ""),
                    "body_system": item.get("body_system", ""),
                    "importance": item.get("importance", "medium"),
                    "source_textbooks": [],
                    "reason": "由分教材 DeepSeek 关键词去重合并。",
                    "_score": 0,
                },
            )
            current["_score"] += importance_weight.get(item.get("importance", "medium"), 2)
            for alias in item.get("aliases", []):
                if alias and alias not in current["aliases"]:
                    current["aliases"].append(alias)
            if title and title not in current["source_textbooks"]:
                current["source_textbooks"].append(title)
            if importance_weight.get(item.get("importance", "medium"), 2) > importance_weight.get(current["importance"], 2):
                current["importance"] = item.get("importance", "medium")
                current["category"] = item.get("category", current["category"])
                current["body_system"] = item.get("body_system", current["body_system"])
    ranked = sorted(merged.values(), key=lambda item: (len(item["source_textbooks"]), item["_score"]), reverse=True)
    global_keywords = []
    for item in ranked[:limit]:
        clean = {key: value for key, value in item.items() if key != "_score"}
        global_keywords.append(clean)
    clusters: list[dict[str, Any]] = []
    by_system: dict[str, list[dict[str, Any]]] = {}
    for item in global_keywords:
        by_system.setdefault(item.get("body_system") or "全身/通用", []).append(item)
    for system, items in sorted(by_system.items(), key=lambda pair: len(pair[1]), reverse=True)[:10]:
        clusters.append(
            {
                "name": system,
                "keywords": [item["keyword"] for item in items[:10]],
                "source_textbooks": sorted({book for item in items for book in item.get("source_textbooks", [])}),
                "teaching_value": "按系统串联跨教材概念，支持图谱导航和检索入口。",
            }
        )
    return {"global_keywords": global_keywords, "clusters": clusters}


def markdown_report(payload: dict[str, Any]) -> str:
    lines = [
        "# DeepSeek 关键词梳理",
        "",
        f"- 生成时间：{payload['generated_at']}",
        f"- 模型：{payload['model']}",
        f"- 教材范围：{', '.join(book['textbook_title'] for book in payload['per_textbook'])}",
        "",
        "## 全局核心关键词",
        "",
        "| 关键词 | 重要性 | 分类 | 系统 | 来源教材 | 说明 |",
        "|---|---|---|---|---|---|",
    ]
    for item in payload.get("global", {}).get("global_keywords", []):
        lines.append(
            "| {keyword} | {importance} | {category} | {body_system} | {sources} | {reason} |".format(
                keyword=item.get("keyword", ""),
                importance=item.get("importance", ""),
                category=item.get("category", ""),
                body_system=item.get("body_system", ""),
                sources="、".join(item.get("source_textbooks", [])),
                reason=(item.get("reason") or "").replace("|", "／"),
            )
        )
    lines.extend(["", "## 跨学科主题簇", ""])
    for cluster in payload.get("global", {}).get("clusters", []):
        lines.extend(
            [
                f"### {cluster.get('name', '')}",
                "",
                f"- 关键词：{'、'.join(cluster.get('keywords', []))}",
                f"- 来源教材：{'、'.join(cluster.get('source_textbooks', []))}",
                f"- 教学价值：{cluster.get('teaching_value', '')}",
                "",
            ]
        )
    lines.extend(["## 分教材关键词", ""])
    for book in payload["per_textbook"]:
        lines.extend(
            [
                f"### {book.get('textbook_title', '')}",
                "",
                f"- 主题：{'、'.join(book.get('themes', []))}",
                "",
                "| 关键词 | 重要性 | 分类 | 系统 | 章节 | 证据线索 |",
                "|---|---|---|---|---|---|",
            ]
        )
        for item in book.get("keywords", []):
            lines.append(
                "| {keyword} | {importance} | {category} | {body_system} | {chapters} | {evidence} |".format(
                    keyword=item.get("keyword", ""),
                    importance=item.get("importance", ""),
                    category=item.get("category", ""),
                    body_system=item.get("body_system", ""),
                    chapters="、".join(item.get("chapter_refs", [])),
                    evidence=(item.get("evidence_hint") or "").replace("|", "／"),
                )
            )
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Use DeepSeek to summarize textbook keywords.")
    parser.add_argument("--include-user", action="store_true", help="include uploaded user_* duplicate textbooks")
    parser.add_argument("--force", action="store_true", help="ignore cached per-textbook keyword results")
    args = parser.parse_args()

    settings = get_settings()
    if not settings.deepseek_ready:
        raise SystemExit("DeepSeek is not configured: OPENAI_API_KEY, OPENAI_BASE_URL, MODEL_NAME are required.")

    client = OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)
    textbooks = load_textbooks(include_user=args.include_user)
    output_dir = settings.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = output_dir / "deepseek_keyword_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    per_textbook: list[dict[str, Any]] = []
    for textbook in textbooks:
        chapters = load_chapters(textbook["id"])
        cache_path = cache_dir / f"{textbook['id']}.json"
        if cache_path.exists() and not args.force:
            print(f"Using cached {textbook['title']} ({len(chapters)} chapters)...", flush=True)
            per_textbook.append(json.loads(cache_path.read_text(encoding="utf-8")))
            continue
        print(f"Extracting {textbook['title']} ({len(chapters)} chapters)...", flush=True)
        result = extract_book_keywords(client, settings.model_name, textbook, chapters)
        cache_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        per_textbook.append(result)

    print("Consolidating global keywords...", flush=True)
    global_result = consolidate_keywords(client, settings.model_name, per_textbook)
    if not global_result.get("global_keywords"):
        global_result = fallback_consolidate_keywords(per_textbook)
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "model": settings.model_name,
        "base_url": settings.openai_base_url,
        "per_textbook": per_textbook,
        "global": global_result,
    }

    json_path = output_dir / "deepseek_keywords.json"
    md_path = output_dir / "deepseek_keywords.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(markdown_report(payload), encoding="utf-8")
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
