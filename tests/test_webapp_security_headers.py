import pytest
from fastapi.testclient import TestClient
from webapp_server import app

def test_security_headers_and_health():
    client = TestClient(app)
    response = client.get('/health')
    assert response.status_code == 200
    assert response.headers.get('x-content-type-options') == 'nosniff'
    assert response.headers.get('referrer-policy') == 'strict-origin-when-cross-origin'
    assert response.headers.get('x-xss-protection') == '1; mode=block'
    data = response.json()
    assert data['app'] == 'CLIN'
    assert data['status'] == 'ok'
