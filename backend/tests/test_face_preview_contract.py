"""Rest API -> private worker contract, using real auth/queue and a fake GPU only."""
import io
import json
from pathlib import Path
import sys
import time
from uuid import uuid4

import httpx
from fastapi.testclient import TestClient
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'ml/scenario-visualization'))
from cloud_api import create_app as worker_app
from job_worker import WorkerSettings
from src.main import create_app
from src.config import Settings
from src.visualization.client import ModelClient
from tests.conftest import SUPABASE_URL, SECRET, make_token


def test_authenticated_face_preview_contract(tmp_path):
    captured = []
    def render(folder, fields, cancel, progress, settings):
        captured.append(fields)
        progress(1, 1)
        output = folder / 'result'
        output.mkdir()
        path = output / 'illustration.png'
        Image.new('RGB', (128, 188), 'gray').save(path)
        return path

    token = 'private-test-token-never-use-in-production'
    worker = worker_app(WorkerSettings(tmp_path, token, device='mps'), runner=render)
    bridge = ModelClient('http://private-worker', token, transport=httpx.ASGITransport(app=worker))
    app = create_app(Settings(supabase_url=SUPABASE_URL, supabase_jwt_secret=SECRET), model_client=bridge)
    alice = {'Authorization': 'Bearer '+make_token(uuid4())}
    bob = {'Authorization': 'Bearer '+make_token(uuid4())}
    raw = io.BytesIO(); Image.new('RGB',(128,128)).save(raw,format='PNG')
    options = {'mode':'face-edit','face_box':[0,0,128,128], 'edit_box':[20,20,40,40], 'strength':0.15,'finish':'soft-light'}
    with TestClient(worker), TestClient(app) as client:
        def submit(headers, fields=options, key=None):
            return client.post('/v1/illustrations', headers={**headers,'Idempotency-Key':key or str(uuid4())},
                data={'consent':'true','options':json.dumps(fields)},
                files={'reference':('photo.png',raw.getvalue(),'image/png')})
        assert submit({}).status_code == 401
        assert submit(alice).status_code == 403
        assert client.put('/v1/consents/illustration',headers=alice,json={'version':'illustration-2026-10-11'}).status_code == 200
        # These inputs have no validated mapping to appearance and must not be silently used.
        for field in ('sleep_hours','mood','stress','connection','ingredients','product'):
            assert submit(alice,{**options,field:'test'}).status_code == 422
        request_key = str(uuid4())
        response = submit(alice,key=request_key)
        assert response.status_code == 202, response.text
        key = response.json()['id']; path = '/v1/jobs/'+key
        assert submit(alice,key=request_key).json()['id'] == key
        assert client.get(path,headers=bob).status_code == 404
        assert client.get(path+'/image',headers=bob).status_code == 404
        assert client.delete(path,headers=bob).status_code == 404
        for _ in range(100):
            status = client.get(path,headers=alice).json()
            if status['status'] in ('completed','failed'): break
            time.sleep(.01)
        assert status['status'] == 'completed'
        result = client.get(path+'/image',headers=alice)
        assert result.status_code == 200 and result.headers['content-type'] == 'image/png'
        assert result.headers['cache-control'] == 'no-store'
        assert len(captured) == 1 and captured[0]['mode'] == 'face-edit'
        assert not (tmp_path/key/'input.png').exists()
        assert client.delete('/v1/consents/illustration',headers=alice).status_code == 200
        assert client.get(path,headers=alice).status_code == 404
        assert not (tmp_path/key).exists()
        assert submit(alice).status_code == 403
