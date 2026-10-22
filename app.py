import logging
from flask import Flask, jsonify, request, send_from_directory
from config import Config, describe_mode
from case_loader import load_all_cases, list_cases_safe
from session_manager import create_session, get_session, get_client_state, add_suspect_statement, apply_accusation_result, session_score
from llm import get_suspect_reply, judge_accusation, LLMUnavailable

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("interrogation_room")

def create_app(test_config=None) -> Flask:
    """Application factory for Interrogation Room."""
    app = Flask(__name__, static_folder="static", static_url_path="/static")
    
    if test_config:
        app.config.update(test_config)
    
    # Initialize cases on startup
    load_all_cases(Config.CASES_DIR)

    @app.route("/")
    def index():
        """Serve the single-page noir detective interface."""
        return send_from_directory(Config.STATIC_DIR, "index.html")

    @app.route("/api/cases", methods=["GET"])
    def get_cases():
        """
        List all available cases.
        Guaranteed: Truth sheet and contradictions never included.
        """
        cases = list_cases_safe()
        return jsonify({"cases": cases}), 200

    @app.route("/api/models", methods=["GET"])
    def get_models():
        """Return the list of selectable LLM models for the Suspect's Brain dropdown."""
        return jsonify({"models": Config.LLM_MODELS, "default": Config.LLM_MODEL}), 200

    @app.route("/api/start", methods=["POST"])
    def start_case():
        """
        Start an interrogation session for a given case_id.
        Payload: {"case_id": "case_01", "model": "<optional model name>"}
        If model is omitted, LLM_MODEL is used.
        """
        data = request.get_json(silent=True) or {}
        case_id = data.get("case_id")
        if not case_id:
            return jsonify({"error": "Missing 'case_id' in request body"}), 400

        # Validate optional model selection
        chosen_model = (data.get("model") or "").strip() or None
        if chosen_model and chosen_model not in Config.LLM_MODELS:
            allowed = ", ".join(Config.LLM_MODELS)
            return jsonify({"error": f"Unknown model '{chosen_model}'. Allowed: {allowed}"}), 400

        session = create_session(case_id, model=chosen_model)
        if not session:
            return jsonify({"error": f"Case '{case_id}' not found"}), 404

        client_state = get_client_state(session)
        return jsonify({
            "session_id": session["session_id"],
            "case": client_state["case"],
            "model": session["model"],
            "questions_left": session["questions_left"],
            "pressure": session["pressure"],
            "strikes": session["strikes"],
            "status": session["status"]
        }), 201

    @app.route("/api/ask", methods=["POST"])
    def ask_suspect():
        """
        Ask the suspect a question.
        Decrements question counter, records statement (S1, S2...), and returns suspect reply.
        """
        data = request.get_json(silent=True) or {}
        session_id = data.get("session_id")
        question = (data.get("question") or "").strip()

        if not session_id:
            return jsonify({"error": "Missing 'session_id'"}), 400
        if not question:
            return jsonify({"error": "Question cannot be empty"}), 400

        session = get_session(session_id)
        if not session:
            return jsonify({"error": f"Session '{session_id}' not found"}), 404

        if session.get("game_over"):
            return jsonify({
                "error": "Interrogation has ended",
                "game_over": True,
                "status": session["status"],
                "result_reason": session["result_reason"]
            }), 400

        if session["questions_left"] <= 0:
            return jsonify({
                "error": "No questions remaining",
                "game_over": True,
                "status": "lost",
                "result_reason": "Time ran out. The suspect walked free."
            }), 400

        # Generate suspect reply
        try:
            answer = get_suspect_reply(session, question)
        except LLMUnavailable as e:
            # Visible error, and the question is NOT spent
            return jsonify({"error": f"The suspect is unavailable: {e}"}), 502
        
        # Record statement and decrement question counter
        statement = add_suspect_statement(session, question, answer)

        return jsonify({
            "answer": answer,
            "statement_id": statement["id"],
            "questions_left": session["questions_left"],
            "pressure": session["pressure"],
            "game_over": session["game_over"],
            "status": session["status"],
            "result_reason": session["result_reason"],
            "score": session_score(session)
        }), 200

    @app.route("/api/accuse", methods=["POST"])
    def accuse_suspect():
        """
        Present a contradiction accusation.
        Payload: {
            "session_id": str,
            "quote_ids": list[str],
            "evidence_id": str|null,
            "explanation": str
        }
        """
        data = request.get_json(silent=True) or {}
        session_id = data.get("session_id")
        quote_ids = data.get("quote_ids") or []
        evidence_id = data.get("evidence_id")
        explanation = (data.get("explanation") or "").strip()

        if not session_id:
            return jsonify({"error": "Missing 'session_id'"}), 400
        if not explanation:
            return jsonify({"error": "Accusation explanation cannot be empty"}), 400
        if not quote_ids and not evidence_id:
            return jsonify({"error": "Must select at least one suspect quote or evidence item"}), 400

        session = get_session(session_id)
        if not session:
            return jsonify({"error": f"Session '{session_id}' not found"}), 404

        if session.get("game_over"):
            return jsonify({
                "error": "Interrogation has already concluded",
                "game_over": True,
                "status": session["status"],
                "result_reason": session["result_reason"]
            }), 400

        # Run judge LLM assessment
        verdict = judge_accusation(session, quote_ids, evidence_id, explanation)

        # Judge could not rule (empty/unparseable response) — no penalty, player retries free
        if verdict.get("judge_error"):
            return jsonify({
                "status": "judge_error",
                "reason": verdict.get("reason", "The judge could not rule on this. Try again."),
                "valid": False,
                "pressure": session["pressure"],
                "strikes": session["strikes"],
                "questions_left": session["questions_left"],
            }), 200

        # Update session state: pressure, strikes, win/loss
        outcome = apply_accusation_result(
            session,
            valid=verdict["valid"],
            contradiction_id=verdict.get("contradiction_id"),
            reason=verdict.get("reason", "")
        )

        return jsonify(outcome), 200

    @app.route("/api/state/<session_id>", methods=["GET"])
    def get_state(session_id: str):
        """Get the full safe interrogation session state."""
        session = get_session(session_id)
        if not session:
            return jsonify({"error": f"Session '{session_id}' not found"}), 404

        return jsonify(get_client_state(session)), 200

    @app.errorhandler(404)
    def handle_404(err):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Endpoint not found"}), 404
        return send_from_directory(Config.STATIC_DIR, "index.html")

    @app.errorhandler(500)
    def handle_500(err):
        logger.error(f"Internal server error: {err}")
        return jsonify({"error": "Internal server error"}), 500

    return app

if __name__ == "__main__":
    app = create_app()
    print(f"Interrogation Room running at http://{Config.HOST}:{Config.PORT}")
    print(describe_mode())
    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG)
