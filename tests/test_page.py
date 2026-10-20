from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_home_page_is_served():
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "<title>Transit AI – Electric Bus Feasibility Check</title>" in response.text
