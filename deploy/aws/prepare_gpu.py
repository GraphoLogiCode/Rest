"""Read-only GPU readiness report; optional quota request never launches resources."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ecs'))
from aws_client import AWS, AwsFailure

QUOTA = 'L-DB2E81BA'
INSTANCE = 'g6.2xlarge'


def prepare(aws, request_quota=False):
    identity = aws.account()  # Fail closed on a different account.
    spec = aws.call('ec2', 'describe-instance-types', {'InstanceTypes': [INSTANCE]})['InstanceTypes'][0]
    required = spec['VCpuInfo']['DefaultVCpus']
    quota = aws.call('service-quotas', 'get-service-quota', {'ServiceCode': 'ec2', 'QuotaCode': QUOTA})['Quota']
    history = aws.call('service-quotas', 'list-requested-service-quota-change-history-by-quota',
                       {'ServiceCode': 'ec2', 'QuotaCode': QUOTA})['RequestedQuotas']
    pending = [r for r in history if r['Status'] in ('PENDING', 'CASE_OPENED')]
    report = {'checkedAt': datetime.now(timezone.utc).isoformat(), 'account': identity['Account'],
              'region': 'us-east-2', 'instanceType': INSTANCE, 'requiredVcpus': required,
              'approvedVcpus': quota['Value'], 'quotaReady': quota['Value'] >= required,
              'pendingQuotaRequests': [{'id': r['Id'], 'status': r['Status'], 'desiredValue': r['DesiredValue']} for r in pending],
              'launched': False, 'paymentsEnabled': False,
              'remainingChecks': ['Administrator deployment permissions', 'Account GPU plan eligibility',
                                  'Current price, remaining credits and bounded shutdown window',
                                  'Private networking and SSM host role', 'Container build and real CUDA smoke test',
                                  'Authenticated HTTPS backend integration']}
    if request_quota and not report['quotaReady'] and not pending:
        try:
            result = aws.call('service-quotas', 'request-service-quota-increase',
                             {'ServiceCode': 'ec2', 'QuotaCode': QUOTA, 'DesiredValue': required})['RequestedQuota']
            report['quotaRequest'] = {'id': result['Id'], 'status': result['Status']}
        except AwsFailure as exc:
            report['quotaRequestError'] = exc.code
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile')
    parser.add_argument('--request-quota', action='store_true', help='Request only the 8-vCPU GPU quota; no instance launch')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = prepare(AWS(args.profile), args.request_quota)
    payload = json.dumps(result, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload)
    print(payload)
