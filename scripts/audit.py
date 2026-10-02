"""Offline report and secret checks. Never echo a matching secret."""
import argparse
import json
import os
import re
import subprocess
from pathlib import Path
from html.parser import HTMLParser
from xhs_analyzer.storage import read, dump
from xhs_analyzer.report import all_claims

class HTMLAudit(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids, self.refs, self.external_assets = set(), [], []
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if 'id' in attrs:self.ids.add(attrs['id'])
        if attrs.get('href','').startswith('#'):self.refs.append(attrs['href'][1:])
        if tag in ('script','img','link') and any(attrs.get(k,'').startswith(('http:','https:','//')) for k in ('src','href')):
            self.external_assets.append(tag)

def audit(root, report):
    result={'secrets':[], 'git':'not-a-repository', 'report':{}, 'limits':['Structural validation cannot prove semantic truth.', 'Static standalone check does not replace a browser opening test.']}
    root=Path(root).resolve(); report=Path(report)
    secrets=[os.environ.get(k) for k in ('TIKHUB_API_KEY','AI_API_KEY') if os.environ.get(k)]
    patterns=[re.compile(r'\bsk-[A-Za-z0-9_-]{24,}\b'),re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
              re.compile(r'(?im)^\s*(?:TIKHUB_API_KEY|AI_API_KEY)\s*=\s*["\']?([A-Za-z0-9_-]{20,})')]
    paths=[p for p in root.rglob('*') if p.is_file() and not {'.git','.venv','__pycache__'} & set(p.parts)]
    for path in paths:
        try:text=path.read_text(encoding='utf-8-sig')
        except (UnicodeError,OSError):continue
        if any(s in text for s in secrets) or any(p.search(text) for p in patterns):
            result['secrets'].append(str(path.relative_to(root)))
    try:
        probe=subprocess.run(['git','rev-parse','--show-toplevel'],cwd=root,capture_output=True,text=True)
        if probe.returncode==0:
            gitroot=Path(probe.stdout.strip()).resolve()
            tracked=subprocess.run(['git','ls-files','-z'],cwd=root,capture_output=True).stdout.decode().split('\0')
            result['git']='tracked-files-checked'
            result['tracked_env_files']=[p for p in tracked if Path(p).name=='.env' or (Path(p).name.startswith('.env.') and Path(p).name!='.env.example')]
            # Inspect all reachable historical blobs without displaying their content.
            objects=subprocess.run(['git','rev-list','--objects','--all'],cwd=root,capture_output=True,text=True)
            scanned=0
            for line in objects.stdout.splitlines():
                sha=line.split(' ',1)[0]
                kind=subprocess.run(['git','cat-file','-t',sha],cwd=root,capture_output=True,text=True)
                if kind.stdout.strip()!='blob':continue
                payload=subprocess.run(['git','cat-file','-p',sha],cwd=root,capture_output=True).stdout.decode('utf-8',errors='ignore')
                scanned+=1
                if any(s in payload for s in secrets) or any(p.search(payload) for p in patterns):
                    result['secrets'].append('git-blob:'+sha)
            result['historical_blobs_checked']=scanned
    except OSError:
        result['git']='git-unavailable'
    data=read(report/'analysis-result.json')
    known={e['evidence_id'] for e in data['evidence']}
    claims=all_claims(data)
    result['report']['claims_checked']=len(claims)
    result['report']['unresolved_claims']=sum(not c.get('evidence_ids') or not set(c['evidence_ids'])<=known for c in claims)
    result['report']['untyped_claims']=sum(c.get('claim_type') not in {'FACT','ANALYSIS','INFERENCE'} for c in claims)
    parser=HTMLAudit();parser.feed((report/'report.html').read_text(encoding='utf-8'))
    result['report']['broken_anchors']=len(set(parser.refs)-parser.ids)
    result['report']['external_runtime_assets']=parser.external_assets
    result['report']['hypotheses']={k:len(v) for k,v in data['hypotheses'].items()}
    result['passed']=not(result['secrets'] or result.get('tracked_env_files') or result['report']['unresolved_claims'] or result['report']['untyped_claims'] or result['report']['broken_anchors'] or result['report']['external_runtime_assets'])
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--report',type=Path,default=Path('examples/demo'))
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--out',type=Path,default=Path('references/audit-result.json'))
    args=parser.parse_args()
    result=audit(args.root,args.report)
    dump(args.out,result)
    print(json.dumps(result,ensure_ascii=True,indent=2))
    raise SystemExit(0 if result['passed'] else 1)
