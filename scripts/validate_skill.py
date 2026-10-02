"""Dependency-free check for this skill's simple two-field YAML frontmatter."""
import re
from pathlib import Path

def validate(root):
    root=Path(root)
    text=(root/'SKILL.md').read_text(encoding='utf-8')
    if not text.startswith('---\n'):
        raise ValueError('Missing frontmatter')
    front=text.split('---',2)[1].strip()
    metadata={}
    for line in front.splitlines():
        key,value=line.split(':',1)
        metadata[key.strip()]=value.strip()
    if set(metadata)!={'name','description'}:
        raise ValueError('Expected name and description')
    if not re.fullmatch(r'[a-z0-9-]{1,63}',metadata['name']) or metadata['name']!=root.name:
        raise ValueError('Invalid skill name')
    if not metadata['description']:
        raise ValueError('Empty description')
    for name in ['README.md','requirements.txt','.env.example','.gitignore','scripts','references','templates','tests']:
        if not (root/name).exists():raise ValueError('Missing '+name)
    if '[TODO:' in text:raise ValueError('Unfinished scaffold')
    return True

if __name__=='__main__':
    validate(Path(__file__).resolve().parents[1])
    print('Skill metadata and required files validated (stdlib checker).')
