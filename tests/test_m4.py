import pytest
from app import create_app
from case_loader import load_all_cases, get_case

@pytest.fixture
def client():
    app = create_app({"TESTING": True})
    with app.test_client() as client:
        yield client

def test_all_three_cases_loaded():
    cases = load_all_cases()
    assert len(cases) == 3
    assert set(cases.keys()) == {"case_01", "case_02", "case_03"}

def test_case_schemas():
    for case_id in ["case_01", "case_02", "case_03"]:
        case = get_case(case_id)
        assert case is not None
        assert case["id"] == case_id
        assert len(case["title"]) > 0
        assert len(case["blurb"]) > 0
        assert len(case["setting"]) > 0
        assert len(case["briefing"]) > 0
        
        # Suspect
        assert "name" in case["suspect"]
        assert "personality" in case["suspect"]
        assert "speech_style" in case["suspect"]

        # Truth sheet
        assert "what_really_happened" in case["truth_sheet"]
        assert len(case["truth_sheet"]["timeline"]) >= 4
        assert "secret" in case["truth_sheet"]

        # Cover story
        assert len(case["cover_story"]) > 0

        # Evidence (4-5 items)
        assert len(case["evidence"]) >= 4
        for ev in case["evidence"]:
            assert "id" in ev and "name" in ev and "description" in ev

        # Contradictions (4-5 items)
        assert len(case["contradictions"]) >= 4
        for c in case["contradictions"]:
            assert "id" in c and "description" in c and "why_it_conflicts" in c

def test_case_02_playthrough(client):
    start = client.post("/api/start", json={"case_id": "case_02"}).get_json()
    sid = start["session_id"]
    assert start["case"]["suspect"]["name"] == "Dr. Julian Sterling"

    # Ask a question
    ask_res = client.post("/api/ask", json={"session_id": sid, "question": "Where were you?"})
    assert ask_res.status_code == 200

    # 3 valid accusations
    c1 = client.post("/api/accuse", json={
        "session_id": sid, "quote_ids": ["S1"], "evidence_id": "E1",
        "explanation": "Audio wire spool proves speech was pre-recorded."
    }).get_json()
    assert c1["valid"] is True
    assert c1["contradiction_id"] == "C1"
    assert c1["pressure"] == 34

    c2 = client.post("/api/accuse", json={
        "session_id": sid, "quote_ids": ["S1"], "evidence_id": "E2",
        "explanation": "Thumbprint found on port decanter."
    }).get_json()
    assert c2["valid"] is True
    assert c2["contradiction_id"] == "C2"
    assert c2["pressure"] == 67

    c3 = client.post("/api/accuse", json={
        "session_id": sid, "quote_ids": ["S1"], "evidence_id": "E3",
        "explanation": "50ml sodium cyanide missing from your locked laboratory cabinet."
    }).get_json()
    assert c3["valid"] is True
    assert c3["contradiction_id"] == "C3"
    assert c3["pressure"] == 100
    assert c3["status"] == "won"
    assert c3["game_over"] is True

def test_case_03_playthrough(client):
    start = client.post("/api/start", json={"case_id": "case_03"}).get_json()
    sid = start["session_id"]
    assert start["case"]["suspect"]["name"] == "'Big Mike' Callahan"

    # 3 valid accusations
    c1 = client.post("/api/accuse", json={
        "session_id": sid, "quote_ids": [], "evidence_id": "E1",
        "explanation": "The waterlogged duplicate ledger proves $80,000 embezzlement."
    }).get_json()
    assert c1["valid"] is True
    assert c1["contradiction_id"] == "C1"

    c2 = client.post("/api/accuse", json={
        "session_id": sid, "quote_ids": [], "evidence_id": "E2",
        "explanation": "Foreman keycard magnetic timestamp opened Warehouse 3 at 11:05 PM."
    }).get_json()
    assert c2["valid"] is True
    assert c2["contradiction_id"] == "C2"

    c3 = client.post("/api/accuse", json={
        "session_id": sid, "quote_ids": [], "evidence_id": "E3",
        "explanation": "Boots were soaked with low-tide pier slime from Pier 14."
    }).get_json()
    assert c3["valid"] is True
    assert c3["contradiction_id"] == "C3"
    assert c3["pressure"] == 100
    assert c3["status"] == "won"

def test_all_cases_api_leak_prevention(client):
    cases_res = client.get("/api/cases").get_data(as_text=True)
    assert "truth_sheet" not in cases_res
    assert "contradictions" not in cases_res
    assert "what_really_happened" not in cases_res
    assert "why_it_conflicts" not in cases_res

    for case_id in ["case_01", "case_02", "case_03"]:
        start = client.post("/api/start", json={"case_id": case_id}).get_data(as_text=True)
        assert "truth_sheet" not in start
        assert "contradictions" not in start
        assert "what_really_happened" not in start
        assert "why_it_conflicts" not in start
