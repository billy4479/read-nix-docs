from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence, TextIO

from .option_docs import (
    find_option,
    format_option_markdown,
    load_options,
    option_declaration,
    option_description_summary,
    search_options,
)


DEVELOPMENT_DOCS_ROOT = Path("../../src/nixpkgs/doc")
NIXPKGS_DOCS_ROOT = Path("@nixpkgs_doc@")
NIXOS_OPTIONS_FILE = Path("@nixos_options_json@")
HOME_MANAGER_OPTIONS_FILE = Path("@home_manager_options_json@")
DEFAULT_ENTRYPOINT = "manual.md.in"

INCLUDE_START_RE = re.compile(r"^```\{=include=}\s*(.*)\s*$")
FENCE_END_RE = re.compile(r"^```\s*$")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
ANCHOR_RE = re.compile(r"\s*\{#([^}\s]+)\}\s*$")
WORD_RE = re.compile(r"[\w.+-]+")
TEMPLATE_PLACEHOLDER_LINE_RE = re.compile(r"^\s*@[-\w]+@\s*$")
HTML_COMMENT_RE = re.compile(r"<!--.*?-->")


@dataclass(frozen=True)
class SourceLine:
    text: str
    path: Path
    line_number: int


@dataclass(frozen=True)
class Heading:
    title: str
    id: str
    level: int
    source_path: Path
    line_number: int
    start: int
    end: int
    ancestry: tuple[str, ...]


def default_docs_root() -> Path:
    if (NIXPKGS_DOCS_ROOT / DEFAULT_ENTRYPOINT).exists():
        return NIXPKGS_DOCS_ROOT
    return (Path.cwd() / DEVELOPMENT_DOCS_ROOT).resolve()


def load_manual(
    docs_root: Path, entrypoint: str = DEFAULT_ENTRYPOINT
) -> list[SourceLine]:
    root = docs_root.resolve()
    entry = (root / entrypoint).resolve()
    if not entry.exists():
        raise FileNotFoundError(f"manual entrypoint not found: {entry}")
    if root not in (entry, *entry.parents):
        raise ValueError(f"entrypoint is outside docs root: {entry}")
    return _load_markdown_file(entry, root, stack=())


def _load_markdown_file(
    path: Path, docs_root: Path, stack: tuple[Path, ...]
) -> list[SourceLine]:
    if path in stack:
        cycle = " -> ".join(str(item.relative_to(docs_root)) for item in (*stack, path))
        raise ValueError(f"recursive include cycle detected: {cycle}")
    if not path.exists():
        generated_source = path.with_suffix(f"{path.suffix}.in")
        if generated_source.exists():
            return _load_markdown_file(generated_source, docs_root, stack)
        relative = path.relative_to(docs_root) if docs_root in path.parents else path
        return [SourceLine(f"<!-- missing include: {relative} -->\n", path, 1)]

    raw_lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    result: list[SourceLine] = []
    index = 0
    while index < len(raw_lines):
        line = raw_lines[index]
        start_match = INCLUDE_START_RE.match(line.rstrip("\n"))
        if start_match is None:
            result.append(SourceLine(_substitute_known_tokens(line), path, index + 1))
            index += 1
            continue

        include_kind = (
            start_match.group(1).split()[0] if start_match.group(1).split() else ""
        )
        block_start = index + 1
        index += 1
        block_lines: list[tuple[int, str]] = []
        while (
            index < len(raw_lines)
            and FENCE_END_RE.match(raw_lines[index].rstrip("\n")) is None
        ):
            block_lines.append((index + 1, raw_lines[index]))
            index += 1

        if index >= len(raw_lines):
            result.append(
                SourceLine(
                    f"<!-- unterminated include block in {path.relative_to(docs_root)}:{block_start} -->\n",
                    path,
                    block_start,
                )
            )
            break

        index += 1
        result.extend(
            _expand_include_block(
                path, docs_root, include_kind, block_lines, (*stack, path), block_start
            )
        )
    return result


def _expand_include_block(
    current_path: Path,
    docs_root: Path,
    include_kind: str,
    block_lines: list[tuple[int, str]],
    stack: tuple[Path, ...],
    block_start: int,
) -> list[SourceLine]:
    if include_kind not in {"chapters", "parts", "sections", "appendix"}:
        rendered = [
            SourceLine(
                f"<!-- unsupported include block '{include_kind}' in {current_path.relative_to(docs_root)}:{block_start} -->\n",
                current_path,
                block_start,
            )
        ]
        rendered.extend(
            SourceLine(f"<!-- {line.rstrip()} -->\n", current_path, line_number)
            for line_number, line in block_lines
        )
        return rendered

    base_dir = current_path.parent
    expanded: list[SourceLine] = []
    for line_number, line in block_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" in stripped or "=" in stripped:
            continue
        include_path = (base_dir / stripped).resolve()
        if docs_root not in (include_path, *include_path.parents):
            expanded.append(
                SourceLine(
                    f"<!-- skipped include outside docs root: {stripped} -->\n",
                    current_path,
                    line_number,
                )
            )
            continue
        expanded.extend(_load_markdown_file(include_path, docs_root, stack))
    return expanded


def _substitute_known_tokens(line: str) -> str:
    return line.replace("@MANUAL_VERSION@", "unknown")


def parse_sections(lines: Sequence[SourceLine]) -> list[Heading]:
    starts: list[tuple[int, str, str, int, Path, int]] = []
    in_fence = False
    for index, source_line in enumerate(lines):
        stripped = source_line.text.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = HEADING_RE.match(source_line.text.rstrip("\n"))
        if match is None:
            continue
        level = len(match.group(1))
        raw_title = match.group(2).strip()
        title, explicit_id = _split_heading_anchor(raw_title)
        section_id = explicit_id or slugify(title)
        starts.append(
            (index, title, section_id, level, source_line.path, source_line.line_number)
        )

    sections: list[Heading] = []
    title_stack: list[tuple[int, str]] = []
    for position, (
        start,
        title,
        section_id,
        level,
        source_path,
        line_number,
    ) in enumerate(starts):
        end = len(lines)
        for (
            next_start,
            _next_title,
            _next_id,
            next_level,
            _next_path,
            _next_line,
        ) in starts[position + 1 :]:
            if next_level <= level:
                end = next_start
                break

        title_stack = [
            (stack_level, stack_title)
            for stack_level, stack_title in title_stack
            if stack_level < level
        ]
        ancestry = tuple(stack_title for _stack_level, stack_title in title_stack)
        sections.append(
            Heading(
                title, section_id, level, source_path, line_number, start, end, ancestry
            )
        )
        title_stack.append((level, title))
    return sections


def _split_heading_anchor(raw_title: str) -> tuple[str, str | None]:
    match = ANCHOR_RE.search(raw_title)
    if match is None:
        return raw_title.strip(), None
    return raw_title[: match.start()].strip(), match.group(1)


def slugify(title: str) -> str:
    words = WORD_RE.findall(title.lower())
    return "-".join(word.strip("._") for word in words if word.strip("._")) or "section"


def search_sections(
    sections: Sequence[Heading], lines: Sequence[SourceLine], query: str, limit: int
) -> list[tuple[int, Heading]]:
    terms = [term.lower() for term in WORD_RE.findall(query)]
    if not terms:
        return []
    scored: list[tuple[int, Heading]] = []
    joined_query = " ".join(terms)
    compact_query = compact_text(joined_query)
    for position, section in enumerate(sections):
        local_end = (
            sections[position + 1].start
            if position + 1 < len(sections)
            else section.end
        )
        section_text = "".join(
            line.text for line in lines[section.start : local_end]
        ).lower()
        title = section.title.lower()
        section_id = section.id.lower()
        path = " ".join((*section.ancestry, section.title)).lower()
        compact_title = compact_text(title)
        compact_id = compact_text(section_id)
        compact_path = compact_text(path)
        score = 0
        if section_id == joined_query or title == joined_query:
            score += 200
        if compact_query and compact_query in {compact_id, compact_title}:
            score += 120
        if joined_query in section_id:
            score += 80
        if joined_query in title:
            score += 70
        if joined_query in path:
            score += 50
        if compact_query and compact_query in compact_path:
            score += 40
        for term in terms:
            compact_term = compact_text(term)
            if term in section_id:
                score += 30
            if term in title:
                score += 25
            if compact_term and compact_term in compact_id:
                score += 20
            if compact_term and compact_term in compact_title:
                score += 20
            if term in path:
                score += 10
            score += min(section_text.count(term), 20)
        if score > 0:
            scored.append((score, section))
    scored.sort(
        key=lambda item: (-item[0], item[1].source_path.as_posix(), item[1].line_number)
    )
    return scored[:limit]


def compact_text(text: str) -> str:
    return "".join(WORD_RE.findall(text.lower()))


def find_section(sections: Sequence[Heading], selector: str) -> Heading | None:
    lowered = selector.lower()
    for section in sections:
        if section.id == selector:
            return section
    for section in sections:
        if section.id.lower() == lowered or section.title.lower() == lowered:
            return section
    return None


def relative_source(section: Heading, docs_root: Path) -> str:
    try:
        path = section.source_path.relative_to(docs_root)
    except ValueError:
        path = section.source_path
    return f"{path}:{section.line_number}"


def section_path(section: Heading) -> str:
    return " > ".join((*section.ancestry, section.title))


def format_index_line(section: Heading, include_title: bool) -> str:
    prefix = f"{'#' * section.level}\t{section.id}"
    if include_title:
        return f"{prefix}\t{section.title}"
    return prefix


def clean_markdown(lines: Sequence[SourceLine]) -> str:
    cleaned: list[str] = []
    in_fence = False
    in_comment = False
    blank_lines = 0
    for source_line in lines:
        line = source_line.text
        stripped = line.strip()

        if stripped.startswith("```"):
            in_fence = not in_fence
            cleaned.append(line)
            blank_lines = 0
            continue

        if in_fence:
            cleaned.append(line)
            continue

        if in_comment:
            if "-->" in line:
                in_comment = False
            continue

        if TEMPLATE_PLACEHOLDER_LINE_RE.match(line):
            continue

        if stripped.startswith("<!--"):
            if "-->" not in line:
                in_comment = True
            continue

        line = HTML_COMMENT_RE.sub("", line)
        if line.strip():
            cleaned.append(line)
            blank_lines = 0
        elif source_line.text.strip() == "":
            if blank_lines == 0:
                cleaned.append(line)
            blank_lines += 1

    return "".join(cleaned)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Search and read Nix documentation offline."
    )
    corpora = parser.add_subparsers(dest="corpus", required=True)

    manual = corpora.add_parser(
        "nixpkgs-manual", help="search the Nixpkgs Markdown manual"
    )
    manual_commands = manual.add_subparsers(dest="command", required=True)

    search = manual_commands.add_parser("search", help="search manual sections")
    search.add_argument("query", nargs="+", help="search terms")
    search.add_argument(
        "--limit", type=int, default=20, help="maximum number of results"
    )

    get = manual_commands.add_parser(
        "get", help="print markdown for a section id or exact title"
    )
    get.add_argument("section", help="section id or exact heading title")

    index = manual_commands.add_parser("index", help="list all section ids")
    index.add_argument(
        "section",
        nargs="?",
        help="optional section id or exact title whose subsections should be listed",
    )
    index.add_argument("--titles", action="store_true", help="include section titles")

    _add_option_corpus_parser(
        corpora,
        "nixos-options",
        "search NixOS configuration options",
        NIXOS_OPTIONS_FILE,
    )
    _add_option_corpus_parser(
        corpora,
        "home-manager-docs",
        "search Home Manager configuration options",
        HOME_MANAGER_OPTIONS_FILE,
    )
    return parser


def _add_option_corpus_parser(
    corpora: argparse._SubParsersAction[argparse.ArgumentParser],
    name: str,
    help_text: str,
    default_file: Path,
) -> None:
    corpus = corpora.add_parser(name, help=help_text)
    corpus.add_argument(
        "--options-file",
        type=Path,
        default=default_file,
        help=f"path to generated options.json (default: {default_file})",
    )
    commands = corpus.add_subparsers(dest="command", required=True)

    search = commands.add_parser("search", help="search options")
    search.add_argument("query", nargs="+", help="search terms")
    search.add_argument(
        "--limit", type=int, default=20, help="maximum number of results"
    )

    get = commands.add_parser("get", help="print an option as Markdown")
    get.add_argument("option", help="exact option name")


def run(
    argv: Sequence[str] | None = None,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    if args.corpus != "nixpkgs-manual":
        return _run_option_command(args, stdout, stderr)

    docs_root = default_docs_root().resolve()
    try:
        lines = load_manual(docs_root)
    except (FileNotFoundError, ValueError, OSError) as error:
        print(f"error: {error}", file=stderr)
        return 2
    sections = parse_sections(lines)

    if args.command == "index":
        indexed_sections = sections
        if args.section is not None:
            parent = find_section(sections, args.section)
            if parent is None:
                print(f"error: section not found: {args.section}", file=stderr)
                return 1
            indexed_sections = [
                section
                for section in sections
                if section.start > parent.start and section.end <= parent.end
            ]

        for section in indexed_sections:
            print(format_index_line(section, args.titles), file=stdout)
        return 0

    if args.command == "search":
        query = " ".join(args.query)
        results = search_sections(sections, lines, query, max(args.limit, 0))
        if not results:
            print(f"No sections matched: {query}", file=stdout)
            return 0

        for index, (score, section) in enumerate(results, start=1):
            if index > 1:
                print(file=stdout)
            print(f"{index}. {section.title}", file=stdout)
            print(f"   id:     {section.id}", file=stdout)
            print(f"   source: {relative_source(section, docs_root)}", file=stdout)
            print(f"   path:   {section_path(section)}", file=stdout)
            print(f"   score:  {score}", file=stdout)
        return 0

    if args.command == "get":
        section = find_section(sections, args.section)
        if section is None:
            print(f"error: section not found: {args.section}", file=stderr)
            return 1
        stdout.write(clean_markdown(lines[section.start : section.end]))
        return 0

    parser.error(f"unknown command: {args.command}")
    return 2


def _run_option_command(
    args: argparse.Namespace, stdout: TextIO, stderr: TextIO
) -> int:
    options_file = args.options_file.resolve()
    try:
        options = load_options(options_file)
    except (FileNotFoundError, ValueError, OSError) as error:
        print(f"error: {error}", file=stderr)
        return 2

    if args.command == "search":
        query = " ".join(args.query)
        results = search_options(options, query, max(args.limit, 0))
        if not results:
            print(f"No options matched: {query}", file=stdout)
            return 0

        for index, (score, option) in enumerate(results, start=1):
            if index > 1:
                print(file=stdout)
            print(f"{index}. {option.name}", file=stdout)
            print(f"   type:        {option.option_type or 'unspecified'}", file=stdout)
            summary = option_description_summary(option)
            if summary:
                print(f"   description: {summary}", file=stdout)
            declaration = option_declaration(option)
            if declaration:
                print(f"   declared by: {declaration}", file=stdout)
            print(f"   score:       {score}", file=stdout)
        return 0

    if args.command == "get":
        option = find_option(options, args.option)
        if option is None:
            print(f"error: option not found: {args.option}", file=stderr)
            return 1
        stdout.write(format_option_markdown(option))
        return 0

    raise ValueError(f"unknown option command: {args.command}")


def main() -> None:
    try:
        raise SystemExit(run())
    except BrokenPipeError:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
        raise SystemExit(0)
