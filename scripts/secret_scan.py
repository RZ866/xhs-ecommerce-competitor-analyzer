"""Pattern-based scan. Never print matching secret values."""
import re,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PATTERNS={
 'private_key':rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
 'github_token':rb'\b(?:ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})',
 'bearer_literal':rb'(?i)bearer\s+[A-Za-z0-9._-]{35,}',
 'secret_assignment':rb'(?i)(?:api[_-]?key|password|web_session|access_token)\s*[=:]\s*["\x27]([A-Za-z0-9_-]{24,})["\x27]',
}
def main():
    findings=[];checked=0
    def inspect(label,data):
        nonlocal checked
        checked+=1
        for name,pattern in PATTERNS.items():
            if re.search(pattern,data):findings.append((label,name))
    for path in ROOT.rglob('*'):
        if not path.is_file() or any(p in ('.git','reports','.state','.internal','__pycache__','.venv','dist') for p in path.relative_to(ROOT).parts):continue
        inspect(str(path.relative_to(ROOT)),path.read_bytes())
    listing=subprocess.run(['git','rev-list','--objects','--all'],cwd=ROOT,capture_output=True,check=True,text=True).stdout
    for line in listing.splitlines():
        identity=line.split(' ',1)[0]
        obj=subprocess.run(['git','cat-file','-t',identity],cwd=ROOT,capture_output=True,check=True).stdout.strip()
        if obj==b'blob':inspect('git:'+identity,subprocess.run(['git','cat-file','blob',identity],cwd=ROOT,capture_output=True,check=True).stdout)
    print(f'Scanned {checked} files/objects; findings={len(findings)}')
    for location,kind in findings:print(location,kind)
    return bool(findings)
if __name__=='__main__':sys.exit(main())
