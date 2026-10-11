from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from src.config import Settings
from src.main import create_app
from src.storage import MemoryStore
from src import pilot


def test_managed_container_refuses_memory_or_illustrations(monkeypatch):
    monkeypatch.setattr(pilot.Settings, 'from_env', lambda: Settings(supabase_url='https://example.supabase.co'))
    with pytest.raises(RuntimeError, match='DATABASE_URL'): pilot.create_app()
    monkeypatch.setattr(pilot.Settings, 'from_env', lambda: Settings(supabase_url='https://example.supabase.co', database_url='unused', model_service_url='http://worker', model_service_token='x'*32))
    with pytest.raises(RuntimeError, match='disabled'): pilot.create_app()


def test_managed_origin_serves_ui_and_authenticated_api(tmp_path, monkeypatch):
    (tmp_path/'index.html').write_text('<h1>Test fixture</h1>')
    monkeypatch.setenv('REST_FRONTEND_DIR', str(tmp_path))
    settings=Settings(supabase_url='https://example.supabase.co', database_url='unused')
    monkeypatch.setattr(pilot.Settings, 'from_env', lambda: settings)
    monkeypatch.setattr(pilot, 'create_api', lambda config: create_app(config, store=MemoryStore()))
    with TestClient(pilot.create_app()) as client:
        assert 'Test fixture' in client.get('/').text
        assert client.get('/rest-api/healthz').status_code == 200
        assert client.get('/rest-api/v1/products').json()['total'] == 9
        assert client.get('/rest-api/v1/progress/photos').status_code == 401
