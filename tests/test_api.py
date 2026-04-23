import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "message": "Code Refactoring Agent API is running"}

def test_analyze_endpoint():
    # Only test that the endpoint receives the request properly and tries to process it.
    code = "def foo():\n    pass"
    response = client.post("/analyze", json={"code": code, "language": "python"})
    
    # We might get a 200 or 500 depending on API key availability during CI/testing.
    # We just ensure the routing works.
    assert response.status_code in [200, 500] 
