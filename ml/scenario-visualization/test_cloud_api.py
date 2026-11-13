"""CPU-only service tests. The injected runner does not claim to test CUDA inference."""
from io import BytesIO
import json
import threading
import time
from uuid import uuid4

from fastapi.testclient import TestClient
from PIL import Image
import pytest

from cloud_api import create_app
from job_worker import JobQueue, WorkerSettings, JobError
from gpu_runtime import resolve_device, sample_memory, write_progress

TOKEN = 'test-internal-service-token-' + 'x' * 32
OPTIONS = {"mode": "face-edit", "face_box": [0, 0, 128, 128], "edit_box": [30, 50, 60, 80]}


def photo():
    stream = BytesIO()
    Image.new('RGB', (128, 128), '#cababc').save(stream, format='PNG')
    return stream.getvalue()


def fake_runner(folder, fields, cancel, progress, settings):
    progress(1, 4)
    if cancel.wait(0.02):
        raise RuntimeError('cancelled')
    out = folder / 'result'
    out.mkdir()
    Image.new('RGB', (128, 188), '#aabbcc').save(out / 'illustration.png')
    (out / 'private.log').write_text('private')
    progress(4, 4)
    return out / 'illustration.png'


def headers(owner=None, key=None):
    return {'Authorization': 'Bearer ' + TOKEN, 'X-Rest-User-ID': str(owner or uuid4()), 'Idempotency-Key': str(key or uuid4())}


def submit(client, auth, options=None, raw=None):
    return client.post('/jobs', headers=auth, data={'consent': 'true', 'options': json.dumps(options or OPTIONS)},
                       files={'reference': ('photo.png', raw or photo(), 'image/png')})


def terminal(client, auth, key):
    deadline = time.monotonic() + 4
    while time.monotonic() < deadline:
        response = client.get('/jobs/' + key, headers=auth)
        if response.status_code != 200 or response.json()['status'] in ('failed', 'completed'):
            return response
        time.sleep(.01)
    pytest.fail('job did not finish')


def test_auth_ownership_idempotency_cleanup(tmp_path):
    app = create_app(WorkerSettings(tmp_path, TOKEN), runner=fake_runner)
    with TestClient(app) as client:
        assert submit(client, {}).status_code == 401
        owner, other = headers(), headers()
        response = submit(client, owner)
        assert response.status_code == 202, response.text
        key = response.json()['id']
        assert submit(client, owner).json()['id'] == key
        assert submit(client, owner, {**OPTIONS, 'strength': .15}).status_code == 409
        assert client.get('/jobs/' + key, headers=other).status_code == 404
        assert client.get('/jobs/' + key + '/image', headers=other).status_code == 404
        result = terminal(client, owner, key).json()
        assert result['status'] == 'completed'
        assert result['progress'] == 100 and result['progressStage'] == 'denoising'
        assert set(p.name for p in (tmp_path / key).iterdir()) == {'illustration.png'}
        assert client.get('/jobs/' + key + '/image', headers=owner).headers['cache-control'] == 'no-store'
        assert client.delete('/jobs/' + key, headers=other).status_code == 404
        assert client.delete('/jobs', headers=owner).json()['deleted'] == 1
        assert not (tmp_path / key).exists()
        assert client.get('/jobs', headers=owner).json() == {'items': []}


@pytest.mark.parametrize('options,raw', [({**OPTIONS, 'face_box': [0,0,64,80]}, None),
    ({**OPTIONS, 'edit_box': [100,100,150,150]}, None), ({**OPTIONS, 'steps': True}, None),
    ({**OPTIONS, 'owner': str(uuid4())}, None), ({**OPTIONS, 'strength': 1.0}, None),
    ({'mode':'scene', 'scenario':'arbitrary prompt'}, None), (OPTIONS, b'not a photo')])
def test_invalid_input(tmp_path, options, raw):
    with TestClient(create_app(WorkerSettings(tmp_path, TOKEN), runner=fake_runner)) as client:
        assert submit(client, headers(), options, raw).status_code == 422


def test_limits_cancel_and_expiry(tmp_path):
    started = threading.Event()
    def slow(folder, fields, cancel, progress, settings):
        started.set()
        cancel.wait(4)
        raise RuntimeError('cancelled')
    app = create_app(WorkerSettings(tmp_path, TOKEN, max_pending=1, ttl=1), runner=slow)
    with TestClient(app) as client:
        auth = headers()
        key = submit(client, auth).json()['id']
        assert started.wait(1)
        assert submit(client, headers()).status_code == 429
        assert client.delete('/jobs/' + key, headers=auth).status_code == 204
        assert not (tmp_path / key).exists()
        assert client.get('/usage', headers=auth).json()['items'] == []
        auth = headers()
        key = submit(client, auth).json()['id']
        time.sleep(1.2)
        assert client.get('/jobs/' + key, headers=auth).status_code == 404
        app.state.queue.cleanup()
        assert not (tmp_path / key).exists()
        assert client.get('/usage', headers=auth).json()['items'] == []


def test_body_limit_and_consent(tmp_path):
    with TestClient(create_app(WorkerSettings(tmp_path, TOKEN), runner=fake_runner)) as client:
        auth = headers()
        assert client.post('/jobs', headers=auth, content=b'x' * (11*1024*1024+1)).status_code == 413
        assert client.post('/jobs', headers=auth, data={'consent':'false', 'options':json.dumps(OPTIONS)}, files={'reference':('x',photo())}).status_code == 422


def test_recovery_and_single_process_lock(tmp_path):
    settings = WorkerSettings(tmp_path, TOKEN)
    queue = JobQueue(settings, fake_runner)
    queue.start()
    with pytest.raises(RuntimeError, match='Only one worker'):
        JobQueue(settings).start()
    owner, key = str(uuid4()), str(uuid4())
    queue.close()
    import sqlite3
    with sqlite3.connect(tmp_path / 'jobs.sqlite3') as db:
        db.execute("INSERT INTO jobs(id,owner,request_key,fingerprint,fields,status,created,expires) VALUES(?,?,?,?,?,'running',?,?)",
                   (key,owner,str(uuid4()),'hash',json.dumps(OPTIONS),time.time(),time.time()+30))
    folder = tmp_path / key
    folder.mkdir()
    (folder / 'input.png').write_bytes(photo())
    queue = JobQueue(settings, fake_runner)
    queue.start()
    try:
        assert queue.status(owner,key)['status'] == 'failed'
        assert not folder.exists()
    finally:
        queue.close()


def test_gpu_boundary_and_atomic_progress(tmp_path):
    from types import SimpleNamespace as NS
    torch = NS(cuda=NS(is_available=lambda: True, synchronize=lambda:None,
                      max_memory_allocated=lambda:12, max_memory_reserved=lambda:20),
               backends=NS(mps=NS(is_available=lambda:False)))
    assert resolve_device(torch, 'auto') == 'cuda'
    stats = {}
    sample_memory(torch, 'cuda', stats)
    assert stats['cuda_peak_allocated_bytes'] == 12
    torch.cuda.is_available = lambda: False
    with pytest.raises(RuntimeError, match='CUDA unavailable'):
        resolve_device(torch, 'cuda')
    path = tmp_path / 'progress.json'
    write_progress(path,2,4)
    assert json.loads(path.read_text()) == {'completedSteps':2,'totalSteps':4}
    assert not path.with_suffix('.tmp').exists()


def test_photo_metadata_is_removed():
    from job_worker import validate_input
    image = Image.new('RGB',(128,128),'white')
    exif = Image.Exif()
    exif[270] = 'private photo description'
    stream = BytesIO()
    image.save(stream, format='PNG', exif=exif)
    normalized, _ = validate_input(stream.getvalue(), OPTIONS)
    saved = BytesIO()
    normalized.save(saved, format='PNG')
    assert not Image.open(BytesIO(saved.getvalue())).getexif()


def test_chunked_body_cannot_bypass_limit(tmp_path):
    with TestClient(create_app(WorkerSettings(tmp_path,TOKEN),runner=fake_runner)) as client:
        chunks = (b'x' * 1024 * 1024 for _ in range(12))
        assert client.post('/jobs',headers=headers(),content=chunks).status_code == 413


def test_usage_is_durable_owned_and_not_poll_driven(tmp_path):
    settings = WorkerSettings(tmp_path, TOKEN)
    owner, other = headers(), headers()
    with TestClient(create_app(settings, runner=fake_runner)) as client:
        key = submit(client, owner).json()['id']
        assert terminal(client, owner, key).json()['status'] == 'completed'
        assert submit(client, owner).json()['id'] == key
        assert client.get('/usage').status_code == 401
        assert client.get('/usage', headers=other).json()['items'] == []
        page = client.get('/usage', headers=owner).json()
        assert len(page['items']) == 1
        event = page['items'][0]
        assert event['eventId'] == key and event['quantity'] == 1
        assert event['runtimeMs'] >= 0 and event['customerId'] == owner['X-Rest-User-ID']
        assert client.get('/usage?limit=0', headers=owner).status_code == 422
        assert client.delete('/jobs/' + key, headers=owner).status_code == 204
        assert client.get('/usage', headers=owner).json() == page
    with TestClient(create_app(settings, runner=fake_runner)) as client:
        assert client.get('/usage', headers=owner).json() == page
        from export_usage import export_events
        exported = tmp_path / 'usage.jsonl'
        result = export_events(tmp_path / 'jobs.sqlite3', exported)
        assert result['events'] == 1 and result['delivered'] is False
        assert json.loads(exported.read_text())['eventId'] == key
        with pytest.raises(FileExistsError): export_events(tmp_path / 'jobs.sqlite3', exported)
        assert client.get('/usage?after=' + str(event['sequence']), headers=owner).json()['items'] == []
        assert client.delete('/usage', headers=other).json()['deleted'] == 0
        assert client.delete('/usage', headers=owner).json()['deleted'] == 1


def test_failed_generation_never_counts_usage(tmp_path):
    def fail(*args):
        raise RuntimeError('simulated GPU failure')
    with TestClient(create_app(WorkerSettings(tmp_path, TOKEN), runner=fail)) as client:
        owner = headers()
        key = submit(client, owner).json()['id']
        assert terminal(client, owner, key).json()['status'] == 'failed'
        assert client.get('/usage', headers=owner).json()['items'] == []
