# tests/test_usage.py
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# Has not been tested
def test_get_usage():
    response = client.get("/usage", headers={"Authorization": "Bearer test_token"})
    assert response.status_code == 200
    data = response.json()
    assert "requests_today" in data
    assert "requests_limit" in data
