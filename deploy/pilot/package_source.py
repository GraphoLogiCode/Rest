"""Build an allowlisted source archive for CodeBuild, excluding secrets and photos."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
root = Path(__file__).resolve().parents[2]
out = root / 'output/rest-pilot-source.zip'
files = []
for folder in ('backend/src', 'frontend/src', 'frontend/public', 'frontend/build', 'frontend/tests', 'backend/tests', 'deploy/ecs'):
    files.extend(p for p in (root / folder).rglob('*') if p.is_file() and not p.is_symlink() and '__pycache__' not in p.parts and not any(s.startswith('.') for s in p.relative_to(root).parts))
for file in ('backend/requirements.txt', 'backend/requirements-dev.txt', 'backend/pytest.ini', 'frontend/package.json', 'frontend/package-lock.json', 'frontend/index.html', 'frontend/tsconfig.json', 'frontend/vite.config.ts', 'data/catalog/products.json', 'deploy/pilot/Dockerfile.managed', 'deploy/pilot/buildspec.yml'):
    files.append(root / file)
out.parent.mkdir(exist_ok=True)
with ZipFile(out, 'w', ZIP_DEFLATED) as archive:
    for file in sorted(files): archive.write(file, file.relative_to(root))
print(f'Packaged {len(files)} allowlisted files into {out}. No .env, local uploads or model weights included.')
