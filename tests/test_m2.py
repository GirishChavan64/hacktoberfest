import pytest
from app import create_app
from session_manager import get_session

@pytest.fixture
def client():
    app = create_app({"TESTING": True})
    with app.test_client() as client:
        yield client

def test_ask_basic_flow(client):
    start_res = client.post("/api/start", json={"case_id": "case_01"})
    session_id = start_res.get_json()["session_id"]

    ask_res = client.post("/api/ask", json={
        "session_id": session_id,
        "question": "Where were you last night?"
    })
    assert ask_res.status_code == 200
    data = ask_res.get_json()
    assert data["statement_id"] == "S1"
    assert data["questions_left"] == 14
    assert data["pressure"] == 0
    assert data["game_over"] is False
    assert data["status"] == "in_progress"
    assert len(data["answer"]) > 0
    # Under 60 words check
    assert len(data["answer"].split()) <= 60

    # Verify statement persisted in session state
    state_res = client.get(f"/api/state/{session_id}")
    state = state_res.get_json()
    assert len(state["statements"]) == 1
    assert state["statements"][0]["id"] == "S1"
    assert state["statements"][0]["question"] == "Where were you last night?"
    assert state["statements"][0]["text"] == data["answer"]

def test_ask_multiple_statements_increment(client):
    start_res = client.post("/api/start", json={"case_id": "case_01"})
    session_id = start_res.get_json()["session_id"]

    res1 = client.post("/api/ask", json={"session_id": session_id, "question": "Question 1"})
    assert res1.get_json()["statement_id"] == "S1"
    assert res1.get_json()["questions_left"] == 14

    res2 = client.post("/api/ask", json={"session_id": session_id, "question": "Question 2"})
    assert res2.get_json()["statement_id"] == "S2"
    assert res2.get_json()["questions_left"] == 13

    res3 = client.post("/api/ask", json={"session_id": session_id, "question": "Question 3"})
    assert res3.get_json()["statement_id"] == "S3"
    assert res3.get_json()["questions_left"] == 12

def test_ask_exhaustion_loses_game(client):
    start_res = client.post("/api/start", json={"case_id": "case_01"})
    session_id = start_res.get_json()["session_id"]

    # Ask 15 questions
    for i in range(14):
        res = client.post("/api/ask", json={"session_id": session_id, "question": f"Q{i+1}"})
        assert res.status_code == 200
        assert res.get_json()["game_over"] is False

    # 15th question should deplete questions and trigger game over (loss)
    res15 = client.post("/api/ask", json={"session_id": session_id, "question": "Final Q"})
    assert res15.status_code == 200
    data = res15.get_json()
    assert data["questions_left"] == 0
    assert data["game_over"] is True
    assert data["status"] == "lost"
    assert data["result_reason"] is not None

    # Subsequent question must be rejected
    res16 = client.post("/api/ask", json={"session_id": session_id, "question": "After timeout"})
    assert res16.status_code == 400
    assert res16.get_json()["game_over"] is True

def test_ask_validation_errors(client):
    start_res = client.post("/api/start", json={"case_id": "case_01"})
    session_id = start_res.get_json()["session_id"]

    # Missing session_id
    r1 = client.post("/api/ask", json={"question": "Hello?"})
    assert r1.status_code == 400

    # Missing question
    r2 = client.post("/api/ask", json={"session_id": session_id, "question": ""})
    assert r2.status_code == 400

    # Nonexistent session
    r3 = client.post("/api/ask", json={"session_id": "fake-session", "question": "Hello?"})
    assert r3.status_code == 404

def test_mock_llm_keyword_triggers(client):
    start_res = client.post("/api/start", json={"case_id": "case_01"})
    session_id = start_res.get_json()["session_id"]

    # Asking about cash or receipt
    r_cash = client.post("/api/ask", json={"session_id": session_id, "question": "Did you pay in cash or with a card receipt?"})
    assert "cash" in r_cash.get_json()["answer"].lower()

    # Asking about grease on cuff
    r_grease = client.post("/api/ask", json={"session_id": session_id, "question": "What is that grease on your cuff?"})
    assert "cuff" in r_grease.get_json()["answer"].lower() or "grease" in r_grease.get_json()["answer"].lower()
