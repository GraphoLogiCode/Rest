"""Check action names and ARN types against downloaded AWS service-reference JSON.

Usage: python3 deploy/ecs/check_iam.py /tmp/rest-iam-reference
This is a static check, not IAM simulation or a live authorization guarantee.
"""
import hashlib
import json
import re
import sys
from pathlib import Path
HERE=Path(__file__).resolve().parent

def compatible(arn, pattern):
    regex='^'+re.sub(r'\\\$\\\{[^}]+\\\}', '.+', re.escape(pattern))+'$'
    return bool(re.match(regex,arn))

def check(folder):
    checked=0;failures=[];sources={}
    for file in (HERE/'iam').glob('*policy.json'):
        document=json.loads(file.read_text())
        if 'Statement' not in document: continue
        for statement in document['Statement']:
            actions=statement['Action'];actions=[actions] if isinstance(actions,str) else actions
            resources=statement['Resource'];resources=[resources] if isinstance(resources,str) else resources
            for action in actions:
                service,name=action.split(':',1)
                path=folder/(service+'.json')
                data=json.loads(path.read_text());sources[service]={'url':f'https://servicereference.us-east-1.amazonaws.com/v1/{service}/{service}.json','sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'version':data.get('Version')}
                definition=next((a for a in data['Actions'] if a['Name']==name),None)
                if definition is None: failures.append(f'{file.name}: unknown action {action}');continue
                allowed=definition.get('Resources',[])
                if not allowed and '*' not in resources:failures.append(f'{file.name}: {action} requires Resource=*')
                patterns=[p for r in data['Resources'] if r['Name'] in {a['Name'] for a in allowed} for p in r['ARNFormats']]
                if allowed and '*' not in resources and not any(compatible(arn,pattern) for arn in resources for pattern in patterns):
                    failures.append(f'{file.name}: ARN type does not match {action}')
                checked+=1
    report={'checked_actions':checked,'failures':failures,'sources':sources,'limitation':'Static AWS action/ARN-type check only. Live IAM and deployment tests remain required.'}
    (HERE/'iam/static-check.json').write_text(json.dumps(report,indent=2)+'\n')
    for error in failures:print(error)
    print(f'Checked {checked} action references; {len(failures)} errors.')
    return not failures

if __name__=='__main__':raise SystemExit(0 if check(Path(sys.argv[1])) else 1)
