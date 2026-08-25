#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import json,re,sys

ROOT=Path(__file__).resolve().parents[1]
FLOW_ROOT=ROOT/'docs'/'software-architecture'/'flows'
MERMAID_RE=re.compile(r'```mermaid\s*\n(.*?)\n```',re.S|re.I)
GEN_START='<!-- GENERATED_MERMAID:'

def migrate(path:Path,check:bool)->bool:
    text=path.read_text(encoding='utf-8')
    # Ignore files already fully source-controlled by process-model blocks.
    parts=[]; pos=0; idx=0; changed=False
    for m in MERMAID_RE.finditer(text):
        # Mermaid inside an existing generated block is already managed.
        prefix=text[max(0,m.start()-120):m.start()]
        if GEN_START in prefix and ' START -->' in prefix:
            continue
        idx+=1; changed=True
        body=m.group(1).strip('\n')
        lines=body.splitlines()
        declaration=lines[0].strip() if lines else 'flowchart TD'
        model_id=f'{path.stem}-{idx}'
        model={"id":model_id,"kind":"mermaid-source","declaration":declaration,"lines":lines[1:]}
        replacement=("```process-model\n"+json.dumps(model,ensure_ascii=False,indent=2)+"\n```\n\n"
                     f"<!-- GENERATED_MERMAID:{model_id} START -->\n```mermaid\n{body}\n```\n"
                     f"<!-- GENERATED_MERMAID:{model_id} END -->")
        parts.append(text[pos:m.start()]); parts.append(replacement); pos=m.end()
    if not changed:
        return False
    parts.append(text[pos:]); out=''.join(parts)
    if check:
        raise ValueError(f'{path}: legacy handmatig Mermaid-blok aanwezig')
    path.write_text(out,encoding='utf-8')
    return True

def main()->int:
    check='--check' in sys.argv
    changed=[]
    for p in sorted(FLOW_ROOT.glob('*.md')):
        if migrate(p,check): changed.append(p.name)
    print(f'PASS: legacy Mermaid migration; changed={len(changed)}; mode={"check" if check else "write"}')
    return 0

if __name__=='__main__':
    try: raise SystemExit(main())
    except Exception as e:
        print(f'FAIL: {e}',file=sys.stderr); raise SystemExit(1)
