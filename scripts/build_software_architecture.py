#!/usr/bin/env python3
"""Build the HEMS software architecture master Markdown from manifest.yaml.

Uses only the Python standard library and intentionally supports the small,
controlled manifest shape used by this repository.
"""
from __future__ import annotations

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
DOC_ROOT = ROOT / "docs" / "software-architecture"
MANIFEST = DOC_ROOT / "manifest.yaml"


def parse_manifest(text: str) -> tuple[str, str, list[str], dict[str, bool]]:
    title = "Software Architecture"
    output = "docs/software-architecture/generated/software-architecture.md"
    sections: list[str] = []
    rules: dict[str, bool] = {}
    mode: str | None = None

    for raw in text.splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not line.startswith(" ") and stripped.endswith(":"):
            mode = stripped[:-1]
            continue
        if not line.startswith(" ") and ":" in stripped:
            key, value = stripped.split(":", 1)
            if key == "title":
                title = value.strip()
            mode = None
            continue
        if mode == "output" and stripped.startswith("markdown:"):
            output = stripped.split(":", 1)[1].strip()
        elif mode == "sections" and stripped.startswith("- "):
            sections.append(stripped[2:].strip())
        elif mode == "rules" and ":" in stripped:
            key, value = stripped.split(":", 1)
            rules[key.strip()] = value.strip().lower() == "true"

    if not sections:
        raise ValueError("manifest bevat geen sections")
    return title, output, sections, rules


def split_frontmatter(text: str, path: Path) -> tuple[str, str]:
    if not text.startswith("---\n"):
        raise ValueError(f"{path}: YAML-frontmatter ontbreekt")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise ValueError(f"{path}: YAML-frontmatter is niet afgesloten")
    return text[4:end], text[end + 5 :].lstrip()


def validate_frontmatter(frontmatter: str, rel: str, rules: dict[str, bool]) -> None:
    def has_value(key: str) -> bool:
        return re.search(rf"(?m)^{re.escape(key)}\s*:\s*.+$", frontmatter) is not None

    if rules.get("require_last_verified", False) and not has_value("last_verified"):
        raise ValueError(f"{rel}: last_verified ontbreekt")

    if rules.get("require_source_paths", False) and rel.startswith(("components/", "architecture/")):
        has_sources = (
            re.search(r"(?m)^source\s*:\s*$", frontmatter)
            or re.search(r"(?m)^sources\s*:\s*$", frontmatter)
            or has_value("source")
            or has_value("sources")
        )
        if not has_sources:
            raise ValueError(f"{rel}: source/sources ontbreekt")


def demote_top_heading(body: str) -> str:
    # The generated file owns H1. Each module H1 becomes H2; lower headings
    # retain their relative hierarchy.
    lines = body.splitlines()
    for idx, line in enumerate(lines):
        if line.startswith("# "):
            lines[idx] = "## " + line[2:]
            break
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    title, output_rel, sections, rules = parse_manifest(MANIFEST.read_text(encoding="utf-8"))
    chunks = [
        "<!-- GENERATED FILE: do not edit manually. -->",
        "<!-- Source: docs/software-architecture/manifest.yaml -->",
        f"# {title}",
        "",
    ]

    for rel in sections:
        path = DOC_ROOT / rel
        if not path.is_file():
            raise FileNotFoundError(f"manifest section ontbreekt: {rel}")
        text = path.read_text(encoding="utf-8")
        if rules.get("require_frontmatter", False):
            frontmatter, body = split_frontmatter(text, path)
            validate_frontmatter(frontmatter, rel, rules)
        else:
            body = text
        chunks.extend(
            [f"<!-- BEGIN {rel} -->", demote_top_heading(body), f"<!-- END {rel} -->", ""]
        )

    output = ROOT / output_rel
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(chunks).rstrip() + "\n", encoding="utf-8")
    print(f"PASS: {len(sections)} sections -> {output.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
