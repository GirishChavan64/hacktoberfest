import uuid
from typing import Dict, Optional
from case_loader import get_case, sanitize_case_for_client
from config import Config

# In-memory session store keyed by session_id
_SESSIONS: Dict[str, dict] = {}

TOTAL_QUESTIONS = 15
MAX_STRIKES = 3
CONTRADICTIONS_TO_WIN = 3

def calculate_score(status: str, questions_left: int, strikes: int) -> int:
    """Win = 1000 + 50 per question left + 100 per unused strike. Loss/in-progress = 0."""
    if status != "won":
        return 0
    unused_strikes = max(0, MAX_STRIKES - max(0, strikes))
    return 1000 + 50 * max(0, questions_left) + 100 * unused_strikes


def session_score(session: dict) -> int:
    return calculate_score(session["status"], session["questions_left"], session["strikes"])


def create_session(case_id: str, model: Optional[str] = None) -> Optional[dict]:
    """Create a new interrogation session for a specific case.

    Args:
        case_id: The case to load.
        model:   Optional per-session LLM model name (must be in Config.LLM_MODELS).
                 Falls back to Config.LLM_MODEL.
    """
    case = get_case(case_id)
    if not case:
        return None

    # Resolve the model: player choice → env default
    resolved_model = model or Config.LLM_MODEL

    session_id = str(uuid.uuid4())
    session = {
        "session_id": session_id,
        "case_id": case_id,
        "case": case,  # Raw server-side case data
        "model": resolved_model,  # LLM model used for this session
        "questions_left": TOTAL_QUESTIONS,
        "pressure": 0,
        "strikes": 0,
        "statements": [],  # List of {"id": "S1", "question": str, "text": str}
        "statement_counter": 0,
        "solved_contradictions": [],  # List of contradiction IDs successfully caught
        "status": "in_progress",  # "in_progress" | "won" | "lost"
        "game_over": False,
        "result_reason": None,
        "mock_statement_idx": 0,
    }
    _SESSIONS[session_id] = session
    return session

def get_session(session_id: str) -> Optional[dict]:
    """Retrieve an existing session by ID."""
    return _SESSIONS.get(session_id)

def add_suspect_statement(session: dict, question: str, answer_text: str) -> dict:
    """Register a new suspect statement in the session and decrement questions."""
    session["statement_counter"] += 1
    statement_id = f"S{session['statement_counter']}"
    
    statement = {
        "id": statement_id,
        "question": question,
        "text": answer_text
    }
    session["statements"].append(statement)
    session["questions_left"] = max(0, session["questions_left"] - 1)
    
    # Check if questions ran out without a confession
    if session["questions_left"] == 0 and session["status"] == "in_progress":
        session["status"] = "lost"
        session["game_over"] = True
        session["result_reason"] = "Your time has expired. The suspect's attorney arrived with a writ of habeas corpus and walked them out the door."

    return statement

def apply_accusation_result(session: dict, valid: bool, contradiction_id: Optional[str], reason: str) -> dict:
    """
    Apply the outcome of an accusation:
    - If valid and NEW contradiction: +pressure (+34 then +33 so 3 = 100). 3 valid = confession/win!
    - If valid but already caught: no extra pressure, explain to user.
    - If invalid: strike added (+1). 3 strikes = lose!
    """
    if valid and contradiction_id:
        if contradiction_id not in session["solved_contradictions"]:
            session["solved_contradictions"].append(contradiction_id)
            solved_count = len(session["solved_contradictions"])
            
            # 3 contradictions = 100% pressure
            if solved_count == 1:
                session["pressure"] = 34
            elif solved_count == 2:
                session["pressure"] = 67
            else:
                session["pressure"] = 100

            if solved_count >= CONTRADICTIONS_TO_WIN:
                session["status"] = "won"
                session["game_over"] = True
                session["result_reason"] = "The suspect shattered under the weight of their own lies and signed a full confession."
        else:
            reason = f"You already established this contradiction ({contradiction_id}). The suspect is already cornered on this point."
    else:
        session["strikes"] += 1
        if session["strikes"] >= MAX_STRIKES:
            session["status"] = "lost"
            session["game_over"] = True
            session["result_reason"] = "Three baseless accusations. The suspect sneers, clamming up completely while their counsel threatens a badge-revoking lawsuit."

    return {
        "valid": valid,
        "contradiction_id": contradiction_id,
        "reason": reason,
        "pressure": session["pressure"],
        "strikes": session["strikes"],
        "status": session["status"],
        "game_over": session["game_over"],
        "result_reason": session["result_reason"],
        "score": session_score(session)
    }

def get_client_state(session: dict) -> dict:
    """
    Produce a complete, safe client representation of the session.
    NEVER includes truth_sheet or master contradictions.
    """
    return {
        "session_id": session["session_id"],
        "case_id": session["case_id"],
        "case": sanitize_case_for_client(session["case"]),
        "model": session.get("model", ""),
        "questions_left": session["questions_left"],
        "pressure": session["pressure"],
        "strikes": session["strikes"],
        "statements": session["statements"],
        "solved_contradictions": session["solved_contradictions"],
        "status": session["status"],
        "game_over": session["game_over"],
        "result_reason": session["result_reason"],
        "score": session_score(session)
    }
