"""Authenticated cloud smoke test; supply a test photo you are allowed to process."""
import argparse
import json
import os
from pathlib import Path
import time
from uuid import uuid4

import httpx


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--photo', type=Path, required=True)
    parser.add_argument('--face-box', type=int, nargs=4, required=True)
    parser.add_argument('--edit-box', type=int, nargs=4, required=True)
    parser.add_argument('--output', type=Path, default=Path('smoke-output.png'))
    args = parser.parse_args()
    key = None
    with httpx.Client(base_url=os.environ['REST_API_URL'].rstrip('/'),
                      headers={'Authorization':'Bearer ' + os.environ['REST_ACCESS_TOKEN']}, timeout=30) as client:
        response = client.put('/v1/consents/illustration',json={'version':'illustration-2026-10-11'})
        response.raise_for_status()
        options = {'mode':'face-edit','face_box':args.face_box,'edit_box':args.edit_box,'strength':.15}
        try:
            with args.photo.open('rb') as stream:
                response = client.post('/v1/illustrations', headers={'Idempotency-Key':str(uuid4())},
                    data={'consent':'true','options':json.dumps(options)}, files={'reference':('reference.png',stream)})
            response.raise_for_status()
            job = response.json()
            key = job['id']
            deadline = time.monotonic() + 360
            while job['status'] in ('queued','running'):
                if time.monotonic() > deadline:
                    raise TimeoutError('Job did not finish in six minutes')
                print(job['status'], job.get('completedSteps',''), job.get('totalSteps',''))
                time.sleep(2)
                response = client.get('/v1/jobs/' + key)
                response.raise_for_status()
                job = response.json()
            if job['status'] != 'completed':
                raise RuntimeError(job.get('error','Generation failed'))
            response = client.get(f'/v1/jobs/{key}/image')
            response.raise_for_status()
            args.output.write_bytes(response.content)
            print('Saved labeled illustration:',args.output)
        finally:
            if key:
                response = client.delete('/v1/jobs/' + key)
                response.raise_for_status()
                print('Temporary server job deleted.')


if __name__ == '__main__':
    main()
