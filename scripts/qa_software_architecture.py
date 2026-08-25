#!/usr/bin/env python3
"""QA the generated HEMS software architecture master document.

The checks are deliberately deterministic and dependency-free so the same gate
can run locally and in GitHub Actions.
"""
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

    # Markdown code fences must always be balanced; otherwise DOCX/PDF conversion
    # can silently absorb whole chapters into one code block.
    fences = len(re.findall(r"(?m)^```", text))
    if fences % 2:
        fail(f"ongebalanceerde Markdown code fences: {fences}")

    # Validate only module titles: the first H2 inside each assembled BEGIN/END
    # section. Repeated internal headings such as Doel, Inputs and Validatie are
    # intentional because component modules share a standard structure.
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
    duplicates = [name for name, count in Counter(module_titles).items() if count > 1]
    if duplicates:
        fail("dubbele moduletitels: " + ", ".join(sorted(duplicates)))

    # Mermaid blocks must contain a recognizable Mermaid diagram declaration.
    blocks = re.findall(r"```mermaid\s*\n(.*?)\n```", text, flags=re.S | re.I)
    for idx, block in enumerate(blocks, 1):
        first = next((line.strip() for line in block.splitlines() if line.strip()), "")
        if not re.match(r"^(flowchart|graph|sequenceDiagram|stateDiagram(?:-v2)?|classDiagram|erDiagram|journey|gantt|timeline)\b", first):
            fail(f"Mermaid blok {idx} heeft geen herkenbare diagramdeclaratie: {first!r}")

    folded = text.casefold()
    for label, terms in REQUIRED_STATUS_FACTS.items():
        if not all(term.casefold() in folded for term in terms):
            fail(f"status/RC contract ontbreekt: {label}")

    # No migration placeholders may survive in the finished master baseline.
    forbidden = ["TODO MIGRATE", "TBD MIGRATION"]
    hits = [term for term in forbidden if term.casefold() in folded]
    if hits:
        fail("onafgeronde migratieplaceholder(s): " + ", ".join(hits))

    print(
        f"PASS: master QA; sections={text.count('<!-- BEGIN ')}; "
        f"mermaid={len(blocks)}; modules={len(module_titles)}; fences={fences}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
