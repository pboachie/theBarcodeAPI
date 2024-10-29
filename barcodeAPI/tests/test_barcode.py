# tests/test_barcode.py
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# Has not been tested
def test_generate_barcode():
    response = client.get("/api/generate?data=123456")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"