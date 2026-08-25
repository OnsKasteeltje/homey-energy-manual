#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / 'docs' / 'software-architecture' / 'generated' / 'software-architecture.md'
BUILD = ROOT / 'build'
OUT = BUILD / 'software-architecture-publication.md'
DIAGRAM_DIR = BUILD / 'diagrams'
PUPPETEER_CONFIG = ROOT / 'scripts' / 'mermaid-puppeteer-config.json'

PROCESS_MODEL_RE = re.compile(r'```process-model\s*\n.*?\n```\s*', re.S | re.I)
MERMAID_RE = re.compile(r'```mermaid\s*\n(.*?)\n```', re.S | re.I)
GENERATED_MARKER_RE = re.compile(r'<!--\s*GENERATED_MERMAID:[^>]+(?:START|END)\s*-->\s*', re.I)


def render_mermaid(source: str, index: int) -> str:
    DIAGRAM_DIR.mkdir(parents=True, exist_ok=True)
    mmd = DIAGRAM_DIR / f'diagram-{index:02d}.mmd'
    png = DIAGRAM_DIR / f'diagram-{index:02d}.png'
    mmd.write_text(source.strip() + '\n', encoding='utf-8')
    cmd = [
        'mmdc',
        '-p', str(PUPPETEER_CONFIG),
        '-i', str(mmd),
        '-o', str(png),
        '-b', 'white',
        '-w', '1600',
        '-s', '1',
    ]
    subprocess.run(cmd, check=True)
    if not png.exists() or png.stat().st_size == 0:
        raise RuntimeError(f'Mermaid render produced no PNG: {png}')
    return f'![Procesdiagram](diagrams/{png.name}){{ width=95% }}'


def main() -> int:
    if not MASTER.exists():
        raise FileNotFoundError(f'Master Markdown ontbreekt: {MASTER}')
    BUILD.mkdir(parents=True, exist_ok=True)
    if DIAGRAM_DIR.exists():
        for p in DIAGRAM_DIR.iterdir():
            if p.is_file():
                p.unlink()
    text = MASTER.read_text(encoding='utf-8')
    text = PROCESS_MODEL_RE.sub('', text)
    text = GENERATED_MARKER_RE.sub('', text)

    count = 0
    parts: list[str] = []
    pos = 0
    for match in MERMAID_RE.finditer(text):
        count += 1
        parts.append(text[pos:match.start()])
        parts.append(render_mermaid(match.group(1), count))
        pos = match.end()
    parts.append(text[pos:])
    publication = ''.join(parts)

    if '```process-model' in publication:
        raise RuntimeError('process-model bron is niet volledig verwijderd')
    if '```mermaid' in publication:
        raise RuntimeError('Mermaid bron is niet volledig vervangen door afbeeldingen')
    if 'GENERATED_MERMAID:' in publication:
        raise RuntimeError('generated markers zijn niet volledig verwijderd')

    OUT.write_text(publication, encoding='utf-8')
    print(f'PASS: publication Markdown -> {OUT}; diagrams={count}')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f'FAIL: {exc}', file=sys.stderr)
        raise SystemExit(1)
