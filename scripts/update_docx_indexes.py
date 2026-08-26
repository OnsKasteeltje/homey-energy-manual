#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import os
import subprocess
import sys
import time

DOCX = Path(sys.argv[1] if len(sys.argv) > 1 else 'build/Softwarearchitectuur_Home_Energy_Management_System.docx').resolve()
PROFILE = Path('/tmp/lo-toc-profile').resolve()
PORT = 2002


def main() -> int:
    if not DOCX.exists():
        raise FileNotFoundError(DOCX)
    PROFILE.mkdir(parents=True, exist_ok=True)

    soffice = subprocess.Popen([
        'libreoffice',
        f'-env:UserInstallation=file://{PROFILE}',
        '--headless',
        f'--accept=socket,host=127.0.0.1,port={PORT};urp;StarOffice.ComponentContext',
        '--norestore', '--nodefault', '--nofirststartwizard',
    ])
    try:
        time.sleep(2)
        import uno
        from com.sun.star.beans import PropertyValue

        local_ctx = uno.getComponentContext()
        resolver = local_ctx.ServiceManager.createInstanceWithContext('com.sun.star.bridge.UnoUrlResolver', local_ctx)
        ctx = resolver.resolve(f'uno:socket,host=127.0.0.1,port={PORT};urp;StarOffice.ComponentContext')
        smgr = ctx.ServiceManager
        desktop = smgr.createInstanceWithContext('com.sun.star.frame.Desktop', ctx)

        hidden = PropertyValue()
        hidden.Name = 'Hidden'
        hidden.Value = True
        url = uno.systemPathToFileUrl(str(DOCX))
        doc = desktop.loadComponentFromURL(url, '_blank', 0, (hidden,))
        if doc is None:
            raise RuntimeError('LibreOffice kon DOCX niet openen')

        indexes = doc.getDocumentIndexes()
        if indexes.getCount() == 0:
            raise RuntimeError('Geen document-index/TOC gevonden in DOCX')
        for i in range(indexes.getCount()):
            indexes.getByIndex(i).update()

        doc.updateLinks()
        doc.store()
        doc.close(True)
        print(f'PASS: updated document indexes={indexes.getCount()} in {DOCX}')
        return 0
    finally:
        soffice.terminate()
        try:
            soffice.wait(timeout=5)
        except subprocess.TimeoutExpired:
            soffice.kill()


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f'FAIL: {exc}', file=sys.stderr)
        raise SystemExit(1)
