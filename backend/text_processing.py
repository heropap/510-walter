from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Iterable


FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)
TITLE_RE = re.compile(r"^title:\s*(.+?)\s*$", re.M)
HEADING_RE = re.compile(r"^#\s+(.+?)\s*$", re.M)
OBSIDIAN_LINK_RE = re.compile(r"\[\[(?:[^|\]]+\|)?([^\]]+)\]\]")


def stable_id(*parts: object, prefix: str = "") -> str:
    raw = "|".join(str(part) for part in parts)
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}{digest}" if prefix else digest


def clean_title(text: str) -> str:
    text = text.strip().strip('"').strip("'")
    text = OBSIDIAN_LINK_RE.sub(r"\1", text)
    text = re.sub(r"^\d+[_\s-]+", "", text)
    text = re.sub(r"^(第[一二三四五六七八九十百千万两\d]+[章节])\s*", "", text)
    text = re.sub(r"^[一二三四五六七八九十]+、\s*", "", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_name(text: str) -> str:
    text = clean_title(text).lower()
    text = re.sub(r"[（(].*?[）)]", "", text)
    text = re.sub(r"[^\w\u4e00-\u9fff]+", "", text)
    return text


def parse_markdown_note(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    frontmatter = ""
    body = text
    matched = FRONTMATTER_RE.match(text)
    if matched:
        frontmatter = matched.group(1)
        body = text[matched.end() :]

    title = ""
    title_match = TITLE_RE.search(frontmatter)
    if title_match:
        title = title_match.group(1).strip().strip('"')
    if not title:
        heading = HEADING_RE.search(body)
        title = heading.group(1).strip() if heading else path.stem

    content = body
    if "## 正文" in body:
        content = body.split("## 正文", 1)[1]
    content = re.sub(r"^上级：.*$", "", content, flags=re.M)
    content = re.sub(r"^## 下级[\s\S]*?(?=^## |\Z)", "", content, flags=re.M)
    content = re.sub(r"\n{3,}", "\n\n", content).strip()
    return {"title": clean_title(title), "content": content}


def compact_evidence(text: str, limit: int = 180) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit("。", 1)[0]
    return (cut or text[:limit]).strip(" ，,。") + "..."


def definition_from_content(title: str, content: str) -> str:
    if not content:
        return f"{title} 是教材中的核心知识点。"
    escaped = re.escape(title[:12])
    patterns = [
        rf"([^。；;]{{0,30}}{escaped}[^。；;]{{0,120}}(?:是|指|称为|定义为)[^。；;]{{0,160}}[。；;])",
        r"([^。；;]{2,40}(?:是|指|称为|定义为)[^。；;]{10,160}[。；;])",
        r"([^。；;]{10,180}[。；;])",
    ]
    for pattern in patterns:
        match = re.search(pattern, content)
        if match:
            return compact_evidence(match.group(1), 140)
    return compact_evidence(content, 140)


def chunk_text(text: str, chunk_size: int = 700, overlap: int = 100) -> Iterable[tuple[int, int, str]]:
    if not text:
        return
    step = max(chunk_size - overlap, 1)
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end].strip()
        if chunk:
            yield start, end, chunk
        if end >= len(text):
            break
        start += step

