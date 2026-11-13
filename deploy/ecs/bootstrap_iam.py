"""Administrator provisioning of four fixed IAM roles. Plan-only unless --apply."""
import argparse
import json
from aws_client import AWS, AwsFailure, HERE, SETTINGS as S

def load(file): return json.loads((HERE/'iam'/file).read_text())
def role_specs():
    return [
      (S['deployer_role'],'deployer-trust.json','operator-policy.json',None),
      (S['build_role'],'build-trust.json','build-policy.json',None),
      (S['execution_role'],'execution-trust.json','execution-policy.json',None),
      (S['infrastructure_role'],'infrastructure-trust.json',None,load('infrastructure-managed-policy.json')['PolicyArn'])]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--profile');parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    if not args.apply:
        for name,trust,inline,managed in role_specs(): print(f'{name}: trust={trust}; policy={inline or managed}')
        print('Ben receives only sts:AssumeRole for rest-pilot-deployer. No changes made. Administrator runs --apply after review.')
        return
    aws=AWS(args.profile);aws.account()
    for name,trust,inline,managed in role_specs():
        expected=load(trust)
        try:
            existing=aws.call('iam','get-role',{'RoleName':name})['Role']
            if existing['AssumeRolePolicyDocument'] != expected:
                raise RuntimeError(f'{name} has a different trust policy; no automatic trust changes were made.')
        except AwsFailure as exc:
            if exc.code != 'NoSuchEntity': raise
            aws.call('iam','create-role',{'RoleName':name,'AssumeRolePolicyDocument':json.dumps(expected),'Tags':[{'Key':'RestApp','Value':'pilot'}]})
        if inline: aws.call('iam','put-role-policy',{'RoleName':name,'PolicyName':'RestPilotScoped','PolicyDocument':json.dumps(load(inline))})
        if managed: aws.call('iam','attach-role-policy',{'RoleName':name,'PolicyArn':managed})
        print(f'Configured {name}.',flush=True)
    aws.call('iam','put-user-policy',{'UserName':'Ben','PolicyName':'AssumeRestPilotDeployer','PolicyDocument':json.dumps(load('ben-assume-deployer.json'))})
    print('IAM bootstrap complete. Configure the rest-pilot CLI role profile, then run deploy.py preflight.')

if __name__=='__main__':
    try: main()
    except (AwsFailure,RuntimeError) as exc: raise SystemExit(str(exc))
