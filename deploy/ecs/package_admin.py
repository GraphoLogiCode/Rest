"""Bundle only the administrator setup, policies and fixed resource settings."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
out=ROOT/'output/rest-ecs-iam.zip';out.parent.mkdir(exist_ok=True)
files=[HERE/'bootstrap_iam.py',HERE/'aws_client.py',HERE/'settings.json',*sorted((HERE/'iam').glob('*.json'))]
with ZipFile(out,'w',ZIP_DEFLATED) as archive:
    for file in files: archive.write(file,Path('rest-ecs-iam')/file.relative_to(HERE))
print('Created',out,'with IAM setup only; no app data, environment files or credentials.')
