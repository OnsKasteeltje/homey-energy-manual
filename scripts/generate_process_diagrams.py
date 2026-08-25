#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import json,re,sys

ROOT=Path(__file__).resolve().parents[1]
FLOW_ROOT=ROOT/'docs'/'software-architecture'/'flows'
MODEL_RE=re.compile(r'```process-model\s*\n(.*?)\n```',re.S)

def esc(s:str)->str:
    return s.replace('"','\\"')

def render(model:dict)->str:
    mid=model['id']
    if model.get('kind')=='mermaid-source':
        declaration=model.get('declaration','flowchart TD')
        lines=['```mermaid',declaration,*model.get('lines',[]),'```']
        return f'<!-- GENERATED_MERMAID:{mid} START -->\n'+"\n".join(lines)+f'\n<!-- GENERATED_MERMAID:{mid} END -->'
    direction=model.get('direction','TD'); nodes=model['nodes']; edges=model['edges']
    lines=['```mermaid',f'flowchart {direction}']
    ids={n['id'] for n in nodes}
    for n in nodes:
        nid=n['id']; label=esc(n['label']); typ=n.get('type','step')
        shape=f'{{{label}}}' if typ=='decision' else f'[{label}]'
        lines.append(f'  {nid}{shape}')
    for e in edges:
        if e['from'] not in ids or e['to'] not in ids: raise ValueError(f"{mid}: edge verwijst naar onbekende node")
        lab=e.get('label'); arrow=f"-->|{esc(lab)}|" if lab else '-->'
        lines.append(f"  {e['from']} {arrow} {e['to']}")
    lines.append('```')
    return f'<!-- GENERATED_MERMAID:{mid} START -->\n'+"\n".join(lines)+f'\n<!-- GENERATED_MERMAID:{mid} END -->'

def process(path:Path,check:bool)->bool:
    text=path.read_text(encoding='utf-8'); models=MODEL_RE.findall(text)
    if not models: return False
    out=text
    for raw in models:
        m=json.loads(raw); block=render(m); pat=re.compile(rf'<!-- GENERATED_MERMAID:{re.escape(m["id"])} START -->.*?<!-- GENERATED_MERMAID:{re.escape(m["id"])} END -->',re.S)
        if not pat.search(out): raise ValueError(f'{path}: generated block ontbreekt voor {m["id"]}')
        out=pat.sub(block,out,count=1)
    if check and out!=text: raise ValueError(f'{path}: Mermaid is niet synchroon met process-model')
    if not check and out!=text: path.write_text(out,encoding='utf-8')
    return out!=text

def main()->int:
    check='--check' in sys.argv
    count=0
    for p in sorted(FLOW_ROOT.glob('*.md')):
        if MODEL_RE.search(p.read_text(encoding='utf-8')):
            process(p,check); count+=1
    print(f'PASS: process-model files={count}; mode={"check" if check else "write"}')
    return 0

if __name__=='__main__':
    try: raise SystemExit(main())
    except Exception as e:
        print(f'FAIL: {e}',file=sys.stderr); raise SystemExit(1)
