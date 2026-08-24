from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


WORD_RE = re.compile(r"[\w.+-]+")


@dataclass(frozen=True)
class OptionDocument:
    name: str
    data: Mapping[str, Any]

    @property
    def description(self) -> str:
        value = self.data.get("description")
        return value if isinstance(value, str) else ""

    @property
    def option_type(self) -> str:
        value = self.data.get("type")
        return value if isinstance(value, str) else ""


def load_options(path: Path) -> list[OptionDocument]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid options JSON in {path}: {error}") from error

    if not isinstance(raw, dict):
        raise ValueError(f"options JSON must contain an object: {path}")

    options: list[OptionDocument] = []
    for name, data in raw.items():
        if not isinstance(name, str) or not isinstance(data, dict):
            raise ValueError(f"invalid option record in {path}: {name!r}")
        options.append(OptionDocument(name, data))
    options.sort(key=lambda option: option.name.lower())
    return options


def search_options(
    options: Sequence[OptionDocument], query: str, limit: int
) -> list[tuple[int, OptionDocument]]:
    terms = [term.lower() for term in WORD_RE.findall(query)]
    if not terms:
        return []

    joined_query = " ".join(terms)
    compact_query = _compact_text(joined_query)
    scored: list[tuple[int, OptionDocument]] = []
    for option in options:
        name = option.name.lower()
        compact_name = _compact_text(name)
        description = option.description.lower()
        option_type = option.option_type.lower()
        searchable_text = f"{name} {description} {option_type}"
        score = 0

        if name == joined_query:
            score += 300
        if compact_query and compact_name == compact_query:
            score += 180
        if name.startswith(joined_query):
            score += 120
        elif joined_query in name:
            score += 90
        if compact_query and compact_query in compact_name:
            score += 60
        if all(term in searchable_text for term in terms):
            score += 100
        if all(term in name for term in terms):
            score += 100

        for term in terms:
            compact_term = _compact_text(term)
            if term in name:
                score += 40
            if compact_term and compact_term in compact_name:
                score += 25
            score += min(description.count(term), 10) * 2
            score += min(option_type.count(term), 3)

        if score > 0:
            scored.append((score, option))

    scored.sort(key=lambda item: (-item[0], item[1].name.lower()))
    return scored[:limit]


def find_option(
    options: Sequence[OptionDocument], selector: str
) -> OptionDocument | None:
    for option in options:
        if option.name == selector:
            return option
    lowered = selector.lower()
    for option in options:
        if option.name.lower() == lowered:
            return option
    return None


def option_description_summary(option: OptionDocument, limit: int = 160) -> str:
    summary = " ".join(option.description.split())
    if len(summary) <= limit:
        return summary
    return f"{summary[: limit - 3].rstrip()}..."


def option_declaration(option: OptionDocument) -> str:
    declarations = option.data.get("declarations")
    if not isinstance(declarations, list) or not declarations:
        return ""
    declaration = declarations[0]
    if isinstance(declaration, str):
        return declaration
    if isinstance(declaration, dict):
        name = declaration.get("name")
        return name if isinstance(name, str) else ""
    return ""


def format_option_markdown(option: OptionDocument) -> str:
    parts = [f"# `{option.name}`\n"]
    if option.description:
        parts.append(f"{option.description.strip()}\n")

    option_type = option.option_type or "unspecified"
    if option.data.get("readOnly") is True:
        option_type = f"{option_type} (read only)"
    parts.append(f"**Type:** {option_type}\n")

    for key, title in (("default", "Default"), ("example", "Example")):
        if key in option.data:
            parts.append(f"**{title}:**\n\n{_format_value(option.data[key])}\n")

    related_packages = option.data.get("relatedPackages")
    if isinstance(related_packages, str) and related_packages.strip():
        parts.append(f"**Related packages:**\n\n{related_packages.strip()}\n")

    declarations = option.data.get("declarations")
    if isinstance(declarations, list) and declarations:
        rendered = [
            item for item in (_format_declaration(d) for d in declarations) if item
        ]
        if rendered:
            parts.append("**Declared by:**\n\n" + "\n".join(rendered) + "\n")

    return "\n".join(parts).rstrip() + "\n"


def _compact_text(text: str) -> str:
    return "".join(WORD_RE.findall(text.lower()))


def _format_value(value: Any) -> str:
    if isinstance(value, dict) and isinstance(value.get("_type"), str):
        text = value.get("text")
        if isinstance(text, str):
            if value["_type"] == "literalMD":
                return text.strip()
            if value["_type"] == "literalExpression":
                return f"```nix\n{text.rstrip()}\n```"
    return f"```json\n{json.dumps(value, ensure_ascii=False, indent=2)}\n```"


def _format_declaration(declaration: Any) -> str:
    if isinstance(declaration, str):
        return f"- `{declaration}`"
    if not isinstance(declaration, dict):
        return ""
    name = declaration.get("name")
    url = declaration.get("url")
    if not isinstance(name, str):
        return ""
    if isinstance(url, str):
        return f"- [`{name}`]({url})"
    return f"- `{name}`"
