"""Build a source-only ZIP, excluding local secrets, runtime state and caches."""
from pathlib import Path
import sys
import zipfile
root=Path(__file__).resolve().parents[1]
output=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else root.parent/'Noryx-Hosting-Backend-v5.zip'
excluded={'.git','.venv','venv','node_modules','__pycache__','.pytest_cache','instance'}
with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
    for path in sorted(root.rglob('*')):
        if not path.is_file() or path.is_symlink() or path==output: continue
        relative=path.relative_to(root)
        if excluded.intersection(relative.parts): continue
        if path.name=='.env' or (path.name.startswith('.env.') and path.name!='.env.example'): continue
        if path.suffix.lower() in {'.pyc','.pyo','.log','.sqlite','.sqlite3','.db','.pem','.key','.zip'}: continue
        archive.write(path,Path(root.name)/relative)
print(output)
