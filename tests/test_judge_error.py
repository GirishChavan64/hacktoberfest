"""
Tests for the judge_error path: when the judge LLM returns empty or
unparseable content, /api/accuse must NOT add a strike, must NOT mark valid,
and must return status="judge_error" with a human-readable reason.
"""

import pytest
from unittest.mock import patch, MagicMock, PropertyMock
from app import create_app
from session_manager import get_session
import llm as llm_module
from config import Config


@pytest.fixture
def client():
    app = create_app({"TESTING": True})
    with app.test_client() as c:
        yield c


def _start_session(client, case_id="case_01"):
    """Start a session and ask one question so we have a statement ID."""
    res = client.post("/api/start", json={"case_id": case_id})
    assert res.status_code == 201
    sid = res.get_json()["session_id"]
    ask = client.post("/api/ask", json={"session_id": sid, "question": "Where were you?"})
    assert ask.status_code == 200
    stmt_id = ask.get_json()["statement_id"]
    return sid, stmt_id


def _make_accuse_payload(sid, stmt_id, evidence_id=None):
    return {
        "session_id": sid,
        "quote_ids": [stmt_id],
        "evidence_id": evidence_id,
        "explanation": "The alibi is a lie — time and location don't match.",
    }


def _mock_openai_response(content: str):
    """Return a MagicMock that looks like an openai ChatCompletion response."""
    choice = MagicMock()
    choice.message.content = content
    resp = MagicMock()
    resp.choices = [choice]
    return resp


# ---------------------------------------------------------------------------
# 1. Empty string on first attempt, empty on retry → judge_error, no strike
# ---------------------------------------------------------------------------

def test_judge_empty_content_no_strike(client):
    """Both judge attempts return ''. Expect judge_error, strikes unchanged."""
    sid, stmt_id = _start_session(client)
    strikes_before = get_session(sid)["strikes"]
    pressure_before = get_session(sid)["pressure"]

    empty_resp = _mock_openai_response("")

    with patch.object(Config, "MOCK_LLM", False), \
         patch.object(llm_module, "OpenAI") as MockClient:
        instance = MockClient.return_value
        instance.chat.completions.create.return_value = empty_resp  # all calls return ""

        res = client.post("/api/accuse", json=_make_accuse_payload(sid, stmt_id))

    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "judge_error", f"Expected judge_error, got: {data}"
    reason_lower = data["reason"].lower()
    assert "judge could not rule" in reason_lower or "try again" in reason_lower

    session_after = get_session(sid)
    assert session_after["strikes"] == strikes_before, "Strike added on judge_error — bug"
    assert session_after["pressure"] == pressure_before, "Pressure changed on judge_error — bug"
    assert session_after["status"] == "in_progress"
    assert not session_after["game_over"]


# ---------------------------------------------------------------------------
# 2. Garbage JSON on first attempt, empty on retry → judge_error, no strike
# ---------------------------------------------------------------------------

def test_judge_garbage_json_no_strike(client):
    """First attempt returns unparseable text; retry returns empty. Expect judge_error."""
    sid, stmt_id = _start_session(client)
    strikes_before = get_session(sid)["strikes"]

    garbage_resp = _mock_openai_response("Sorry, I cannot assist with that.")
    empty_resp = _mock_openai_response("")

    with patch.object(Config, "MOCK_LLM", False), \
         patch.object(llm_module, "OpenAI") as MockClient:
        instance = MockClient.return_value
        instance.chat.completions.create.side_effect = [garbage_resp, empty_resp]

        res = client.post("/api/accuse", json=_make_accuse_payload(sid, stmt_id))

    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "judge_error", f"Expected judge_error, got: {data}"
    assert get_session(sid)["strikes"] == strikes_before, "Strike added on garbage JSON — bug"


# ---------------------------------------------------------------------------
# 3. Empty first, valid JSON on retry → normal invalid verdict (strike added)
# ---------------------------------------------------------------------------

def test_judge_empty_then_valid_json(client):
    """First call empty, retry returns valid JSON → result applied normally (invalid → +1 strike)."""
    sid, stmt_id = _start_session(client)
    strikes_before = get_session(sid)["strikes"]

    empty_resp = _mock_openai_response("")
    valid_resp = _mock_openai_response(
        '{"valid": false, "contradiction_id": null, "reason": "Does not match."}'
    )

    with patch.object(Config, "MOCK_LLM", False), \
         patch.object(llm_module, "OpenAI") as MockClient:
        instance = MockClient.return_value
        instance.chat.completions.create.side_effect = [empty_resp, valid_resp]

        res = client.post("/api/accuse", json=_make_accuse_payload(sid, stmt_id))

    assert res.status_code == 200
    data = res.get_json()
    assert data.get("status") != "judge_error", "Should have processed valid JSON from retry"
    assert get_session(sid)["strikes"] == strikes_before + 1, "Invalid accusation should cost a strike"


# ---------------------------------------------------------------------------
# 4. judge_error response must not leak truth_sheet or contradictions
# ---------------------------------------------------------------------------

def test_judge_error_no_secret_leak(client):
    """judge_error response body must not contain any hidden server secrets."""
    sid, stmt_id = _start_session(client)

    with patch.object(Config, "MOCK_LLM", False), \
         patch.object(llm_module, "OpenAI") as MockClient:
        instance = MockClient.return_value
        instance.chat.completions.create.return_value = _mock_openai_response("")

        res = client.post("/api/accuse", json=_make_accuse_payload(sid, stmt_id))

    body = res.get_data(as_text=True)
    for forbidden in ["truth_sheet", "what_really_happened", "why_it_conflicts"]:
        assert forbidden not in body.lower(), f"Secret '{forbidden}' leaked in judge_error response"


# ---------------------------------------------------------------------------
# 5. parse_judge_json returns None for empty / whitespace string (unit test)
# ---------------------------------------------------------------------------

def test_parse_judge_json_empty_string():
    from llm import parse_judge_json
    assert parse_judge_json("") is None
    assert parse_judge_json("   ") is None


# ---------------------------------------------------------------------------
# 6. Repeated judge_errors must not accumulate strikes or end the game
# ---------------------------------------------------------------------------

def test_judge_error_repeated_no_strike_accumulation(client):
    """Three consecutive judge_errors must leave strikes completely unchanged."""
    sid, stmt_id = _start_session(client)
    strikes_before = get_session(sid)["strikes"]

    with patch.object(Config, "MOCK_LLM", False), \
         patch.object(llm_module, "OpenAI") as MockClient:
        instance = MockClient.return_value
        instance.chat.completions.create.return_value = _mock_openai_response("")

        for i in range(3):
            res = client.post("/api/accuse", json=_make_accuse_payload(sid, stmt_id))
            data = res.get_json()
            assert data["status"] == "judge_error", f"Attempt {i+1}: expected judge_error, got {data}"

    session = get_session(sid)
    assert session["strikes"] == strikes_before, "Strikes accumulated from judge_errors — bug"
    assert not session["game_over"], "Game ended due to judge_errors — bug"
    assert session["status"] == "in_progress"
