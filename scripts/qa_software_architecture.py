#!/usr/bin/env python3
"""QA the generated HEMS software architecture master document."""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "docs/software-architecture/generated/software-architecture.md"

REQUIRED_STATUS_FACTS = {
    "Victron remains non-integrated": ["NOT_INTEGRATED", "Victron"],
    "Power Intent remains shadow": ["Power Intent", "SHADOW"],
    "Opportunity is not a physical writer": ["Opportunity", "writer"],
    "WW shadow boundary documented": ["warm", "SHADOW"],
    "single-writer RC gate documented": ["single-writer"],
    "restart recovery RC gate documented": ["restart"],
    "idempotency RC gate documented": ["idempot"],
    "rollback RC gate documented": ["rollback"],
}


def fail(message: str) -> None:
    raise ValueError(message)


def main() -> int:
    if not MASTER.is_file():
        fail(f"master ontbreekt: {MASTER.relative_to(ROOT)}")
    text = MASTER.read_text(encoding="utf-8")

    if not text.startswith("<!-- GENERATED FILE: do not edit manually. -->"):
        fail("generated-file marker ontbreekt")
    if text.count("<!-- BEGIN ") != text.count("<!-- END "):
        fail("BEGIN/END section markers zijn niet in balans")
    if text.count("<!-- BEGIN ") < 20:
        fail("onverwacht weinig samengestelde secties")

    fences = len(re.findall(r"(?m)^```", text))
    if fences % 2:
        fail(f"ongebalanceerde Markdown code fences: {fences}")

    section_blocks = re.findall(
        r"<!-- BEGIN ([^>]+) -->\s*(.*?)\s*<!-- END \1 -->",
        text,
        flags=re.S,
    )
    module_titles: list[str] = []
    for rel, body in section_blocks:
        match = re.search(r"(?m)^##\s+(.+)$", body)
        if not match:
            fail(f"module heeft geen H2-titel na assembly: {rel.strip()}")
        module_titles.append(match.group(1).strip().casefold())

        # Every module must have exactly one H2: its module/chapter title.
        # Internal sections start at H3 and may nest deeper from there.
        h2s = re.findall(r"(?m)^##\s+(.+)$", body)
        if len(h2s) != 1:
            fail(f"module moet exact één H2-hoofdstuktitel hebben: {rel.strip()} ({len(h2s)} gevonden)")

    duplicates = [name for name, count in Counter(module_titles).items() if count > 1]
    if duplicates:
        fail("dubbele moduletitels: " + ", ".join(sorted(duplicates)))

    # Generated headings must never carry manual numbering. Pandoc owns all
    # visible chapter/paragraph numbering based solely on H2/H3/H4 hierarchy.
    manual_numbered_headings = re.findall(
        r"(?m)^#{2,6}\s+\d+(?:\.\d+)*[.)]?\s+.+$",
        text,
    )
    if manual_numbered_headings:
        fail("handmatige nummering in generated headings: " + " | ".join(manual_numbered_headings[:5]))

    # No heading may skip more than one level (e.g. H2 -> H4).
    in_fence = False
    previous_level: int | None = None
    for line in text.splitlines():
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = re.match(r"^(#{1,6})\s+", line)
        if not m:
            continue
        level = len(m.group(1))
        if previous_level is not None and level > previous_level + 1:
            fail(f"heading hierarchy slaat niveau over: H{previous_level} -> H{level}: {line}")
        previous_level = level

    blocks = re.findall(r"```mermaid\s*\n(.*?)\n```", text, flags=re.S | re.I)
    for idx, block in enumerate(blocks, 1):
        first = next((line.strip() for line in block.splitlines() if line.strip()), "")
        if not re.match(r"^(flowchart|graph|sequenceDiagram|stateDiagram(?:-v2)?|classDiagram|erDiagram|journey|gantt|timeline)\b", first):
            fail(f"Mermaid blok {idx} heeft geen herkenbare diagramdeclaratie: {first!r}")

    folded = text.casefold()
    for label, terms in REQUIRED_STATUS_FACTS.items():
        if not all(term.casefold() in folded for term in terms):
            fail(f"status/RC contract ontbreekt: {label}")

    forbidden = ["TODO MIGRATE", "TBD MIGRATION"]
    hits = [term for term in forbidden if term.casefold() in folded]
    if hits:
        fail("onafgeronde migratieplaceholder(s): " + ", ".join(hits))

    print(
        f"PASS: master QA; sections={text.count('<!-- BEGIN ')}; "
        f"mermaid={len(blocks)}; modules={len(module_titles)}; fences={fences}; "
        "numbering=HIERARCHICAL"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
