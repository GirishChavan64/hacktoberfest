"""When the real model fails, the player sees a visible error, not a fake canned reply."""
import pytest
from unittest.mock import patch
from app import create_app
from config import Config
import llm as llm_module


@pytest.fixture
def client():
    with create_app({"TESTING": True}).test_client() as c:
        yield c


def test_ask_returns_502_and_keeps_question_when_llm_fails(client):
    sid = client.post("/api/start", json={"case_id": "case_01"}).get_json()["session_id"]
    with patch.object(Config, "MOCK_LLM", False), \
         patch.object(llm_module, "OpenAI", side_effect=Exception("Error code: 404 model_not_found")):
        res = client.post("/api/ask", json={"session_id": sid, "question": "Where were you?"})
    assert res.status_code == 502
    assert "suspect is unavailable" in res.get_json()["error"]
    # the failed call must not spend a question
    state = client.get(f"/api/state/{sid}").get_json()
    assert state["questions_left"] == 15


def test_clean_strips_think_tags():
    assert llm_module._clean("<think>plan</think>Hello") == "Hello"
    assert llm_module._clean(None) == ""
