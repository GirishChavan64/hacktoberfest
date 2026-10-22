# 🕵️ INTERROGATION ROOM — A Noir AI Detective Game

> *"The rain doesn't wash away sins in this town; it just makes the blood run darker."*

**INTERROGATION ROOM** is a gritty, atmospheric 1940s detective game powered by modern LLMs. As a precinct detective, you interrogate a criminal suspect who defends a carefully fabricated cover story. The server holds a hidden **truth sheet** that is never revealed to the client. Your objective is to cross-examine the suspect, trap them in their own lies, and present physical evidence to expose 3 fatal contradictions before your questions run out or the suspect's attorney walks them out the door.

---

## 🎯 How to Play

1. **Select a Case Dossier**: Choose from 3 distinct noir cases (*The Velvet Alibi*, *Poison in Neon*, or *The Harbor Ledger*).
2. **Interrogate the Suspect**: You have **15 questions** per case. Every question decrements your clock and adds a stamped statement (`[S1]`, `[S2]`...) to the police transcript.
3. **Inspect the Evidence Locker**: Examine forensic lab reports, crime scene plaster casts, receipts, and timestamped timeclock records.
4. **Present Contradictions**: Click **"⚠️ PRESENT CONTRADICTION"**:
   - Pick a recorded suspect statement (`[S1]`, `[S2]`...)
   - Pair it with an **Evidence Item** (`[E1]`-`[E5]`) OR a **Second Suspect Statement**
   - Type your logical deduction explaining the contradiction.
5. **The Impartial Judge**: An LLM judge evaluates your accusation against the secret truth sheet at temperature `0.0`:
   - **Valid Contradiction**: Increases suspect **PRESSURE** (`34%` &rarr; `67%` &rarr; `100%`).
   - **Invalid Accusation**: Incurs a **STRIKE** (3 strikes and your case is dismissed!).
6. **Scoring**: a win scores `1000 + 50 per question left + 100 per unused strike`; a loss scores 0. The end screen shows a **CASE CLOSED** result card with a **Copy result** button.
7. **Voice (optional)**: the header **VOICE** toggle reads suspect answers aloud with your browser's built-in speech (a different voice pitch per suspect). It is off by default, has a **MUTE** button, and stops when you send a new question.
8. **Win & Loss Conditions**:
   - 🏆 **WIN**: 3 valid contradictions force a full suspect confession!
   - ❌ **LOSE (Strikeout)**: 3 invalid accusations cause the suspect to clam up and walk.
   - ❌ **LOSE (Time Expired)**: 0 questions left before breaking the suspect.

---

## ⚡ Quickstart (Run in 3 Commands)

Works immediately with zero configuration or API keys via deterministic `MOCK_LLM=1`:

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Setup environment (defaults to deterministic zero-key MOCK_LLM mode)
cp .env.example .env

# 3. Start the interrogation server
python app.py
```

Open your browser at **`http://localhost:5000`** and begin your interrogation!

---

## 🔌 Switching LLM Providers

The engine is built on standard OpenAI-compatible endpoints. To switch from the deterministic mock to a live LLM, set `MOCK_LLM=0` in `.env`:

### 1. Groq (Default live provider, open-weight models)
```ini
MOCK_LLM=0
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_MODEL=openai/gpt-oss-120b
LLM_API_KEY=gsk_your_groq_api_key_here
```

### 2. OpenAI
```ini
MOCK_LLM=0
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
LLM_API_KEY=sk-your_openai_api_key_here
```

### 3. Together AI
```ini
MOCK_LLM=0
LLM_BASE_URL=https://api.together.xyz/v1
LLM_MODEL=meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo
LLM_API_KEY=your_together_api_key_here
```

### 4. Ollama (100% Local & Free)
```ini
MOCK_LLM=0
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL=llama3.1
LLM_API_KEY=ollama
```

### 5. Deterministic Mock (Zero external API, ideal for unit testing)
```ini
MOCK_LLM=1
```

Never commit `.env` — it is git-ignored. Set secrets only in your host's environment settings.

### 🧠 Suspect's Brain (model picker)

The case-select screen has a **Suspect's Brain** dropdown, and the game header shows
`Powered by open-weight model: <name>`. The choice applies to that session only (suspect and judge).

- `LLM_MODELS` — comma-separated allowed list
  (default `openai/gpt-oss-120b,qwen/qwen3.8-27b,openai/gpt-oss-20b`).
- `LLM_MODEL` — the default selection.
- `GET /api/models` returns `{"models": [...], "default": "..."}`.
- `POST /api/start` accepts an optional `"model"`; anything outside the allowed list returns `400`.
- Models that reject `reasoning_effort` are retried once without it.

When using a provider other than Groq, set `LLM_MODELS` to model names that provider serves.

---

## 🧬 Built with open-weight models

The suspect and the judge run on open-weight models served through [Groq](https://groq.com):

- **gpt-oss-120b** (`openai/gpt-oss-120b`) — default
- **qwen3.8-27b** (`qwen/qwen3.8-27b`)
- **gpt-oss-20b** (`openai/gpt-oss-20b`)

Any OpenAI-compatible endpoint works, including local Ollama.

---

## 🚀 Deployment

### DigitalOcean App Platform

1. **Deploy via GitHub**:
   - Push this repository to GitHub.
   - In DigitalOcean Cloud Console, navigate to **Apps** &rarr; **Create App**.
   - Select your GitHub repository.
   - DigitalOcean will automatically detect the `Procfile` or `Dockerfile`.
   - Set Environment Variables:
     - `LLM_API_KEY`: your provider key (mark it **Encrypted / Secret**)
     - `LLM_BASE_URL`: `https://api.groq.com/openai/v1`
     - `LLM_MODEL`: `openai/gpt-oss-120b`
     - `MOCK_LLM`: `0` (the Dockerfile defaults to `1`, so set this explicitly)
   - Click **Deploy**.

   **Important:** sessions are stored in memory, so run exactly **one** gunicorn worker
   (`--workers 1`, already set in the `Procfile` and `Dockerfile`) and one instance.
   Sessions are lost on restart. Debug mode is off unless `FLASK_DEBUG=1`.

### Docker Deployment

Run anywhere with Docker:

```bash
docker build -t interrogation-room .
docker run -p 5000:5000 -e MOCK_LLM=1 interrogation-room
```

---

## 📂 Project Architecture

```
interrogation-room/
├── app.py               # Flask factory & REST API endpoints
├── config.py            # Environment configuration & defaults
├── case_loader.py       # JSON case loader & client sanitization (Zero Secrets Leak)
├── session_manager.py   # In-memory session tracking, strikes, pressure, win/lose rules
├── llm.py               # Suspect persona synthesis, OpenAI client, temperature 0 judge
├── cases/               # Noir case dossiers (Truth sheet, cover story, evidence)
│   ├── case_01.json     # The Velvet Alibi (Vincent "Silky" Vance)
│   ├── case_02.json     # Poison in Neon (Dr. Julian Sterling)
│   └── case_03.json     # The Harbor Ledger ('Big Mike' Callahan)
├── static/              # Vanilla noir frontend (Zero build step)
│   ├── index.html       # Single-page dossier & interrogation room
│   ├── style.css        # Atmospheric noir styling, CRT scanlines, typography
│   └── app.js           # State machine, modal contradiction workflow, sound synthesizer
├── tests/               # Pytest suite
│   ├── test_api.py      # Master end-to-end integration & zero-leak assertions
│   └── test_m*.py       # Milestone verification unit tests
├── requirements.txt     # Python requirements
├── Procfile             # Production WSGI process definition
├── Dockerfile           # Multi-stage lightweight production image
├── LICENSE              # MIT License
└── HANDOFF.md           # Single source of truth for engineering status
```

---

## 🔒 Security & Anti-Cheat

- **Zero Secret Leaks**: The server sanitizes all case data sent to the client via `case_loader.sanitize_case_for_client()`. Neither the master `truth_sheet` nor the solution `contradictions` list is ever present in HTTP responses or client DOM.
- **Judge Robustness**: The judge prompt operates with temperature `0.0`, strict JSON schema output, markdown code fence stripping, and automatic 1-shot retry on bad output.
- **Session Isolation**: Each interrogation runs in an isolated session keyed by UUIDv4 in memory.

---

## 🧪 Testing

Run the automated suite (56 tests; always uses the deterministic mock, never a real API):

```bash
python -m pytest -q
```

---

## 📜 License

MIT License. See [LICENSE](LICENSE) for full details.


## Troubleshooting: "the suspect gives the same canned lines"

That means the game is in **mock mode** (no real AI). When you run `python app.py`, the last
startup line tells you:

- `MODE: MOCK ...` -> copy `.env.example` to `.env`, set `MOCK_LLM=0` and your `LLM_API_KEY`, restart.
- `MODE: LIVE - model=...` -> the real model is on. If a question fails you will see
  "The suspect is unavailable: <reason>" (wrong model name, bad key, rate limit) and no question is spent.

Models change on every provider. List what your key can use with:

    python -c "from dotenv import load_dotenv; import os; from openai import OpenAI; load_dotenv(); c=OpenAI(base_url=os.getenv('LLM_BASE_URL'), api_key=os.getenv('LLM_API_KEY')); print('\n'.join(sorted(m.id for m in c.models.list().data)))"
