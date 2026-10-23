from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_home_page_is_served():
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "<title>Transit AI – Electric Bus Feasibility Check</title>" in response.text


def test_page_has_banner_and_feedback_form():
    text = client.get("/").text
    assert "Proof of concept: figures are first-pass estimates from public data" in text
    assert 'id="feedback"' in text and 'fetch("/feedback"' in text
