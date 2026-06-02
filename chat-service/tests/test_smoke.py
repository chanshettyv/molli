from app.main import app
from fastapi.testclient import TestClient


def test_healthz() -> None:
    client = TestClient(app)
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_added_to_space_returns_greeting() -> None:
    client = TestClient(app)
    resp = client.post("/", json={"type": "ADDED_TO_SPACE"})
    assert resp.status_code == 200
    assert "Molli" in resp.json()["text"]
