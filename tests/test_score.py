"""Tests for score calculation and the score field in API responses."""

import pytest
from app import create_app
from session_manager import calculate_score, get_session


@pytest.fixture
def client():
    with create_app({"TESTING": True}).test_client() as c:
        yield c


def test_win_score_formula():
    # 1000 + 50 * 11 questions left + 100 * 3 unused strikes
    assert calculate_score("won", 11, 0) == 1000 + 550 + 300


def test_win_with_strikes_used():
    assert calculate_score("won", 0, 2) == 1000 + 0 + 100


def test_win_all_strikes_used_is_still_base_plus_questions():
    assert calculate_score("won", 5, 3) == 1000 + 250


def test_loss_scores_zero():
    assert calculate_score("lost", 10, 0) == 0


def test_in_progress_scores_zero():
    assert calculate_score("in_progress", 15, 0) == 0


def test_negative_inputs_are_clamped():
    assert calculate_score("won", -3, 5) == 1000


def test_state_endpoint_reports_score(client):
    sid = client.post("/api/start", json={"case_id": "case_01"}).get_json()["session_id"]
    assert client.get(f"/api/state/{sid}").get_json()["score"] == 0

    s = get_session(sid)
    s.update(status="won", game_over=True, questions_left=12, strikes=1)
    assert client.get(f"/api/state/{sid}").get_json()["score"] == 1000 + 600 + 200


def test_ask_response_has_score(client):
    sid = client.post("/api/start", json={"case_id": "case_01"}).get_json()["session_id"]
    res = client.post("/api/ask", json={"session_id": sid, "question": "Where were you?"})
    assert res.get_json()["score"] == 0
