import pytest
from app import create_app
from config import Config
from case_loader import load_all_cases, get_case, sanitize_case_for_client
from session_manager import create_session, get_session

@pytest.fixture
def client():
    app = create_app({"TESTING": True})
    with app.test_client() as client:
        yield client

def test_config_defaults():
    # MOCK_LLM is forced True by conftest.py for all test runs
    assert Config.MOCK_LLM is True
    # LLM_MODEL may be overridden by .env; just verify it's a non-empty string
    assert isinstance(Config.LLM_MODEL, str) and len(Config.LLM_MODEL) > 0
    assert Config.PORT == 5000

def test_case_loader():
    cases = load_all_cases()
    assert "case_01" in cases
    case = get_case("case_01")
    assert case["id"] == "case_01"
    assert "truth_sheet" in case
    assert "contradictions" in case
    
    # Check sanitize
    safe = sanitize_case_for_client(case)
    assert "truth_sheet" not in safe
    assert "contradictions" not in safe
    assert safe["id"] == "case_01"
    assert len(safe["evidence"]) > 0

def test_api_cases_no_leak(client):
    res = client.get("/api/cases")
    assert res.status_code == 200
    data = res.get_json()
    assert "cases" in data
    assert len(data["cases"]) >= 1
    
    # Verify NO secrets leaked anywhere in response
    res_str = res.get_data(as_text=True)
    assert "truth_sheet" not in res_str
    assert "contradictions" not in res_str
    assert "what_really_happened" not in res_str
    assert "why_it_conflicts" not in res_str

def test_api_start_session(client):
    res = client.post("/api/start", json={"case_id": "case_01"})
    assert res.status_code == 201
    data = res.get_json()
    assert "session_id" in data
    assert data["questions_left"] == 15
    assert data["pressure"] == 0
    assert data["strikes"] == 0
    assert data["status"] == "in_progress"
    assert "truth_sheet" not in data
    assert "contradictions" not in data

    # Verify session in memory
    session = get_session(data["session_id"])
    assert session is not None
    assert session["case_id"] == "case_01"

def test_api_start_invalid_case(client):
    res = client.post("/api/start", json={"case_id": "nonexistent_case"})
    assert res.status_code == 404
    data = res.get_json()
    assert "error" in data

def test_api_start_missing_case_id(client):
    res = client.post("/api/start", json={})
    assert res.status_code == 400
    data = res.get_json()
    assert "error" in data

def test_api_get_state(client):
    start_res = client.post("/api/start", json={"case_id": "case_01"})
    session_id = start_res.get_json()["session_id"]

    state_res = client.get(f"/api/state/{session_id}")
    assert state_res.status_code == 200
    state = state_res.get_json()
    assert state["session_id"] == session_id
    assert state["questions_left"] == 15
    assert state["pressure"] == 0
    assert state["strikes"] == 0
    assert "truth_sheet" not in state
    assert "contradictions" not in state
