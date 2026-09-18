#!/usr/bin/env python3
"""Build the clean-room Frontend V2 preview assets into the MkDocs docs tree."""
from pathlib import Path
import shutil
import re
ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'frontend'
OUT=ROOT/'docs'/'v2'
PAGES=('live',)
def main():
    for page in PAGES:
        src=SRC/page
        dst=OUT/page
        dst.mkdir(parents=True,exist_ok=True)
        for name in ('index.html',f'{page}.js',f'{page}.css'):
            source=src/name
            if not source.is_file(): raise FileNotFoundError(source)
            shutil.copy2(source,dst/name)
    # MkDocs copies docs/v2 into site/v2. Remove any stale generated source copy first.
if __name__=='__main__': main()
