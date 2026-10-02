"""Package source and synthetic examples only; never include runtime data or credentials."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

def package(root):
    root=Path(root).resolve()
    destination=root.parent/(root.name+'-v1.zip')
    allowed_dirs={'scripts','references','templates','tests','examples'}
    allowed_files={'SKILL.md','README.md','requirements.txt','.env.example','.gitignore'}
    with ZipFile(destination,'w',ZIP_DEFLATED) as archive:
        for path in sorted(root.rglob('*')):
            if not path.is_file():continue
            relative=path.relative_to(root)
            if '__pycache__' in relative.parts or path.suffix in {'.pyc','.pyo'}:continue
            if path.name.startswith('.env') and path.name!='.env.example':continue
            if len(relative.parts)==1 and path.name not in allowed_files:continue
            if len(relative.parts)>1 and relative.parts[0] not in allowed_dirs:continue
            if relative.parts[0]=='examples' and path.name=='dataset.json':
                import json
                if not json.loads(path.read_text(encoding='utf-8'))['synthetic']:
                    raise ValueError('Refusing to package live examples')
            archive.write(path,str(Path(root.name)/relative))
    return destination

if __name__=='__main__':print(package(Path(__file__).resolve().parents[1]))
