#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import time
from pathlib import Path

import uno
from com.sun.star.beans import PropertyValue


def prop(name: str, value):
    p = PropertyValue()
    p.Name = name
    p.Value = value
    return p


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('docx', type=Path)
    ap.add_argument('--port', type=int, default=2002)
    args = ap.parse_args()

    docx = args.docx.resolve()
    if not docx.exists():
        raise FileNotFoundError(docx)

    profile = Path('/tmp/lo-toc-profile')
    profile.mkdir(parents=True, exist_ok=True)
    accept = f'--accept=socket,host=127.0.0.1,port={args.port};urp;StarOffice.ComponentContext'
    proc = subprocess.Popen([
        'libreoffice',
        f'-env:UserInstallation=file://{profile}',
        '--headless', '--nologo', '--nodefault', '--nofirststartwizard',
        accept,
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    try:
        local_ctx = uno.getComponentContext()
        resolver = local_ctx.ServiceManager.createInstanceWithContext(
            'com.sun.star.bridge.UnoUrlResolver', local_ctx
        )
        ctx = None
        for _ in range(50):
            try:
                ctx = resolver.resolve(
                    f'uno:socket,host=127.0.0.1,port={args.port};urp;StarOffice.ComponentContext'
                )
                break
            except Exception:
                time.sleep(0.2)
        if ctx is None:
            raise RuntimeError('Could not connect to LibreOffice UNO listener')

        smgr = ctx.ServiceManager
        desktop = smgr.createInstanceWithContext('com.sun.star.frame.Desktop', ctx)
        url = uno.systemPathToFileUrl(str(docx))
        document = desktop.loadComponentFromURL(
            url, '_blank', 0, (prop('Hidden', True), prop('ReadOnly', False))
        )
        if document is None:
            raise RuntimeError(f'LibreOffice could not open {docx}')

        indexes = document.getDocumentIndexes()
        if indexes.getCount() < 1:
            raise RuntimeError('No document index/TOC found after importing Word TOC field')
        for i in range(indexes.getCount()):
            indexes.getByIndex(i).update()

        # Let Writer complete pagination before saving refreshed TOC page references.
        if hasattr(document, 'refresh'):
            document.refresh()
        time.sleep(1.0)
        document.store()
        document.close(True)
        print(f'PASS: refreshed {indexes.getCount()} document index(es) with page numbers')
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == '__main__':
    main()
