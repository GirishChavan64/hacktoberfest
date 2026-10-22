# HANDOFF.md — Interrogation Room

## Project Summary
"INTERROGATION ROOM" is a noir detective game where a detective interrogates an AI suspect (an LLM playing a character with a secret cover story containing lies). The server holds a hidden truth sheet that is never sent to the client. The player wins by catching contradictions:
- 15 questions per case.
- "Present Contradiction": player picks a suspect quote plus a second quote or an evidence item, and types an explanation.
- A judge LLM checks the accusation against the truth sheet and contradictions list, returning JSON: `{"valid": bool, "contradiction_id": string|null, "reason": string}`.
- Each valid NEW contradiction increases pressure (+33 or +34, reaching 100 on 3 valid contradictions).
- 3 valid contradictions = suspect confesses (WIN).
- 3 invalid accusations = strike out (LOSE).
- 0 questions remaining before confession = time runs out (LOSE).
- 3 rich noir cases in `cases/`.
- Frontend: Single-page noir detective interface with dark tones (#0a0a0a), typewriter aesthetics, police report dossier, mobile friendly, no build step.

## How to Run + Env Vars
### Quickstart (3 commands)
```bash
pip install -r requirements.txt
cp .env.example .env
python app.py
```
Open `http://127.0.0.1:5000` in your browser.

### Environment Variables
| Variable | Description | Default |
|---|---|---|
| `LLM_BASE_URL` | OpenAI-compatible API base URL | `https://api.groq.com/openai/v1` |
| `LLM_API_KEY` | API key for LLM provider (not needed if MOCK_LLM=1) | `""` |
| `LLM_MODEL` | LLM model identifier | `openai/gpt-oss-120b` |
| `MOCK_LLM` | Enable canned deterministic replies for zero-key testing | `1` |
| `PORT` | Web server port | `5000` |
| `HOST` | Web server host | `0.0.0.0` |

## Key Decisions
1. **Zero Secret Leaks**: The truth sheet and master contradiction solutions are server-only. `case_loader.sanitize_case_for_client()` strips `truth_sheet` and `contradictions` list before sending case data to client.
2. **Determinism via MOCK_LLM**: When `MOCK_LLM=1` (default), suspect replies cycle through character statements with keyword sensitivity, and the judge analyzes keywords in accusations against contradiction definitions for reproducible unit and end-to-end testing without external API calls or keys.
3. **Robust Judge Parser**: Strip markdown code fences (` ```json `), enforce temperature 0, parse JSON with 1-shot retry on syntax error, and gracefully fall back to `{"valid": false, "reason": "..."}` on bad LLM output or connection errors.
4. **Clean Session Architecture**: In-memory sessions keyed by UUIDv4, tracking question count (starts at 15), statements history (`S1`, `S2`...), strikes (max 3), pressure (0 to 100), discovered contradictions, and game status.
5. **Vanilla Noir Frontend**: Single static bundle with retro typewriter suspect logs, amber/gold accents, stamped evidence dossiers, modal accusation workflow, and pressure gauges without requiring node/npm build tools.

## Milestone Checklist
- [x] M0: skeleton + git init + HANDOFF.md + .gitignore + MIT LICENSE
- [x] M1: config, MOCK_LLM, case loader, sessions, /api/cases, /api/start
- [x] M2: /api/ask with suspect prompt and question counter
- [x] M3: /api/accuse with judge, pressure, strikes, win/lose
- [x] M4: write all 3 cases
- [x] M5: frontend: case select, chat, evidence panel, pressure bar, counters, contradiction modal, win/lose screens
- [x] M6: pytest passing with MOCK_LLM=1 (session flow, judge JSON parsing, truth sheet never leaks)
- [x] M7: README, Procfile/Dockerfile
- [x] M8: polish: loading states, animations, error messages

## File Map
- `app.py`: Flask application factory (`create_app`), routing (`/`, `/api/cases`, `/api/start`, `/api/ask`, `/api/accuse`, `/api/state/<id>`), error handlers
- `config.py`: Environment configuration and loading
- `case_loader.py`: Server-side JSON case loader and client-sanitization
- `session_manager.py`: In-memory session tracking, game rules (strikes, pressure, win/lose)
- `llm.py`: Suspect prompt synthesis, deterministic mock generator, judge evaluation with JSON parser and code fence stripping
- `cases/`: JSON case definitions
  - `cases/case_01.json`: The Velvet Alibi (Vincent "Silky" Vance)
  - `cases/case_02.json`: Poison in Neon (Dr. Julian Sterling)
  - `cases/case_03.json`: The Harbor Ledger ('Big Mike' Callahan)
- `static/`: Static frontend assets
  - `static/index.html`: Noir interrogation room interface with 3 main screens and modal
  - `static/style.css`: Noir aesthetic (#0a0a0c background, #c9a227 gold accents, scanlines, responsive)
  - `static/app.js`: Interrogation state machine, audio synthesizer, modal forms, transcript feed
- `tests/`: Automated test suite
  - `tests/test_m0.py`: Verification of test runner and skeleton
  - `tests/test_m1.py`: Unit tests for config, case loader, sanitize, /api/cases, /api/start, /api/state
  - `tests/test_m2.py`: Unit tests for /api/ask, question counter, statements, game over on exhaustion
  - `tests/test_m3.py`: Unit tests for /api/accuse, judge parser, pressure increments, strikes, win/loss
  - `tests/test_m4.py`: Schema validation, playthrough tests for cases 1, 2, and 3, and zero-leak verification
  - `tests/test_m5.py`: Verification of frontend assets and static route serving
  - `tests/test_api.py`: Master end-to-end integration suite (full win/loss flows, judge edge cases, zero-leak validation)
- `README.md`: Comprehensive guide (game rules, quickstart, multi-provider setup, DigitalOcean / Docker deploy)
- `Procfile`: Gunicorn production process definition
- `Dockerfile`: Multi-stage lightweight production container
- `.dockerignore`: Container ignore rules
- `requirements.txt`: Python package requirements
- `.env.example`: Safe template environment file with MOCK_LLM=1
- `.env`: Local active configuration
- `.gitignore`: Version control ignores
- `LICENSE`: MIT License
- `HANDOFF.md`: Single source of truth for project state

## LAST COMPLETED ACTION
Upgrades finished: model picker, suspect voice (speechSynthesis, frontend only), scoring + CASE CLOSED result card (server-side `calculate_score`). Stray git helper files removed. 56 tests pass with MOCK_LLM=1. Rollback point: `git tag v1-working` (before voice and scoring).

## NEXT ACTION
2. Owner creates the GitHub repo and pushes. Then deploy to DigitalOcean App Platform (one worker, one instance).

## Known Bugs
None.

## Resume Instructions
All milestones M0-M8 plus the model picker are complete and tested. Server is ready to run via `python app.py`.

## Changelog
- 2026-10-22: M0 completed: setup repository, license, gitignore, pytest environment, and HANDOFF documentation.
- 2026-10-22: M1 completed: config, case loader, safe sanitization, session management, /api/cases, /api/start, and test suite.
- 2026-10-22: M2 completed: suspect prompt generation, deterministic mock replies, /api/ask endpoint with question counter and statement IDs.
- 2026-10-22: M3 completed: judge LLM logic, accusation evaluation, pressure/strike updates, win/loss conditions.
- 2026-10-22: M4 completed: wrote 3 complete noir cases with rich evidence and contradiction webs, verified test playthroughs.
- 2026-10-22: M5 completed: built full noir detective frontend (HTML/CSS/JS) with audio feedback, modal contradiction workflow, and responsive layout.
- 2026-10-22: M6 completed: comprehensive test suite passing 35/35 with zero-leak verification and full end-to-end assertions.
- 2026-10-22: M7 completed: comprehensive README, Procfile, Dockerfile, .dockerignore.
- 2026-10-22: M8 completed: UI polish (typing indicators, typewriter animation, pulse highlights, evidence hints, Ctrl+Enter shortcuts, error handling).
- 2026-10-22: Bug fix: judge empty-content → judge_error (no strike). max_tokens→1500, reasoning_effort params, suspect retry, conftest MOCK_LLM=1 override, 41 tests passing.

- 2026-10-22: Fix: .env now overrides shell env (override=True); startup prints MODE: MOCK/LIVE; failed model calls return a visible 502 error instead of a canned reply (question not spent); default model gpt-oss-120b; Qwen <think> tags stripped; test_llm_unavailable.py added.
