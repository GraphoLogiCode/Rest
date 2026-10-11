"""AWS CLI wrapper: JSON uses a protected temporary file; secrets never enter argv or logs."""
import json
import re
import subprocess
import tempfile
import os
from pathlib import Path
HERE = Path(__file__).resolve().parent
SETTINGS = json.loads((HERE/'settings.json').read_text())

class AwsFailure(RuntimeError):
    def __init__(self, service, operation, code):
        self.code = code
        super().__init__(f'{service}:{operation} failed ({code}). No input values or credentials printed.')

class AWS:
    def __init__(self, profile=None, runner=subprocess.run):
        self.profile, self.runner = profile, runner

    def call(self, service, operation, body=None, extra=()):
        command=['aws'] + (['--profile',self.profile] if self.profile else []) + ['--region',SETTINGS['region'],'--no-cli-pager',service,operation,'--output','json',*extra]
        request_path = None
        try:
            if body is not None:
                descriptor, request_path = tempfile.mkstemp(prefix='rest-aws-request-', suffix='.json')
                os.chmod(request_path, 0o600)
                with os.fdopen(descriptor, 'w') as file:
                    json.dump(body, file)
                command += ['--cli-input-json','file://' + request_path]
            result=self.runner(command,text=True,capture_output=True)
        finally:
            if request_path: os.unlink(request_path)
        if result.returncode:
            match=re.search(r'An error occurred \(([^)]+)\)',result.stderr)
            code=match.group(1) if match else 'CLIOrAuthenticationError'
            raise AwsFailure(service,operation,code)
        return json.loads(result.stdout or '{}')

    def account(self):
        identity=self.call('sts','get-caller-identity')
        if identity['Account'] != SETTINGS['account']:
            raise RuntimeError('Unexpected AWS account; no changes made.')
        return identity
