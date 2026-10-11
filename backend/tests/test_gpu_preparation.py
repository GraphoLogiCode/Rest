import importlib.util
from pathlib import Path

source = Path(__file__).resolve().parents[2] / 'deploy/aws/prepare_gpu.py'
spec = importlib.util.spec_from_file_location('prepare_gpu', source)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class FakeAWS:
    def __init__(self, quota=0, pending=False):
        self.quota, self.pending, self.writes = quota, pending, []
    def account(self): return {'Account': '620214493890'}
    def call(self, service, operation, body=None):
        if operation == 'describe-instance-types': return {'InstanceTypes': [{'VCpuInfo': {'DefaultVCpus': 8}}]}
        if operation == 'get-service-quota': return {'Quota': {'Value': self.quota}}
        if operation == 'list-requested-service-quota-change-history-by-quota':
            return {'RequestedQuotas': [{'Id': 'existing', 'Status': 'PENDING', 'DesiredValue': 8}] if self.pending else []}
        assert operation == 'request-service-quota-increase'
        self.writes.append(body)
        return {'RequestedQuota': {'Id': 'requested', 'Status': 'PENDING'}}


def test_preparation_is_read_only_by_default():
    aws = FakeAWS()
    result = module.prepare(aws)
    assert not aws.writes and not result['quotaReady'] and not result['launched']


def test_no_duplicate_quota_requests_or_instance_launch():
    for aws in [FakeAWS(quota=8), FakeAWS(pending=True)]:
        module.prepare(aws, request_quota=True)
        assert not aws.writes
    aws = FakeAWS()
    module.prepare(aws, request_quota=True)
    assert aws.writes == [{'ServiceCode': 'ec2', 'QuotaCode': 'L-DB2E81BA', 'DesiredValue': 8}]
