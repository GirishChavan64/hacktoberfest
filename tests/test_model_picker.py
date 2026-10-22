"""Tests for the Suspect's Brain model picker."""

import pytest
from unittest.mock import patch, MagicMock
from app import create_app
from session_manager import get_session
import llm as llm_module
from config import Config

ALLOWED = ["openai/gpt-oss-120b", "qwen/qwen3.8-27b", "openai/gpt-oss-20b"]


@pytest.fixture(autouse=True)
def _models():
    with patch.object(Config, "LLM_MODELS", ALLOWED), \
         patch.object(Config, "LLM_MODEL", "openai/gpt-oss-120b"):
        yield


@pytest.fixture
def client():
    with create_app({"TESTING": True}).test_client() as c:
        yield c


def _resp(text):
    choice = MagicMock()
    choice.message.content = text
    r = MagicMock()
    r.choices = [choice]
    return r


def test_models_endpoint_lists_allowed_and_default(client):
    data = client.get("/api/models").get_json()
    assert data["models"] == ALLOWED
    assert data["default"] == "openai/gpt-oss-120b"


def test_start_rejects_unknown_model(client):
    res = client.post("/api/start", json={"case_id": "case_01", "model": "evil/model"})
    assert res.status_code == 400
    assert "evil/model" in res.get_json()["error"]


def test_start_stores_chosen_model(client):
    res = client.post("/api/start", json={"case_id": "case_01", "model": "qwen/qwen3.8-27b"})
    assert res.status_code == 201
    data = res.get_json()
    assert data["model"] == "qwen/qwen3.8-27b"
    assert get_session(data["session_id"])["model"] == "qwen/qwen3.8-27b"


def test_start_without_model_uses_default(client):
    data = client.post("/api/start", json={"case_id": "case_01"}).get_json()
    assert data["model"] == "openai/gpt-oss-120b"


def test_ask_uses_session_model(client):
    sid = client.post("/api/start", json={"case_id": "case_01", "model": "qwen/qwen3.8-27b"}).get_json()["session_id"]
    with patch.object(Config, "MOCK_LLM", False), patch.object(llm_module, "OpenAI") as M:
        create = M.return_value.chat.completions.create
        create.return_value = _resp("I was home all night.")
        res = client.post("/api/ask", json={"session_id": sid, "question": "Where were you?"})
    assert res.status_code == 200
    assert create.call_args.kwargs["model"] == "qwen/qwen3.8-27b"
    assert "reasoning_effort" not in create.call_args.kwargs  # non-gpt model


def test_accuse_uses_session_model(client):
    sid = client.post("/api/start", json={"case_id": "case_01", "model": "openai/gpt-oss-20b"}).get_json()["session_id"]
    stmt = client.post("/api/ask", json={"session_id": sid, "question": "Where were you?"}).get_json()["statement_id"]
    with patch.object(Config, "MOCK_LLM", False), patch.object(llm_module, "OpenAI") as M:
        create = M.return_value.chat.completions.create
        create.return_value = _resp('{"valid": false, "contradiction_id": null, "reason": "no"}')
        client.post("/api/accuse", json={"session_id": sid, "quote_ids": [stmt],
                                         "evidence_id": None, "explanation": "You lied about the time."})
    assert create.call_args.kwargs["model"] == "openai/gpt-oss-20b"
    assert create.call_args.kwargs["reasoning_effort"] == "medium"


def test_reasoning_effort_rejected_retries_without_it(client):
    sid = client.post("/api/start", json={"case_id": "case_01"}).get_json()["session_id"]
    with patch.object(Config, "MOCK_LLM", False), patch.object(llm_module, "OpenAI") as M:
        create = M.return_value.chat.completions.create
        create.side_effect = [Exception("Unknown parameter: reasoning_effort"), _resp("Fine, I was home.")]
        res = client.post("/api/ask", json={"session_id": sid, "question": "Where were you?"})
    assert res.status_code == 200
    assert create.call_count == 2
    assert "reasoning_effort" in create.call_args_list[0].kwargs
    assert "reasoning_effort" not in create.call_args_list[1].kwargs
