"""Reproducible CPU deployment. Default is read-only preflight; --deploy creates resources."""
import argparse
import hashlib
import json
import os
import runpy
import sys
import time
from pathlib import Path
from aws_client import AWS, AwsFailure, HERE, SETTINGS as S
ROOT=HERE.parents[1]
STATE=ROOT/'output/ecs-deployment.json'

def role(key): return f"arn:aws:iam::{S['account']}:role/{S[key]}"
def project_config(public):
    registry=f"{S['account']}.dkr.ecr.{S['region']}.amazonaws.com"
    return {'name':S['build_project'],'serviceRole':role('build_role'),'timeoutInMinutes':20,'concurrentBuildLimit':1,
      'artifacts':{'type':'NO_ARTIFACTS'},'source':{'type':'S3','location':S['source_bucket']+'/source.zip','buildspec':'deploy/pilot/buildspec.yml'},
      'environment':{'type':'LINUX_CONTAINER','computeType':'BUILD_GENERAL1_SMALL','image':'aws/codebuild/standard:7.0','privilegedMode':True,
        'environmentVariables':[{'name':k,'value':v,'type':'PLAINTEXT'} for k,v in {'SUPABASE_URL':public['url'],'SUPABASE_PUBLISHABLE_KEY':public['key'],'ECR_REGISTRY':registry,'IMAGE_URI':registry+'/'+S['repository']+':pilot'}.items()]},
      'logsConfig':{'cloudWatchLogs':{'status':'ENABLED','groupName':S['build_log_group'],'streamName':'build'}}}

def task_request(image, secret, public):
    return {'family':S['task_family'],'executionRoleArn':role('execution_role'),'networkMode':'awsvpc','requiresCompatibilities':['FARGATE'],
      'cpu':'1024','memory':'2048','runtimePlatform':{'cpuArchitecture':'X86_64','operatingSystemFamily':'LINUX'},
      'containerDefinitions':[{'name':'Main','image':image,'essential':True,'portMappings':[{'containerPort':8000,'name':'http','protocol':'tcp'}],
        'environment':[{'name':'SUPABASE_URL','value':public['url']}],'secrets':[{'name':'DATABASE_URL','valueFrom':secret}],
        'logConfiguration':{'logDriver':'awslogs','options':{'awslogs-group':S['app_log_group'],'awslogs-region':S['region'],'awslogs-stream-prefix':'ecs'}}}],
      'tags':[{'key':'RestApp','value':'pilot'}]}

def service_request(task_arn, subnets):
    return {'serviceName':S['service'],'cluster':S['cluster'],'infrastructureRoleArn':role('infrastructure_role'),
      'taskDefinitionArn':task_arn,'healthCheckPath':'/rest-api/healthz','networkConfiguration':{'subnets':subnets},
      'scalingTarget':{'minTaskCount':1,'maxTaskCount':1,'autoScalingMetric':'AVERAGE_CPU','autoScalingTargetValue':60},
      'tags':[{'key':'RestApp','value':'pilot'}]}

def public_config():
    from dotenv import dotenv_values
    front=dotenv_values(ROOT/'frontend/.env.local');back=dotenv_values(ROOT/'backend/.env')
    url=os.environ.get('SUPABASE_URL') or back.get('SUPABASE_URL')
    key=os.environ.get('SUPABASE_PUBLISHABLE_KEY') or front.get('VITE_SUPABASE_PUBLISHABLE_KEY')
    if url != 'https://byrndjhgzusfjdgjfbev.supabase.co' or not key:
        raise RuntimeError('Expected Rest project URL and public publishable key in the private local configuration.')
    if not key.startswith('sb_publishable_'):
        import base64
        try:
            claims=json.loads(base64.urlsafe_b64decode(key.split('.')[1]+'==='))
            if claims.get('role')!='anon': raise ValueError()
        except Exception: raise RuntimeError('Frontend key must be publishable/anon; server keys are rejected.') from None
    return {'url':url,'key':key}, back

def preflight(aws):
    identity=aws.account();print('AWS account verified:',identity['Account'],flush=True)
    for name in ('build_role','execution_role','infrastructure_role'):
        result=aws.call('iam','get-role',{'RoleName':S[name]})['Role']
        if result['Arn']!=role(name): raise RuntimeError('Unexpected service role; no changes made.')
    vpcs=aws.call('ec2','describe-vpcs',{'Filters':[{'Name':'is-default','Values':['true']}]})['Vpcs']
    if len(vpcs)!=1: raise RuntimeError('A default VPC is required. No network was created automatically.')
    subnets=aws.call('ec2','describe-subnets',{'Filters':[{'Name':'vpc-id','Values':[vpcs[0]['VpcId']]}]})['Subnets']
    public=[s for s in subnets if s.get('MapPublicIpOnLaunch')]
    if len({s['AvailabilityZone'] for s in public})<2: raise RuntimeError('Need public subnets in two availability zones.')
    routes=aws.call('ec2','describe-route-tables',{'Filters':[{'Name':'vpc-id','Values':[vpcs[0]['VpcId']]}]})['RouteTables']
    for subnet in public:
        matching=[r for r in routes if any(a.get('SubnetId')==subnet['SubnetId'] for a in r['Associations'])]
        matching=matching or [r for r in routes if any(a.get('Main') for a in r['Associations'])]
        if not any(route.get('DestinationCidrBlock')=='0.0.0.0/0' and route.get('GatewayId','').startswith('igw-') and route.get('State')=='active' for table in matching for route in table['Routes']):
            raise RuntimeError('Default subnet lacks an internet-gateway route; no network changes made.')
    # Read checks expose missing deployment access before any billable build.
    aws.call('codebuild','batch-get-projects',{'names':[S['build_project']]})
    quota = aws.call('service-quotas','get-service-quota',{'ServiceCode':'fargate','QuotaCode':'L-3032A538'})['Quota']['Value']
    if quota < 2: raise RuntimeError('Fargate quota must support the one-vCPU task plus rollout overlap. No resources created.')
    print('Service roles, public networking and CodeBuild inspection passed.',flush=True)
    return [s['SubnetId'] for s in public]

def resource(aws, service, get, query, create, body, absent):
    try: return aws.call(service,get,query)
    except AwsFailure as exc:
        if exc.code not in absent: raise
        return aws.call(service,create,body)

def save_state(values):
    STATE.parent.mkdir(exist_ok=True)
    old=json.loads(STATE.read_text()) if STATE.exists() else {}
    old.update(values); temp=STATE.with_suffix('.tmp');temp.write_text(json.dumps(old,indent=2)+'\n');temp.replace(STATE)

def provision(aws,public):
    resource(aws,'s3api','head-bucket',{'Bucket':S['source_bucket'],'ExpectedBucketOwner':S['account']},'create-bucket',{'Bucket':S['source_bucket'],'CreateBucketConfiguration':{'LocationConstraint':S['region']}}, {'404','NoSuchBucket','NotFound'})
    aws.call('s3api','put-public-access-block',{'Bucket':S['source_bucket'],'PublicAccessBlockConfiguration':{k:True for k in ('BlockPublicAcls','IgnorePublicAcls','BlockPublicPolicy','RestrictPublicBuckets')}})
    aws.call('s3api','put-bucket-encryption',{'Bucket':S['source_bucket'],'ServerSideEncryptionConfiguration':{'Rules':[{'ApplyServerSideEncryptionByDefault':{'SSEAlgorithm':'AES256'}}]}})
    bucket='arn:aws:s3:::'+S['source_bucket']
    aws.call('s3api','put-bucket-policy',{'Bucket':S['source_bucket'],'Policy':json.dumps({'Version':'2012-10-17','Statement':[{'Effect':'Deny','Principal':'*','Action':'s3:*','Resource':[bucket,bucket+'/*'],'Condition':{'Bool':{'aws:SecureTransport':'false'}}}]})})
    repo=resource(aws,'ecr','describe-repositories',{'repositoryNames':[S['repository']]},'create-repository',{'repositoryName':S['repository'],'imageScanningConfiguration':{'scanOnPush':True},'encryptionConfiguration':{'encryptionType':'AES256'},'tags':[{'Key':'RestApp','Value':'pilot'}]}, {'RepositoryNotFoundException'})
    for group in (S['build_log_group'],S['app_log_group']):
        try: aws.call('logs','create-log-group',{'logGroupName':group})
        except AwsFailure as exc:
            if exc.code!='ResourceAlreadyExistsException': raise
        aws.call('logs','put-retention-policy',{'logGroupName':group,'retentionInDays':7})
    config=project_config(public)
    existing=aws.call('codebuild','batch-get-projects',{'names':[S['build_project']]})['projects']
    if existing and existing[0]['serviceRole'] != role('build_role'):
        raise RuntimeError('Existing build project has a different role; it was not overwritten.')
    aws.call('codebuild','update-project' if existing else 'create-project',config)
    print('Private source bucket, image repository, log groups and build project configured.',flush=True)


def build_image(aws):
    runpy.run_path(str(ROOT/'deploy/pilot/package_source.py'),run_name='__main__')
    archive=ROOT/'output/rest-pilot-source.zip'
    digest=hashlib.sha256(archive.read_bytes()).hexdigest();tag='source-'+digest[:16]
    image=f"{S['account']}.dkr.ecr.{S['region']}.amazonaws.com/{S['repository']}:{tag}"
    aws.call('s3api','put-object',None,extra=('--bucket',S['source_bucket'],'--key','source.zip','--body',str(archive),'--server-side-encryption','AES256'))
    started=aws.call('codebuild','start-build',{'projectName':S['build_project'],'idempotencyToken':digest,'environmentVariablesOverride':[{'name':'IMAGE_URI','value':image,'type':'PLAINTEXT'}]})['build']['id']
    save_state({'build_id':started,'source_sha256':digest});print('Cloud build started:',started,flush=True)
    deadline=time.monotonic()+25*60
    while time.monotonic()<deadline:
        build=aws.call('codebuild','batch-get-builds',{'ids':[started]})['builds'][0]
        if build['buildStatus']=='SUCCEEDED': break
        if build['buildStatus']!='IN_PROGRESS': raise RuntimeError('Cloud build '+build['buildStatus']+'. Inspect its scoped CloudWatch logs.')
        time.sleep(10)
    else: raise RuntimeError('Build wait timed out. Inspect the saved build ID; do not launch another build blindly.')
    scan = None
    for attempt in range(30):
        try:
            scan = aws.call('ecr','describe-image-scan-findings', {'repositoryName':S['repository'],'imageId':{'imageTag':tag}})
        except AwsFailure as exc:
            if exc.code != 'ScanNotFoundException': raise
        if scan and scan.get('imageScanStatus',{}).get('status') in {'COMPLETE','ACTIVE'}: break
        if scan and scan.get('imageScanStatus',{}).get('status') in {'FAILED','UNSUPPORTED_IMAGE','FINDINGS_UNAVAILABLE','LIMIT_EXCEEDED'}:
            raise RuntimeError('Image scan unavailable; inspect ECR before launching.')
        time.sleep(10)
    else: raise RuntimeError('Image scan wait timed out; inspect ECR before launching.')
    counts=scan.get('imageScanFindings',{}).get('findingSeverityCounts',{})
    save_state({'image_scan_counts':counts})
    print('Image scan counts:',json.dumps(counts,sort_keys=True),flush=True)
    if counts.get('CRITICAL',0): raise RuntimeError('Image scan reported critical findings; resolve them before launch.')
    details=aws.call('ecr','describe-images',{'repositoryName':S['repository'],'imageIds':[{'imageTag':tag}]})['imageDetails'][0]
    # Pin the digest so a tag cannot silently replace the deployed image.
    pinned=image.rsplit(':',1)[0]+'@'+details['imageDigest'];save_state({'image_uri':pinned})
    print('Cloud build passed; image digest pinned.',flush=True)
    return pinned

def database_secret(aws,back):
    secret=os.environ.get('DATABASE_URL') or back.get('DATABASE_URL')
    if not secret or 'sslmode=require' not in secret: raise RuntimeError('A verified TLS DATABASE_URL is required in private configuration.')
    try: arn=aws.call('secretsmanager','describe-secret',{'SecretId':S['database_secret']})['ARN']
    except AwsFailure as exc:
        if exc.code!='ResourceNotFoundException': raise
        arn=aws.call('secretsmanager','create-secret',{'Name':S['database_secret'],'SecretString':secret,'Tags':[{'Key':'RestApp','Value':'pilot'}]})['ARN']
    # Existing secrets are reused; do not overwrite a live connection implicitly.
    print('Database secret reference prepared; value was not printed.',flush=True)
    return arn

def launch(aws,image,secret,public,subnets):
    task=aws.call('ecs','register-task-definition',task_request(image,secret,public))['taskDefinition']['taskDefinitionArn']
    arn=f"arn:aws:ecs:{S['region']}:{S['account']}:service/{S['cluster']}/{S['service']}"
    try:
        found=aws.call('ecs','describe-services',{'cluster':S['cluster'],'services':[S['service']]})
        existing=found['services'][0] if found['services'] else None
        if existing: aws.call('ecs','describe-express-gateway-service',{'serviceArn':arn})
    except AwsFailure as exc:
        if exc.code != 'ClusterNotFoundException': raise
        existing=None
    if existing:
        result=aws.call('ecs','update-express-gateway-service',{'serviceArn':arn,'taskDefinitionArn':task})
    else:
        aws.call('ecs','create-cluster',{'clusterName':S['cluster'],'tags':[{'key':'RestApp','value':'pilot'}]})
        result=aws.call('ecs','create-express-gateway-service',service_request(task,subnets))
    save_state({'service_arn':result['service']['serviceArn'],'task_definition':task,'database_secret_arn':secret})
    print('Managed HTTPS deployment started; monitor with deploy.py status.',flush=True)

def status(aws):
    arn=f"arn:aws:ecs:{S['region']}:{S['account']}:service/{S['cluster']}/{S['service']}"
    service=aws.call('ecs','describe-express-gateway-service',{'serviceArn':arn})['service']
    print(json.dumps({'status':service.get('status'),'endpoints':[ingress['endpoint'] for revision in service.get('activeConfigurations',[]) for ingress in revision.get('ingressPaths',[])]},indent=2))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['preflight','deploy','status'],nargs='?',default='preflight');parser.add_argument('--profile');args=parser.parse_args()
    aws=AWS(args.profile)
    if args.action=='status': aws.account();status(aws);return
    subnets=preflight(aws)
    if args.action=='preflight': print('Read-only preflight complete. No resources created.');return
    public,back=public_config()
    if not back.get('DATABASE_URL'): raise RuntimeError('Private database configuration is missing; no resources created.')
    provision(aws,public);image=build_image(aws);secret=database_secret(aws,back);launch(aws,image,secret,public,subnets)

if __name__=='__main__':
    try: main()
    except (AwsFailure,RuntimeError) as exc: raise SystemExit(str(exc))
