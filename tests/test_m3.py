import pytest
from app import create_app
from llm import parse_judge_json

@pytest.fixture
def client():
    app = create_app({"TESTING": True})
    with app.test_client() as client:
        yield client

def test_judge_json_parser():
    # Plain JSON
    j1 = parse_judge_json('{"valid": true, "contradiction_id": "C1", "reason": "Match"}')
    assert j1["valid"] is True
    assert j1["contradiction_id"] == "C1"

    # Markdown code fence with json
    j2 = parse_judge_json('```json\n{"valid": false, "contradiction_id": null, "reason": "Invalid"}\n```')
    assert j2["valid"] is False
    assert j2["contradiction_id"] is None

    # Text before and after
    j3 = parse_judge_json('Here is the verdict:\n{"valid": true, "contradiction_id": "C2", "reason": "Good"}\nHope this helps!')
    assert j3["valid"] is True
    assert j3["contradiction_id"] == "C2"

    # Garbage / invalid JSON
    j4 = parse_judge_json('Not a json at all')
    assert j4 is None

def test_accuse_valid_raises_pressure(client):
    start = client.post("/api/start", json={"case_id": "case_01"}).get_json()
    session_id = start["session_id"]

    # Accuse on cash vs card receipt
    res = client.post("/api/accuse", json={
        "session_id": session_id,
        "quote_ids": ["S1"],
        "evidence_id": "E1",
        "explanation": "He claimed he paid in cash, but the receipt shows he paid with a credit card."
    })
    assert res.status_code == 200
    data = res.get_json()
    assert data["valid"] is True
    assert data["contradiction_id"] == "C1"
    assert data["pressure"] == 34
    assert data["strikes"] == 0
    assert data["status"] == "in_progress"
    assert data["game_over"] is False

def test_accuse_three_valid_wins_game(client):
    start = client.post("/api/start", json={"case_id": "case_01"}).get_json()
    session_id = start["session_id"]
    # Ask a question first so S1 exists in the session
    client.post("/api/ask", json={"session_id": session_id, "question": "Where were you?"})

    # Contradiction 1
    r1 = client.post("/api/accuse", json={
        "session_id": session_id,
        "quote_ids": ["S1"],
        "evidence_id": "E1",
        "explanation": "Receipt proves card payment, not cash."
    })
    assert r1.get_json()["pressure"] == 34
    assert r1.get_json()["status"] == "in_progress"

    # Contradiction 2
    r2 = client.post("/api/accuse", json={
        "session_id": session_id,
        "quote_ids": ["S1"],
        "evidence_id": "E2",
        "explanation": "Waitstaff logbook proves Booth Four was empty between 11 PM and 12:35 AM."
    })
    assert r2.get_json()["pressure"] == 67
    assert r2.get_json()["status"] == "in_progress"

    # Contradiction 3
    r3 = client.post("/api/accuse", json={
        "session_id": session_id,
        "quote_ids": ["S1"],
        "evidence_id": "E4",
        "explanation": "Grease on his silk cuff matches dock freight crane lubricant."
    })
    data3 = r3.get_json()
    assert data3["valid"] is True
    assert data3["pressure"] == 100
    assert data3["status"] == "won"
    assert data3["game_over"] is True
    assert data3["result_reason"] is not None

    # Subsequent accuse after win should fail
    r4 = client.post("/api/accuse", json={
        "session_id": session_id,
        "quote_ids": ["S1"],
        "evidence_id": "E5",
        "explanation": "Tire tracks"
    })
    assert r4.status_code == 400

def test_accuse_invalid_adds_strikes_and_loss(client):
    start = client.post("/api/start", json={"case_id": "case_01"}).get_json()
    session_id = start["session_id"]

    # Strike 1
    r1 = client.post("/api/accuse", json={
        "session_id": session_id,
        "quote_ids": ["S1"],
        "evidence_id": None,
        "explanation": "You look like a criminal."
    })
    assert r1.status_code == 200
    d1 = r1.get_json()
    assert d1["valid"] is False
    assert d1["strikes"] == 1
    assert d1["status"] == "in_progress"

    # Strike 2
    r2 = client.post("/api/accuse", json={
        "session_id": session_id,
        "quote_ids": ["S1"],
        "evidence_id": None,
        "explanation": "I just don't like your tie."
    })
    assert r2.get_json()["strikes"] == 2
    assert r2.get_json()["status"] == "in_progress"

    # Strike 3 (Loss)
    r3 = client.post("/api/accuse", json={
        "session_id": session_id,
        "quote_ids": ["S1"],
        "evidence_id": None,
        "explanation": "You are guilty because I said so."
    })
    d3 = r3.get_json()
    assert d3["valid"] is False
    assert d3["strikes"] == 3
    assert d3["status"] == "lost"
    assert d3["game_over"] is True

def test_accuse_repeat_contradiction(client):
    start = client.post("/api/start", json={"case_id": "case_01"}).get_json()
    session_id = start["session_id"]
    # Ask a question first so S1 exists in the session
    client.post("/api/ask", json={"session_id": session_id, "question": "Where were you?"})

    # First time
    r1 = client.post("/api/accuse", json={
        "session_id": session_id,
        "quote_ids": ["S1"],
        "evidence_id": "E1",
        "explanation": "Receipt proves card payment."
    })
    assert r1.get_json()["pressure"] == 34

    # Repeat
    r2 = client.post("/api/accuse", json={
        "session_id": session_id,
        "quote_ids": ["S1"],
        "evidence_id": "E1",
        "explanation": "Receipt proves card payment again."
    })
    assert r2.status_code == 200
    d2 = r2.get_json()
    # Should not add extra pressure or strikes
    assert d2["pressure"] == 34
    assert d2["strikes"] == 0
    assert "already" in d2["reason"].lower()

def test_accuse_validation_errors(client):
    start = client.post("/api/start", json={"case_id": "case_01"}).get_json()
    session_id = start["session_id"]

    # Missing session_id
    assert client.post("/api/accuse", json={"explanation": "test"}).status_code == 400

    # Missing explanation
    assert client.post("/api/accuse", json={"session_id": session_id, "explanation": ""}).status_code == 400

    # Missing both quote_ids and evidence_id
    assert client.post("/api/accuse", json={"session_id": session_id, "explanation": "test"}).status_code == 400
