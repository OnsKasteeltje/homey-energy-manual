#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import re
import struct
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
HEADING_RE = re.compile(r'^(#{1,6})\s+(.+?)\s*$', re.M)

# Hard publication invariant: every process diagram occupies its own page and
# must fit fully inside the printable A4 portrait area.  Conservative limits
# reserve room for Word/LibreOffice page margins and avoid bottom clipping.
FLOW_MAX_WIDTH_CM = 15.5
FLOW_MAX_HEIGHT_CM = 19.0

# Raw OpenXML page break emitted by Pandoc when using markdown+raw_attribute.
PAGE_BREAK = '''```{=openxml}\n<w:p><w:r><w:br w:type="page"/></w:r></w:p>\n```'''


def png_size(path: Path) -> tuple[int, int]:
    with path.open('rb') as fh:
        sig = fh.read(24)
    if len(sig) < 24 or sig[:8] != b'\x89PNG\r\n\x1a\n' or sig[12:16] != b'IHDR':
        raise RuntimeError(f'Ongeldige PNG: {path}')
    width, height = struct.unpack('>II', sig[16:24])
    if width <= 0 or height <= 0:
        raise RuntimeError(f'Ongeldige PNG-afmetingen: {path}')
    return width, height


def fitted_dimensions_cm(path: Path) -> tuple[float, float]:
    width_px, height_px = png_size(path)
    ratio = width_px / height_px
    width_cm = FLOW_MAX_WIDTH_CM
    height_cm = width_cm / ratio
    if height_cm > FLOW_MAX_HEIGHT_CM:
        height_cm = FLOW_MAX_HEIGHT_CM
        width_cm = height_cm * ratio
    return round(width_cm, 2), round(height_cm, 2)


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

    width_cm, height_cm = fitted_dimensions_cm(png)
    image = (
        f'![Procesdiagram](diagrams/{png.name})'
        f'{{ width={width_cm}cm height={height_cm}cm }}'
    )
    # Page breaks on both sides make the diagram an isolated page object. The
    # exact proportional dimensions guarantee that it cannot extend below the
    # printable page area.
    return f'\n{PAGE_BREAK}\n\n{image}\n\n{PAGE_BREAK}\n'


def strip_heading_attributes(title: str) -> str:
    return re.sub(r'\s*\{[^}]*\}\s*$', '', title).strip()


def build_static_toc(text: str) -> str:
    entries: list[str] = []
    for hashes, raw_title in HEADING_RE.findall(text):
        level = len(hashes)
        if level < 2 or level > 4:
            continue
        title = strip_heading_attributes(raw_title)
        if not title or title.casefold() in {'inhoudsopgave', 'table of contents'}:
            continue
        indent = '  ' * (level - 2)
        entries.append(f'{indent}- {title}')
    if not entries:
        raise RuntimeError('Geen headings gevonden voor statische inhoudsopgave')
    return '# Inhoudsopgave {.unnumbered}\n\n' + '\n'.join(entries) + '\n\n' + PAGE_BREAK + '\n\n'


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
    body = ''.join(parts)

    if '```process-model' in body:
        raise RuntimeError('process-model bron is niet volledig verwijderd')
    if '```mermaid' in body:
        raise RuntimeError('Mermaid bron is niet volledig vervangen door afbeeldingen')
    if 'GENERATED_MERMAID:' in body:
        raise RuntimeError('generated markers zijn niet volledig verwijderd')

    publication = build_static_toc(body) + body
    OUT.write_text(publication, encoding='utf-8')
    print(
        f'PASS: publication Markdown -> {OUT}; diagrams={count}; '
        'toc=STATIC; invariant=ONE_FLOW_ONE_PAGE_HARD'
    )
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f'FAIL: {exc}', file=sys.stderr)
        raise SystemExit(1)
