"""End-to-end backend -> private worker using ASGI transport and a fake model."""
from pathlib import Path
import sys
import json
import time
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'ml/scenario-visualization'))
from cloud_api import create_app as worker_app
from job_worker import WorkerSettings
from test_cloud_api import TOKEN, OPTIONS, fake_runner, photo
from tests.conftest import make_token, SECRET, SUPABASE_URL
from src.config import Settings
from src.main import create_app
from src.storage import MemoryStore
from src.visualization.client import ModelClient


@pytest.fixture
def connected(tmp_path):
    worker = worker_app(WorkerSettings(tmp_path, TOKEN), runner=fake_runner)
    with TestClient(worker):
        proxy = ModelClient('http://worker', TOKEN, transport=httpx.ASGITransport(app=worker))
        store = MemoryStore()
        app = create_app(Settings(SUPABASE_URL, SECRET), store=store, model_client=proxy)
        with TestClient(app) as client:
            yield client, store


def auth(owner):
    return {'Authorization':'Bearer ' + make_token(owner)}


def upload(client, owner, **extra):
    return client.post('/v1/illustrations', headers={**auth(owner), 'Idempotency-Key':str(uuid4()), **extra},
                       data={'consent':'true','options':json.dumps(OPTIONS)}, files={'reference':('photo.png',photo(),'image/png')})


def test_authenticated_flow_and_revoke(connected):
    client, store = connected
    owner, other = uuid4(), uuid4()
    assert client.get('/v1/jobs').status_code == 401
    assert upload(client,owner).status_code == 403
    assert client.put('/v1/consents/illustration',headers=auth(owner),json={'version':'v1'}).status_code == 200
    result = upload(client,owner, **{'X-Rest-User-ID':str(other)})
    assert result.status_code == 202, result.text
    key = result.json()['id']
    for _ in range(100):
        job = client.get('/v1/jobs/'+key,headers=auth(owner)).json()
        if job['status'] == 'completed': break
        time.sleep(.01)
    assert job['status'] == 'completed'
    assert job['imageUrl'] == f'/v1/jobs/{key}/image'
    assert client.get(job['imageUrl'],headers=auth(owner)).headers['content-type'] == 'image/png'
    assert client.get(job['imageUrl'],headers=auth(other)).status_code == 404
    assert client.get(job['imageUrl']).status_code == 401
    exported = client.post('/v1/export',headers=auth(owner))
    assert exported.json()['illustration_jobs'][0]['id'] == key
    assert client.delete('/v1/consents/illustration',headers=auth(owner)).status_code == 200
    assert client.get('/v1/jobs/'+key,headers=auth(owner)).status_code == 404
    assert upload(client,owner).status_code == 403


def test_account_purge(connected):
    client, store = connected
    owner = uuid4()
    store.grant_consent(owner,'illustration','v1')
    assert upload(client,owner).status_code == 202
    response = client.delete('/v1/account',headers=auth(owner))
    assert response.status_code == 200
    assert response.json()['deleted']['illustration_jobs'] == 1
    assert client.get('/v1/jobs',headers=auth(owner)).json() == {'items':[]}


def test_unavailable_worker_blocks_privacy_success():
    async def down(request):
        return httpx.Response(503)
    proxy = ModelClient('http://worker',TOKEN,transport=httpx.MockTransport(down))
    store = MemoryStore()
    owner = uuid4()
    store.grant_consent(owner,'illustration','v1')
    with TestClient(create_app(Settings(SUPABASE_URL,SECRET),store=store,model_client=proxy)) as client:
        assert client.delete('/v1/account',headers=auth(owner)).status_code == 503
        assert client.delete('/v1/consents/illustration',headers=auth(owner)).status_code == 503
        assert store.active_consent(owner,'illustration') is not None
        assert upload(client,owner).status_code == 503


def test_cloud_disabled_and_config():
    with TestClient(create_app(Settings(SUPABASE_URL,SECRET))) as client:
        assert client.get('/v1/jobs',headers=auth(uuid4())).status_code == 503
    with pytest.raises(ValueError):
        Settings(SUPABASE_URL,model_service_url='http://worker')


def test_customer_usage_and_account_deletion(connected):
    client, store = connected
    owner, other = uuid4(), uuid4()
    store.grant_consent(owner, 'illustration', 'v1')
    key = upload(client, owner).json()['id']
    for _ in range(100):
        if client.get('/v1/jobs/' + key, headers=auth(owner)).json()['status'] == 'completed': break
        time.sleep(.01)
    assert client.get('/v1/billing/usage').status_code == 401
    own = client.get('/v1/billing/usage', headers={**auth(owner), 'X-Rest-User-ID': str(other)}).json()
    assert own['billingMode'] == 'tracking_only' and own['paymentsEnabled'] is False
    assert len(own['items']) == 1 and own['items'][0]['customerId'] == str(owner)
    assert client.get('/v1/billing/usage', headers=auth(other)).json()['items'] == []
    assert len(client.post('/v1/export', headers=auth(owner)).json()['illustration_usage']) == 1
    assert client.delete('/v1/account', headers=auth(owner)).status_code == 200
    assert client.get('/v1/billing/usage', headers=auth(owner)).json()['items'] == []
