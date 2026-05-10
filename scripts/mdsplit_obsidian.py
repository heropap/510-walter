#!/usr/bin/env python3
"""Split Markdown/textbook-style Markdown into an Obsidian-friendly tree."""

from __future__ import annotations

import argparse
import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path


CHINESE_NUM = "零〇一二三四五六七八九十百千万两"
FULLWIDTH_DIGITS = "０１２３４５６７８９"
FULLWIDTH_TRANS = str.maketrans(FULLWIDTH_DIGITS, "0123456789")
MARKER_NUM = rf"[{CHINESE_NUM}0-9{FULLWIDTH_DIGITS}]+"
CHAPTER_RE = re.compile(rf"^\s*\f*\s*(第\s*{MARKER_NUM}\s*章)(?:[\s\u3000\u2002\u2003\u2004|｜:：]+(.*)|\s*)$")
SECTION_RE = re.compile(rf"^\s*\f*\s*(第\s*{MARKER_NUM}\s*节)(?:[\s\u3000\u2002\u2003\u2004|｜:：]+(.*)|\s*)$")
ARTICLE_RE = re.compile(rf"^\s*([{CHINESE_NUM}]{{1,3}})、\s*(.+?)\s*$")
MARKDOWN_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
DOT_LEADER_RE = re.compile(r"(\s|\.|·|…){4,}\s*\d+\s*$")
PAGE_NUMBER_RE = re.compile(r"^\s*\d+\s*$")
INDD_RE = re.compile(r"^\s*[\w-]+\.indd\b")
TIME_RE = re.compile(r"^\s*\d{4}/\d{1,2}/\d{1,2}\s+\d{1,2}:\d{2}:\d{2}\s*$")


@dataclass
class Section:
    title: str
    level: int
    marker: str = ""
    body: list[str] = field(default_factory=list)
    children: list["Section"] = field(default_factory=list)
    file_path: Path | None = None
    link: str = ""


def compact_cjk_spaces(text: str) -> str:
    text = text.replace("\u3000", " ")
    text = text.replace("\u2002", " ").replace("\u2003", " ").replace("\u2004", " ")
    text = text.replace("\xa0", " ").replace("\t", " ")
    text = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_marker(text: str) -> str:
    return compact_cjk_spaces(text).translate(FULLWIDTH_TRANS).replace(" ", "")


def clean_title_tail(text: str) -> str:
    text = text.replace("\f", " ")
    text = text.replace("｜", "|").replace(":", " ").replace("：", " ")
    text = re.sub(r"^[\s|]+", "", text)
    text = DOT_LEADER_RE.sub("", text)
    text = re.sub(r"\s+\d+\s*$", "", text)
    text = text.strip(" \t|.。")
    return compact_cjk_spaces(text)


def title_from_marker(marker: str, tail: str, lines: list[str], index: int) -> tuple[str, int]:
    title = clean_title_tail(tail)
    consumed = 0
    if not title:
        for offset in range(1, 4):
            if index + offset >= len(lines):
                break
            candidate = clean_title_tail(lines[index + offset])
            if not candidate or PAGE_NUMBER_RE.match(candidate):
                continue
            if CHAPTER_RE.match(lines[index + offset]) or SECTION_RE.match(lines[index + offset]):
                break
            if len(candidate) <= 40:
                title = candidate
                consumed = offset
            break
    if title:
        return f"{marker} {title}", consumed
    return marker, consumed


def match_chapter(lines: list[str], index: int) -> tuple[str, str, int] | None:
    raw = lines[index]
    m = CHAPTER_RE.match(raw)
    if not m:
        return None
    marker = normalize_marker(m.group(1))
    title, consumed = title_from_marker(marker, m.group(2) or "", lines, index)
    if len(title) > 70:
        return None
    return marker, title, consumed


def match_section(lines: list[str], index: int) -> tuple[str, str, int] | None:
    raw = lines[index]
    m = SECTION_RE.match(raw)
    if not m:
        return None
    marker = normalize_marker(m.group(1))
    title, consumed = title_from_marker(marker, m.group(2) or "", lines, index)
    if len(title) > 70:
        return None
    return marker, title, consumed


def match_article(line: str) -> tuple[str, str] | None:
    matched = ARTICLE_RE.match(line.replace("\f", ""))
    if not matched:
        return None
    marker = f"{matched.group(1)}、"
    title = clean_title_tail(matched.group(2))
    if not title or len(title) > 60 or DOT_LEADER_RE.search(line):
        return None
    return marker, f"{marker} {title}"


def find_textbook_start(lines: list[str]) -> int:
    toc_index = next((i for i, line in enumerate(lines) if "目录" in line), -1)
    search_start = max(toc_index + 1, 0)

    for i in range(search_start, len(lines)):
        matched = match_chapter(lines, i)
        if matched and matched[0] in {"第一章", "第1章"} and "\f" in lines[i]:
            return i

    for i in range(search_start, len(lines)):
        matched = match_chapter(lines, i)
        if not matched:
            continue
        raw = lines[i]
        if DOT_LEADER_RE.search(raw):
            continue
        lookahead = "\n".join(lines[i + 1 : i + 8])
        if "第一节" in lookahead or "本章数字资源" in lookahead:
            return i
    return 0


def chapter_has_section(lines: list[str], start: int, chapter_marker: str) -> bool:
    for index in range(start, len(lines)):
        chapter_match = match_chapter(lines, index)
        if chapter_match and chapter_match[0] != chapter_marker:
            return False
        if match_section(lines, index):
            return True
    return False


def clean_body_lines(lines: list[str], current_chapter: Section | None) -> list[str]:
    cleaned: list[str] = []
    chapter_marker = current_chapter.marker if current_chapter else ""
    chapter_title = current_chapter.title if current_chapter else ""

    for line in lines:
        if "\f" in line:
            before, _, after = line.partition("\f")
            after_match = CHAPTER_RE.match(after.strip())
            if after_match and after_match.group(1) == chapter_marker:
                line = before
            else:
                line = line.replace("\f", "")

        stripped = compact_cjk_spaces(line)
        if not stripped:
            cleaned.append("")
            continue
        if PAGE_NUMBER_RE.match(stripped) or INDD_RE.match(stripped) or TIME_RE.match(stripped):
            continue
        if chapter_marker and stripped in {chapter_marker, chapter_title}:
            continue
        cleaned.append(line.rstrip())

    compacted: list[str] = []
    blank_count = 0
    for line in cleaned:
        if line.strip():
            blank_count = 0
            compacted.append(line.rstrip())
        else:
            blank_count += 1
            if blank_count <= 1:
                compacted.append("")
    while compacted and not compacted[0].strip():
        compacted.pop(0)
    while compacted and not compacted[-1].strip():
        compacted.pop()
    return compacted


def parse_textbook_markdown(path: Path, max_level: int) -> Section:
    lines = path.read_text(encoding="utf-8", errors="ignore").split("\n")
    root = Section(path.stem, 0)
    index = find_textbook_start(lines)
    current_chapter: Section | None = None
    current_section: Section | None = None
    current_chapter_has_sections = False

    while index < len(lines):
        chapter_match = match_chapter(lines, index)
        if chapter_match:
            marker, title, consumed = chapter_match
            if current_chapter and marker == current_chapter.marker:
                index += consumed + 1
                continue
            chapter = Section(title=title, level=1, marker=marker)
            root.children.append(chapter)
            current_chapter = chapter
            current_section = None
            current_chapter_has_sections = chapter_has_section(lines, index + consumed + 1, marker)
            index += consumed + 1
            continue

        section_match = match_section(lines, index)
        if section_match and current_chapter and max_level >= 2:
            marker, title, consumed = section_match
            section = Section(title=title, level=2, marker=marker)
            current_chapter.children.append(section)
            current_section = section
            index += consumed + 1
            continue

        article_match = match_article(lines[index])
        if article_match and current_chapter and max_level >= 2 and not current_chapter_has_sections:
            uses_article_children = (
                not current_chapter.children or current_chapter.children[0].marker.endswith("、")
            )
            if uses_article_children:
                marker, title = article_match
                section = Section(title=title, level=2, marker=marker)
                current_chapter.children.append(section)
                current_section = section
                index += 1
                continue

        line = lines[index]
        if current_section:
            current_section.body.append(line)
        elif current_chapter:
            current_chapter.body.append(line)
        index += 1

    for chapter in root.children:
        chapter.body = clean_body_lines(chapter.body, chapter)
        for section in chapter.children:
            section.body = clean_body_lines(section.body, chapter)
    return root


def parse_standard_markdown(path: Path, max_level: int) -> Section:
    lines = path.read_text(encoding="utf-8", errors="ignore").split("\n")
    root = Section(path.stem, 0)
    stack: list[Section] = [root]

    for line in lines:
        matched = MARKDOWN_HEADING_RE.match(line)
        if matched and len(matched.group(1)) <= max_level:
            level = len(matched.group(1))
            title = matched.group(2).strip()
            while stack and stack[-1].level >= level:
                stack.pop()
            node = Section(title=title, level=level)
            stack[-1].children.append(node)
            stack.append(node)
        else:
            stack[-1].body.append(line)
    return root


def parse_markdown(path: Path, mode: str, max_level: int) -> tuple[Section, str]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    has_markdown_headings = bool(MARKDOWN_HEADING_RE.search(text))
    if mode == "markdown" or (mode == "auto" and has_markdown_headings):
        return parse_standard_markdown(path, max_level), "markdown"
    return parse_textbook_markdown(path, max_level), "textbook"


def safe_name(text: str, fallback: str = "untitled") -> str:
    text = compact_cjk_spaces(text)
    text = re.sub(r'[\\/:*?"<>|#\[\]\^\n\r]+', "_", text)
    text = re.sub(r"\s+", "_", text)
    text = text.strip("._ ")
    return (text or fallback)[:90]


def unique_name(stem: str, used: set[str]) -> str:
    candidate = stem
    number = 2
    while candidate in used:
        candidate = f"{stem}_{number}"
        number += 1
    used.add(candidate)
    return candidate


def vault_relative(path: Path) -> Path:
    try:
        return path.resolve().relative_to(Path.cwd().resolve())
    except ValueError:
        return path


def assign_paths(root: Section, target_dir: Path) -> None:
    link_base = vault_relative(target_dir)

    def walk(parent: Section, rel_dir: Path) -> None:
        used: set[str] = set()
        for index, child in enumerate(parent.children, start=1):
            stem = unique_name(f"{index:02d}_{safe_name(child.title)}", used)
            if child.children:
                child.file_path = target_dir / rel_dir / stem / "index.md"
                child.link = str((link_base / rel_dir / stem / "index").as_posix())
                walk(child, rel_dir / stem)
            else:
                child.file_path = target_dir / rel_dir / f"{stem}.md"
                child.link = str((link_base / rel_dir / stem).as_posix())

    root.file_path = target_dir / "00_总目录.md"
    root.link = str((link_base / "00_总目录").as_posix())
    walk(root, Path(""))


def yaml_quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def obsidian_link(node: Section, label: str | None = None) -> str:
    return f"[[{node.link}|{label or node.title}]]"


def render_toc(nodes: list[Section], depth: int = 0) -> list[str]:
    lines: list[str] = []
    indent = "  " * depth
    for node in nodes:
        lines.append(f"{indent}- {obsidian_link(node)}")
        lines.extend(render_toc(node.children, depth + 1))
    return lines


def iter_nodes(root: Section) -> list[Section]:
    nodes: list[Section] = []

    def walk(node: Section) -> None:
        for child in node.children:
            nodes.append(child)
            walk(child)

    walk(root)
    return nodes


def write_root_index(root: Section, source: Path, parse_mode: str) -> None:
    assert root.file_path is not None
    root.file_path.parent.mkdir(parents=True, exist_ok=True)
    node_count = len(iter_nodes(root))
    content = [
        "---",
        f"title: {yaml_quote(root.title)}",
        f"source: {yaml_quote(str(source))}",
        f"parse_mode: {yaml_quote(parse_mode)}",
        f"nodes: {node_count}",
        "generated_by: mdsplit_obsidian.py",
        "---",
        "",
        f"# {root.title}",
        "",
        f"来源：`{source}`",
        f"拆分节点数：{node_count}",
        "",
        "## 目录",
        "",
    ]
    toc = render_toc(root.children)
    content.extend(toc if toc else ["- 未识别到章节"])
    content.append("")
    root.file_path.write_text("\n".join(content), encoding="utf-8")


def write_section_file(node: Section, root: Section, source: Path, parent: Section) -> None:
    assert node.file_path is not None
    node.file_path.parent.mkdir(parents=True, exist_ok=True)
    children_links = [obsidian_link(child) for child in node.children]
    parent_link = obsidian_link(parent, parent.title)
    content = [
        "---",
        f"title: {yaml_quote(node.title)}",
        f"source: {yaml_quote(str(source))}",
        f"level: {node.level}",
        f"parent: {yaml_quote(parent_link)}",
    ]
    if children_links:
        content.append("children:")
        content.extend(f"  - {yaml_quote(link)}" for link in children_links)
    else:
        content.append("children: []")
    content.extend(["---", "", f"# {node.title}", "", f"上级：{parent_link}", ""])

    if node.children:
        content.extend(["## 下级", ""])
        content.extend(f"- {link}" for link in children_links)
        content.append("")

    body = "\n".join(node.body).strip()
    if body:
        content.extend(["## 正文", "", body, ""])

    node.file_path.write_text("\n".join(content), encoding="utf-8")


def write_tree(root: Section, source: Path, target_dir: Path, parse_mode: str) -> None:
    assign_paths(root, target_dir)
    write_root_index(root, source, parse_mode)

    def walk(parent: Section) -> None:
        for child in parent.children:
            write_section_file(child, root, source, parent)
            walk(child)

    walk(root)


def choose_target(base_out: Path, source: Path, force: bool) -> Path:
    base_out.mkdir(parents=True, exist_ok=True)
    stem = safe_name(source.stem)
    target = base_out / stem
    if force and target.exists():
        shutil.rmtree(target)
    if not target.exists():
        return target
    number = 2
    while True:
        candidate = base_out / f"{stem}_{number}"
        if not candidate.exists():
            return candidate
        number += 1


def split_one(source: Path, out_dir: Path, mode: str, max_level: int, force: bool) -> Path:
    root, parse_mode = parse_markdown(source, mode, max_level)
    target = choose_target(out_dir, source, force)
    write_tree(root, source, target, parse_mode)
    return target


def read_nodes_count(index_path: Path) -> str:
    if not index_path.exists():
        return "?"
    for line in index_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.startswith("nodes:"):
            return line.split(":", 1)[1].strip()
    return "?"


def write_collection_index(out_dir: Path, outputs: list[Path]) -> None:
    if len(outputs) <= 1:
        return
    out_dir.mkdir(parents=True, exist_ok=True)
    index_path = out_dir / "00_总目录.md"
    lines = [
        "---",
        'title: "拆分结果"',
        f"books: {len(outputs)}",
        "generated_by: mdsplit_obsidian.py",
        "---",
        "",
        "# 拆分结果",
        "",
        "## 教材目录",
        "",
    ]
    for output in outputs:
        link = str((vault_relative(output) / "00_总目录").as_posix())
        nodes = read_nodes_count(output / "00_总目录.md")
        lines.append(f"- [[{link}|{output.name}]]（{nodes} 个节点）")
    lines.append("")
    index_path.write_text("\n".join(lines), encoding="utf-8")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Split Markdown into Obsidian notes by headings or Chinese textbook chapters."
    )
    parser.add_argument("inputs", nargs="+", type=Path, help="Markdown files to split.")
    parser.add_argument("--out", type=Path, default=Path("拆分结果"), help="Output directory.")
    parser.add_argument(
        "--mode",
        choices=["auto", "markdown", "textbook"],
        default="auto",
        help="Parser mode. auto uses # headings when present, otherwise textbook chapter detection.",
    )
    parser.add_argument("--max-level", type=int, default=2, help="Maximum heading level to split.")
    parser.add_argument("--force", action="store_true", help="Replace an existing output folder for each input.")
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    outputs: list[Path] = []
    for source in args.inputs:
        if not source.exists():
            raise FileNotFoundError(source)
        outputs.append(split_one(source, args.out, args.mode, args.max_level, args.force))

    print("拆分完成：")
    for output in outputs:
        print(f"- {output / '00_总目录.md'}")
    write_collection_index(args.out, outputs)
    if len(outputs) > 1:
        print(f"- {args.out / '00_总目录.md'}")


if __name__ == "__main__":
    main()
