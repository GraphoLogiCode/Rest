"""Deployment contracts and secret handling; no AWS mutations or credentials."""
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'deploy/ecs'))
from aws_client import AWS, AwsFailure
from deploy import preflight, service_request, task_request


def test_secret_request_uses_private_deleted_file_not_command_arguments():
    seen=[]
    def runner(command, **kwargs):
        path=Path(command[command.index('--cli-input-json')+1].removeprefix('file://'))
        assert path.stat().st_mode & 0o777 == 0o600
        assert json.loads(path.read_text())['SecretString']=='private-test-value'
        assert 'private-test-value' not in ' '.join(command)
        seen.append(path)
        return SimpleNamespace(returncode=0, stdout='{"ARN":"secret-reference"}', stderr='')
    assert AWS(runner=runner).call('secretsmanager','create-secret',{'SecretString':'private-test-value'})['ARN']=='secret-reference'
    assert not seen[0].exists()


def test_secret_cleanup_and_error_message_do_not_echo_request():
    seen=[]
    def runner(command, **kwargs):
        seen.append(Path(command[-1].removeprefix('file://')))
        return SimpleNamespace(returncode=1,stdout='',stderr='An error occurred (AccessDenied): private-test-value')
    with pytest.raises(AwsFailure) as error: AWS(runner=runner).call('secretsmanager','create-secret',{'SecretString':'private-test-value'})
    assert 'private-test-value' not in str(error.value)
    assert not seen[0].exists()


def test_preflight_fails_before_any_mutation_when_role_access_is_denied():
    class FixtureAWS:
        calls=[]
        def account(self): return {'Account':'620214493890'}
        def call(self, service, operation, body):
            self.calls.append(operation)
            raise AwsFailure(service,operation,'AccessDenied')
    aws=FixtureAWS()
    with pytest.raises(AwsFailure):preflight(aws)
    assert aws.calls==['get-role']


def test_express_task_definition_has_private_secret_and_fixed_health_route():
    task=task_request('registry/app@sha256:test','arn:aws:secretsmanager:us-east-2:620214493890:secret:rest-pilot/database-url-abcdef',{'url':'https://example.supabase.co'})
    assert task['requiresCompatibilities']==['FARGATE']
    container=task['containerDefinitions'][0]
    assert container['name']=='Main'
    assert len(container['portMappings'])==1 and container['portMappings'][0]['containerPort']==8000
    assert container['secrets'][0]['name']=='DATABASE_URL'
    assert all(v['name']!='DATABASE_URL' for v in container['environment'])
    assert 'taskRoleArn' not in task
    service=service_request('arn:aws:ecs:us-east-2:620214493890:task-definition/rest-pilot-app:1',['subnet-a','subnet-b'])
    assert service['healthCheckPath']=='/rest-api/healthz'
    assert service['scalingTarget']['maxTaskCount']==1
    for mutually_exclusive in ('primaryContainer','executionRoleArn','taskRoleArn','cpu','memory','cpuArchitecture'):assert mutually_exclusive not in service


def test_operator_cannot_modify_iam_policies_and_passes_only_fixed_service_roles():
    policy=json.loads((Path(__file__).resolve().parents[2]/'deploy/ecs/iam/operator-policy.json').read_text())
    for statement in policy['Statement']:
        assert not any(action in {'iam:PutRolePolicy','iam:PutUserPolicy','iam:CreateRole','iam:AttachRolePolicy'} for action in statement['Action'])
        if 'iam:PassRole' in statement['Action']:
            assert statement['Resource'].startswith('arn:aws:iam::620214493890:role/rest-pilot-')
            assert 'iam:PassedToService' in statement['Condition']['StringEquals']
