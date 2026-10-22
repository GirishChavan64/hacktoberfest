import pytest
from app import create_app

@pytest.fixture
def client():
    app = create_app({"TESTING": True})
    with app.test_client() as client:
        yield client

def test_static_index_route(client):
    res = client.get("/")
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert "INTERROGATION ROOM" in html
    assert "SUSPECT PRESSURE" in html
    assert "QUESTIONS LEFT" in html
    assert "ACCUSATION STRIKES" in html
    assert "screen-case-select" in html
    assert "screen-interrogation" in html
    assert "screen-game-over" in html
    assert "accuse-modal" in html

def test_static_css_served(client):
    res = client.get("/static/style.css")
    assert res.status_code == 200
    css = res.get_data(as_text=True)
    assert "noir-theme" in css
    assert "--border-gold" in css
    assert "pressure-fill" in css

def test_static_js_served(client):
    res = client.get("/static/app.js")
    assert res.status_code == 200
    js = res.get_data(as_text=True)
    assert "startInterrogation" in js
    assert "handleAskQuestion" in js
    assert "handleAccusation" in js
    assert "triggerGameOver" in js
