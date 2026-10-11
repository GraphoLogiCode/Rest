"""Generate concrete policies for the direct ECS deployment workflow; no AWS calls."""
import json
from pathlib import Path
HERE = Path(__file__).resolve().parent
S = json.loads((HERE / 'settings.json').read_text())
A, R = S['account'], S['region']
arn = lambda service, resource: f'arn:aws:{service}:{R}:{A}:{resource}'
role = lambda key: f"arn:aws:iam::{A}:role/{S[key]}"
repo = arn('ecr', 'repository/' + S['repository'])
bucket = 'arn:aws:s3:::' + S['source_bucket']
secret = arn('secretsmanager', 'secret:' + S['database_secret'] + '-??????')
cluster = arn('ecs', 'cluster/' + S['cluster'])
service = arn('ecs', f"service/{S['cluster']}/{S['service']}")
taskdef = arn('ecs', 'task-definition/' + S['task_family'] + ':*')
log = lambda key: arn('logs', 'log-group:' + S[key])
def stmt(sid, actions, resources, condition=None):
    out = {'Sid': sid, 'Effect': 'Allow', 'Action': actions, 'Resource': resources}
    if condition: out['Condition'] = condition
    return out

def policy(items): return {'Version': '2012-10-17', 'Statement': items}
def trust(service):
    return policy([{'Effect': 'Allow', 'Principal': {'Service': service}, 'Action': 'sts:AssumeRole'}])
def write(name, value):
    (HERE/'iam'/name).write_text(json.dumps(value, indent=2)+'\n')

write('deployer-trust.json', policy([{'Effect':'Allow','Principal':{'AWS':f'arn:aws:iam::{A}:user/Ben'},'Action':'sts:AssumeRole'}]))
write('ben-assume-deployer.json', policy([stmt('AssumeOnlyRestDeployment', ['sts:AssumeRole'], role('deployer_role'))]))
for key, principal in [('build_role','codebuild.amazonaws.com'),('execution_role','ecs-tasks.amazonaws.com'),('infrastructure_role','ecs.amazonaws.com')]:
    write(key.replace('_role','')+'-trust.json', trust(principal))

write('administrator-bootstrap-policy.json', policy([
 stmt('CreateInspectTagOnlyFourRoles', ['iam:CreateRole','iam:GetRole','iam:TagRole'], [role(k) for k in ('deployer_role','build_role','execution_role','infrastructure_role')]),
 stmt('ConfigureOnlyThreeInlinePolicies', ['iam:PutRolePolicy'], [role(k) for k in ('deployer_role','build_role','execution_role')]),
 stmt('AttachOnlyEcsInfrastructurePolicy', ['iam:AttachRolePolicy'], role('infrastructure_role'), {'ArnEquals':{'iam:PolicyARN':'arn:aws:iam::aws:policy/service-role/AmazonECSInfrastructureRoleforExpressGatewayServices'}}),
 stmt('GrantOnlyBenRoleAssumption', ['iam:PutUserPolicy'], f'arn:aws:iam::{A}:user/Ben')]))

write('build-policy.json', policy([
 stmt('ReadOnlySourceArchive', ['s3:GetObject','s3:GetObjectVersion'], bucket+'/source.zip'),
 stmt('InspectSourceBucket', ['s3:GetBucketLocation','s3:GetBucketAcl'], bucket),
 stmt('EcrRegistryAuthentication', ['ecr:GetAuthorizationToken'], '*'),
 stmt('PushOnlyAppRepository', ['ecr:BatchCheckLayerAvailability','ecr:InitiateLayerUpload','ecr:UploadLayerPart','ecr:CompleteLayerUpload','ecr:PutImage','ecr:BatchGetImage','ecr:GetDownloadUrlForLayer'], repo),
 stmt('WriteOnlyBuildLogs', ['logs:CreateLogStream','logs:PutLogEvents'], log('build_log_group')+':log-stream:*')]))
write('execution-policy.json', policy([
 stmt('EcrRegistryAuthentication', ['ecr:GetAuthorizationToken'], '*'),
 stmt('PullOnlyAppImage', ['ecr:BatchGetImage','ecr:GetDownloadUrlForLayer','ecr:BatchCheckLayerAvailability'], repo),
 stmt('WriteOnlyAppLogs', ['logs:CreateLogStream','logs:PutLogEvents'], log('app_log_group')+':log-stream:*'),
 stmt('ReadOnlyDatabaseConnection', ['secretsmanager:GetSecretValue'], secret)]))
# ECS's documented managed infrastructure policy handles tagged ALB, networking,
# certificates, autoscaling and alarms. It is attached only to this ECS-trusted role.
write('infrastructure-managed-policy.json', {'PolicyArn':'arn:aws:iam::aws:policy/service-role/AmazonECSInfrastructureRoleforExpressGatewayServices'})

items=[
 stmt('InspectExactServiceRoles', ['iam:GetRole'], [role(k) for k in ('build_role','execution_role','infrastructure_role')]),
 stmt('PassOnlyBuildRole', ['iam:PassRole'], role('build_role'), {'StringEquals':{'iam:PassedToService':'codebuild.amazonaws.com'}}),
 stmt('PassOnlyTaskExecutionRole', ['iam:PassRole'], role('execution_role'), {'StringEquals':{'iam:PassedToService':'ecs-tasks.amazonaws.com'}}),
 stmt('PassOnlyInfrastructureRole', ['iam:PassRole'], role('infrastructure_role'), {'StringEquals':{'iam:PassedToService':'ecs.amazonaws.com'}}),
 stmt('ProvisionOneSourceBucket', ['s3:CreateBucket','s3:GetBucketLocation','s3:ListBucket','s3:GetBucketPolicy','s3:PutBucketPolicy','s3:GetBucketPublicAccessBlock','s3:PutBucketPublicAccessBlock','s3:GetEncryptionConfiguration','s3:PutEncryptionConfiguration'], bucket),
 stmt('UploadOneArchive', ['s3:PutObject','s3:GetObject'], bucket+'/source.zip'),
 stmt('ProvisionOneRepository', ['ecr:CreateRepository','ecr:DescribeRepositories','ecr:DescribeImages','ecr:DescribeImageScanFindings','ecr:TagResource'], repo),
 stmt('BuildOneProject', ['codebuild:CreateProject','codebuild:UpdateProject','codebuild:BatchGetProjects','codebuild:StartBuild','codebuild:StopBuild'], arn('codebuild','project/'+S['build_project'])),
 stmt('MonitorOnlyProjectBuilds', ['codebuild:BatchGetBuilds'], arn('codebuild','project/'+S['build_project'])),
 stmt('ManagePilotLogs', ['logs:CreateLogGroup','logs:PutRetentionPolicy','logs:DescribeLogStreams','logs:FilterLogEvents'], [log(k)+':*' for k in ('build_log_group','app_log_group')]),
 stmt('ReadPilotLogEvents', ['logs:GetLogEvents'], [log(k)+':log-stream:*' for k in ('build_log_group','app_log_group')]),
 stmt('StoreOnlyDatabaseConnection', ['secretsmanager:CreateSecret','secretsmanager:DescribeSecret','secretsmanager:PutSecretValue','secretsmanager:TagResource'], secret),
 stmt('PilotCluster', ['ecs:CreateCluster','ecs:DescribeClusters'], cluster),
 stmt('PilotTaskDefinition', ['ecs:RegisterTaskDefinition'], taskdef),
 stmt('PilotExpressService', ['ecs:CreateExpressGatewayService','ecs:DescribeExpressGatewayService','ecs:UpdateExpressGatewayService','ecs:DeleteExpressGatewayService','ecs:DescribeServices'], service),
 stmt('TagPilotEcsResources', ['ecs:TagResource','ecs:ListTagsForResource'], [cluster,taskdef,service]),
 stmt('CreateEcsServiceLinkedRole', ['iam:CreateServiceLinkedRole'], f'arn:aws:iam::{A}:role/aws-service-role/ecs.amazonaws.com/AWSServiceRoleForECS', {'StringEquals':{'iam:AWSServiceName':'ecs.amazonaws.com'}}),
 stmt('InspectTaskDefinitions', ['ecs:DescribeTaskDefinition'], '*'),
 stmt('InspectNetworking', ['ec2:DescribeVpcs','ec2:DescribeSubnets','ec2:DescribeRouteTables'], '*'),
 stmt('InspectQuotas', ['servicequotas:GetServiceQuota'], '*')]
# IAM is global; constrain every regional service statement to Ohio.
for item in items:
    if not any(a.startswith('iam:') for a in item['Action']):
        item.setdefault('Condition', {}).setdefault('StringEquals', {})['aws:RequestedRegion']=R
write('operator-policy.json', policy(items))
compact=json.dumps(policy(items), separators=(',',':'))
assert len(compact)<10240, 'Inline role policy exceeds IAM size limit'
print(f'Generated policies for account {A}, region {R}. Operator policy: {len(compact)} characters; no IAM policy/role modification permission.')
