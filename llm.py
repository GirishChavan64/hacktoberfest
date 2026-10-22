import json
import logging
import os
import re
from typing import Dict, List, Optional, Tuple
from openai import OpenAI
from config import Config

logger = logging.getLogger(__name__)


class LLMUnavailable(Exception):
    """Raised when the real model cannot answer (wrong model name, bad key, rate limit...).
    The API turns this into a visible error instead of a fake canned reply."""


_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def _clean(text: str) -> str:
    """Strip reasoning tags some models (e.g. Qwen) put in the content."""
    return _THINK_RE.sub("", text or "").strip()


def _short_reason(e: Exception) -> str:
    msg = str(e)
    low = msg.lower()
    if "model_not_found" in low or "does not exist" in low:
        return "model not found for this API key - pick another model"
    if "401" in low or "invalid api key" in low or "authentication" in low:
        return "API key rejected - check LLM_API_KEY in .env"
    if "429" in low or "rate limit" in low:
        return "rate limit reached - wait a few seconds and retry"
    if "timed out" in low or "timeout" in low:
        return "the model took too long - try again"
    return msg[:160]


def _create_with_reasoning_fallback(client, *, reasoning_effort=None, **kwargs):
    """Call chat.completions.create; if the provider rejects the
    reasoning_effort parameter, retry once without it."""
    extra = {}
    if reasoning_effort:
        extra["reasoning_effort"] = reasoning_effort
    try:
        return client.chat.completions.create(**kwargs, **extra)
    except Exception as e:
        msg = str(e).lower()
        if extra and ("reasoning_effort" in msg or "unsupported" in msg
                      or "unknown parameter" in msg or "unrecognized" in msg):
            logger.warning(f"Provider rejected reasoning_effort ({e}); retrying without it.")
            return client.chat.completions.create(**kwargs)
        raise


# Case-specific deterministic replies for MOCK_LLM=1
MOCK_SUSPECT_REPLIES = {
    "case_01": [
        "I already told you, detective. I was at the Blue Note all night listening to sweet jazz. Paid my tab in crisp cash and minded my own business.",
        "Booth four has the best view in the house. I sat there from ten till two without leaving once. The waiter must have grease in his eyes if he says otherwise.",
        "A smudge on my silk cuff? Please. Must've brushed against some yellow cab's greasy fender on the way in. A gentleman doesn't track mud.",
        "My Packard stayed parked right on the boulevard under the neon lights. Anyone claiming they saw it by the docks is either blind or a liar.",
        "Frankie Morretti? Sure, I knew him from the tables, but I don't touch firearms. I'm a promoter, detective, not a street thug."
    ],
    "case_02": [
        "I was speaking before sixty esteemed members of the Chemical Society all evening. Science deals with empirical proof, detective, not your hysterical conjectures.",
        "The wine decanter? I haven't poured Beatrice a single glass in weeks. She enjoyed her evening port in private solitude.",
        "Sodium cyanide is kept under double lock in the faculty vault. Any discrepancy in our requisition logs is an accounting clerical error, nothing more.",
        "Union Station? How preposterous. A scholar of my standing travels by chartered limousine, not on dirty midnight locomotives.",
        "That silver dropper is for my prescription ophthalmic drops. If you contaminate it with your grubby fingers, I shall inform your commissioner."
    ],
    "case_03": [
        "I was sawing logs in my bunk from ten till dawn, copper. Ask any stevedore on the pier if Mike Callahan ever leaves his post.",
        "Those union books are locked in the safe and they're clean as Sunday morning church clothes. Jimmy was barking at ghosts.",
        "Warehouse Three? The bay doors were shut and locked tight all night. Nobody was moving freight in that storm.",
        "My boots got muddy yesterday morning working the high-tide dredge. A foreman works for his living, dick, unlike you.",
        "Every dockhand carries a cargo hook. Hook number seven's been hanging in my locker since Tuesday. You got nothing on me."
    ],
    "default": [
        "You're barking up the wrong tree, flatfoot. My story stands and you've got nothing on me.",
        "Check your facts, detective. I haven't lied about a single minute of my whereabouts.",
        "Is this the best the department can do? I know my rights, and I don't appreciate the harassment.",
        "I told you where I was and who I was with. Stop fishing for fairy tales in a dry pond."
    ]
}

MOCK_CONFESSIONS = {
    "case_01": "All right, damn you, turn off the light! Frankie was gonna break my legs over fifty grand! I took the Packard to the docks and put a slug in his chest. I'll sign whatever you want, just get me a glass of water.",
    "case_02": "Stop it! Shut up! She was going to drag my name through the mud and destroy my career over some trivial grant money! Yes, I dosed the port with five drops of cyanide. I'll sign your cursed statement, just stop that glaring light.",
    "case_03": "Alright! Back off, copper, before I tear this table in half! The rat found the ledger and wouldn't take his cut! I cracked his skull with the hook and dumped him in the harbor. Get the DA in here and make your deal!",
    "default": "Fine! You broke me. I lied about everything. I did it, okay? Hand me the pen, detective."
}

def build_suspect_system_prompt(case: dict, pressure: int, solved_contradictions: List[str]) -> str:
    """Build the system prompt for the LLM suspect."""
    suspect = case.get("suspect", {})
    name = suspect.get("name", "The Suspect")
    personality = suspect.get("personality", "Cagey, guarded, evasive.")
    style = suspect.get("speech_style", "Gruff 1940s noir tone.")
    cover_story = case.get("cover_story", "")

    # Tone guidelines based on pressure (0-100)
    if pressure >= 100:
        pressure_desc = "PRESSURE: 100/100 (BROKEN). You have been completely caught in your lies. Break down and confess to the crime in raw, exhausted detail."
    elif pressure >= 67:
        pressure_desc = "PRESSURE: 67-99 (CORNERED). You are sweating profusely, stammering, agitated, and desperately clutching at your unraveling cover story."
    elif pressure >= 34:
        pressure_desc = "PRESSURE: 34-66 (SHAKEN). You are snappy, defensive, voice trembling slightly, attempting to maintain your smug facade but clearly nervous."
    else:
        pressure_desc = "PRESSURE: 0-33 (CALM). You are confident, smooth, condescending, and casually dismissive of the detective's accusations."

    prompt = f"""You are roleplaying as {name} in a gritty 1940s noir interrogation room.

CHARACTER PROFILE:
- Personality: {personality}
- Speech Style: {style}

YOUR COVER STORY (You MUST aggressively defend this story unless Pressure is 100):
{cover_story}

CURRENT STATE:
{pressure_desc}
Caught Contradictions against you: {', '.join(solved_contradictions) if solved_contradictions else 'None yet.'}

RULES:
1. Stay in character 100% of the time. Never break character.
2. NEVER mention that you are an AI, LLM, or language model.
3. Keep your response short, punchy, and strictly UNDER 60 WORDS.
4. If Pressure is under 100, NEVER admit to the crime or reveal the hidden truth. Deny, deflect, or mock the detective's questions.
5. If Pressure is 100, confess your guilt and surrender.
"""
    return prompt.strip()

def get_suspect_reply(session: dict, question: str) -> str:
    """
    Generate suspect reply either via MOCK_LLM or OpenAI-compatible endpoint.
    """
    case = session["case"]
    case_id = session.get("case_id", "case_01")
    pressure = session.get("pressure", 0)

    if Config.MOCK_LLM:
        # Check if already won/pressure 100
        if pressure >= 100:
            return MOCK_CONFESSIONS.get(case_id, MOCK_CONFESSIONS["default"])

        # Keyword-based or cycling deterministic response
        q_lower = question.lower()
        if "cash" in q_lower or "card" in q_lower or "receipt" in q_lower or "pay" in q_lower or "tab" in q_lower:
            return "I always pay cash for my bourbon, detective. A gentleman doesn't leave paper trails on a quiet night out."
        elif "booth" in q_lower or "leave" in q_lower or "empty" in q_lower or "table" in q_lower or "waiter" in q_lower:
            return "Booth four was occupied by yours truly from 10 PM till two in the morning. If the waiter missed me, he was probably asleep on the job."
        elif "grease" in q_lower or "cuff" in q_lower or "sleeve" in q_lower or "stain" in q_lower:
            return "That smudge on my cuff? Must've caught it on a greasy cab door outside the lounge. A man can't control city grime."
        elif "tire" in q_lower or "packard" in q_lower or "car" in q_lower or "dock" in q_lower:
            return "My Packard was parked right on 5th Street in plain view. Anybody who claims they saw my car down by the docks has water on the brain."
        elif "morretti" in q_lower or "gun" in q_lower or "shoot" in q_lower or "debt" in q_lower or ".38" in q_lower:
            return "Frankie Morretti had a dozen enemies with bad tempers and short fuses. I'm a club promoter, flatfoot, not a hitman."
        else:
            # Cycle through canned replies
            canned = MOCK_SUSPECT_REPLIES.get(case_id, MOCK_SUSPECT_REPLIES["default"])
            idx = session.get("mock_statement_idx", 0)
            reply = canned[idx % len(canned)]
            session["mock_statement_idx"] = idx + 1
            return reply

    # Real LLM call
    try:
        client = OpenAI(
            base_url=Config.LLM_BASE_URL,
            api_key=Config.LLM_API_KEY or "dummy-key",
            timeout=30.0
        )

        system_prompt = build_suspect_system_prompt(case, pressure, session.get("solved_contradictions", []))

        # Build chat history from statements
        messages = [{"role": "system", "content": system_prompt}]
        for s in session.get("statements", [])[-4:]:  # keep last 4 statements for context
            messages.append({"role": "user", "content": s.get("question", "")})
            messages.append({"role": "assistant", "content": s.get("text", "")})
        messages.append({"role": "user", "content": question})

        # Use per-session model; fall back to global default
        model = session.get("model") or Config.LLM_MODEL
        effort = "low" if "gpt" in model.lower() else None

        response = _create_with_reasoning_fallback(
            client,
            reasoning_effort=effort,
            model=model,
            messages=messages,
            temperature=0.7,
            max_tokens=1500,
        )
        reply = _clean(response.choices[0].message.content)

        # Retry once on empty reply
        if not reply:
            logger.warning("Suspect LLM returned empty content; retrying once.")
            response = _create_with_reasoning_fallback(
                client,
                reasoning_effort=effort,
                model=model,
                messages=messages,
                temperature=0.7,
                max_tokens=1500,
            )
            reply = _clean(response.choices[0].message.content)

        return reply if reply else "I have nothing to say to that, detective."
    except Exception as e:
        logger.error(f"Error calling LLM for suspect reply: {e}")
        raise LLMUnavailable(_short_reason(e)) from e

def parse_judge_json(raw_text: str) -> Optional[dict]:
    """Parse judge response JSON, stripping markdown code fences."""
    cleaned = raw_text.strip()
    # Strip markdown code blocks if present
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    # Extract outermost JSON object if surrounded by extra text
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        cleaned = match.group(0)
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict) and "valid" in data:
            return {
                "valid": bool(data["valid"]),
                "contradiction_id": str(data["contradiction_id"]) if data.get("contradiction_id") and data["valid"] else None,
                "reason": str(data.get("reason", "Accusation evaluated."))
            }
    except Exception as e:
        logger.warning(f"Failed to parse judge JSON: {e}")
    return None

def build_judge_prompt(case: dict, quoted_statements: List[dict], evidence_item: Optional[dict], explanation: str) -> str:
    """Build judge prompt including the hidden truth sheet and master contradictions."""
    truth_sheet = case.get("truth_sheet", {})
    contradictions = case.get("contradictions", [])
    
    quotes_text = "\n".join([f"- [{s.get('id')}]: \"{s.get('text')}\"" for s in quoted_statements])
    evidence_text = f"[{evidence_item.get('id')}] {evidence_item.get('name')}: {evidence_item.get('description')}" if evidence_item else "None provided."
    contradictions_text = "\n".join([f"- {c.get('id')}: {c.get('description')} ({c.get('why_it_conflicts')})" for c in contradictions])
    timeline_text = "\n".join([f"- {t}" for t in truth_sheet.get("timeline", [])])

    prompt = f"""You are an impartial detective judge for an interrogation game.
Your task is to determine whether the detective has presented a VALID, FACTUAL CONTRADICTION in the suspect's lies.

HIDDEN TRUTH SHEET (Server Only):
What Really Happened: {truth_sheet.get('what_really_happened')}
Timeline:
{timeline_text}
Secret: {truth_sheet.get('secret')}

MASTER CONTRADICTIONS:
{contradictions_text}

THE DETECTIVE'S ACCUSATION:
Quoted Suspect Statements:
{quotes_text if quotes_text else 'None quoted.'}

Presented Evidence:
{evidence_text}

Detective's Explanation:
"{explanation}"

INSTRUCTIONS:
1. Determine if the detective's argument establishes a valid contradiction between the suspect's statements and the evidence or between two contradictory suspect statements.
2. If valid, match it to one of the MASTER CONTRADICTIONS (e.g. C1, C2, C3, C4, C5).
3. If invalid or grasping at straws, set valid to false and contradiction_id to null.
4. Output STRICT JSON ONLY. No markdown formatting, no commentary.

Required JSON format:
{{"valid": true, "contradiction_id": "C1", "reason": "Explanation in under 40 words"}}
or
{{"valid": false, "contradiction_id": null, "reason": "Explanation in under 40 words"}}
"""
    return prompt.strip()

def judge_accusation(
    session: dict,
    quote_ids: List[str],
    evidence_id: Optional[str],
    explanation: str
) -> dict:
    """
    Evaluate an accusation.
    Uses keyword matching for MOCK_LLM=1, or temperature=0 OpenAI call for real LLM.
    """
    case = session["case"]
    case_id = session.get("case_id", "case_01")
    contradictions = case.get("contradictions", [])

    # Gather quoted statements
    statements_map = {s["id"]: s for s in session.get("statements", [])}
    quoted_statements = [statements_map[qid] for qid in quote_ids if qid in statements_map]

    # Gather evidence
    evidence_map = {e["id"]: e for e in case.get("evidence", [])}
    evidence_item = evidence_map.get(evidence_id) if evidence_id else None

    # MOCK_LLM Evaluation
    if Config.MOCK_LLM:
        expl_lower = explanation.lower()
        
        matched_cid = None
        reason = ""

        # Case-specific evidence and keyword mapping
        if case_id == "case_01":
            if evidence_id == "E1" or any(w in expl_lower for w in ["receipt", "card", "tab", "paid by card"]):
                matched_cid = "C1"
                reason = "The bar tab receipt proves payment with a credit card, catching Vance lying about paying only in cash."
            elif evidence_id == "E2" or any(w in expl_lower for w in ["booth", "empty", "waiter", "unattended"]):
                matched_cid = "C2"
                reason = "The waitstaff logbook confirms Booth Four was empty between 11:00 PM and 12:35 AM, shattering his alibi."
            elif evidence_id == "E4" or any(w in expl_lower for w in ["grease", "cuff", "crane", "lubricant"]):
                matched_cid = "C3"
                reason = "Forensic tests link the grease on Vance's silk sleeve directly to North Dock crane lubricants."
            elif evidence_id == "E5" or any(w in expl_lower for w in ["tire", "packard", "treads", "tracks", "mud"]):
                matched_cid = "C4"
                reason = "Fresh tire tracks at the dock alley match Vance's Packard sedan, proving his car was at the murder scene."
            elif evidence_id == "E3" or any(w in expl_lower for w in ["coroner", "ballistics", ".38", "slug"]):
                matched_cid = "C5"
                reason = "Ballistics report proves Morretti was executed with a .38 caliber weapon."

        elif case_id == "case_02":
            if evidence_id == "E1" or any(w in expl_lower for w in ["reel", "audio", "wire", "speaker", "recording", "exit"]):
                matched_cid = "C1"
                reason = "The audio wire spool proves Sterling's speech was pre-recorded while he slipped out the service exit."
            elif evidence_id == "E2" or any(w in expl_lower for w in ["decanter", "port", "fingerprint", "thumbprint", "crystal"]):
                matched_cid = "C2"
                reason = "Sterling's latent thumbprint was discovered on the neck of the cyanide-laced port decanter."
            elif evidence_id == "E3" or any(w in expl_lower for w in ["cyanide", "inventory", "missing", "vault", "cabinet", "50ml"]):
                matched_cid = "C3"
                reason = "The university lab audit proves 50ml of sodium cyanide disappeared from Sterling's personal locked cabinet."
            elif evidence_id == "E4" or any(w in expl_lower for w in ["station", "ticket", "montreal", "train", "express"]):
                matched_cid = "C4"
                reason = "The Union Station passenger carbon proves Sterling purchased an overnight cash ticket to Montreal at 9:30 PM."
            elif evidence_id == "E5" or any(w in expl_lower for w in ["dropper", "silver", "prussic", "spectrometry", "bulb"]):
                matched_cid = "C5"
                reason = "Mass spectrometry confirms the silver dropper in Sterling's pocket contained concentrated prussic acid."

        elif case_id == "case_03":
            if evidence_id == "E1" or any(w in expl_lower for w in ["ledger", "payroll", "embezzle", "80,000", "pension", "dues"]):
                matched_cid = "C1"
                reason = "The waterlogged duplicate ledger proves Callahan embezzled $80,000 from union accounts."
            elif evidence_id == "E2" or any(w in expl_lower for w in ["keycard", "gate", "warehouse", "magnetic", "timestamp"]):
                matched_cid = "C2"
                reason = "The electronic punch record proves Callahan's master keycard accessed Warehouse 3 at 11:05 PM."
            elif evidence_id == "E3" or any(w in expl_lower for w in ["boot", "boots", "tide", "mud", "silt", "slime"]):
                matched_cid = "C3"
                reason = "Callahan's boots were soaked with low-tide silt and bryozoan slime found exclusively at Pier 14."
            elif evidence_id == "E4" or any(w in expl_lower for w in ["padlock", "hacksaw", "sawed", "severed", "outside"]):
                matched_cid = "C4"
                reason = "Forensics proves the shack padlock was sawed open from the exterior alleyway, disproving an unbroken inside lock."
            elif evidence_id == "E5" or any(w in expl_lower for w in ["hook", "cargo hook", "hair", "bone", "blood", "#7"]):
                matched_cid = "C5"
                reason = "The stevedore cargo hook in Callahan's locker bore O'Malley's hair and bone fragments."

        # Generic mock test keywords per instructions ("alibi", "time", "location", "contradiction", "lie")
        if not matched_cid and any(k in expl_lower for k in ["alibi", "time", "location", "contradiction", "lie"]):
            # Pick first unsolved contradiction
            solved = session.get("solved_contradictions", [])
            for c in contradictions:
                if c["id"] not in solved:
                    matched_cid = c["id"]
                    reason = f"Accusation successfully caught the suspect in a contradiction ({c['id']})."
                    break
            if not matched_cid and contradictions:
                matched_cid = contradictions[0]["id"]
                reason = "Contradiction verified against case evidence."

        if matched_cid:
            return {"valid": True, "contradiction_id": matched_cid, "reason": reason}
        else:
            return {
                "valid": False,
                "contradiction_id": None,
                "reason": "The accusation lacks corroborating evidence or fails to disprove the suspect's cover story."
            }

    # Real LLM call
    try:
        client = OpenAI(
            base_url=Config.LLM_BASE_URL,
            api_key=Config.LLM_API_KEY or "dummy-key",
            timeout=20.0
        )

        prompt = build_judge_prompt(case, quoted_statements, evidence_item, explanation)
        judge_system = "You are a precise, objective interrogation judge. Always reply with raw JSON."

        # Use per-session model; fall back to global default
        model = session.get("model") or Config.LLM_MODEL
        judge_effort = "medium" if "gpt" in model.lower() else None

        # Primary call at temperature 0
        response = _create_with_reasoning_fallback(
            client,
            reasoning_effort=judge_effort,
            model=model,
            messages=[
                {"role": "system", "content": judge_system},
                {"role": "user", "content": prompt}
            ],
            temperature=0.0,
            max_tokens=1500,
        )
        content = _clean(response.choices[0].message.content)

        if not content:
            logger.warning("Judge returned empty content on first attempt; retrying once.")

        parsed = parse_judge_json(content) if content else None

        # 1-shot retry on empty or bad JSON
        if not parsed:
            if content:
                logger.warning(f"Judge returned non-JSON response. Raw content: {content!r}")
            logger.warning("Retrying judge call with strict JSON prompt...")
            retry_messages = [
                {"role": "system", "content": "You must respond with valid JSON only: {\"valid\": bool, \"contradiction_id\": string|null, \"reason\": string}"},
            ]
            if content:
                retry_messages.append({"role": "user", "content": f"Reformat this assessment as strict JSON:\n{content}"})
            else:
                # Content was empty — re-send the full prompt
                retry_messages = [
                    {"role": "system", "content": judge_system},
                    {"role": "user", "content": prompt},
                ]
            retry_res = _create_with_reasoning_fallback(
                client,
                reasoning_effort=judge_effort,
                model=model,
                messages=retry_messages,
                temperature=0.0,
                max_tokens=1500,
            )
            retry_content = _clean(retry_res.choices[0].message.content)
            if not retry_content:
                logger.error("Judge returned empty content on retry as well.")
            else:
                logger.info(f"Judge retry raw content: {retry_content!r}")
            parsed = parse_judge_json(retry_content) if retry_content else None

        if parsed:
            return parsed

        # Both attempts failed to produce parseable JSON — do NOT penalise the player
        logger.error("Judge could not produce valid JSON after retry. Returning judge_error.")
        return {
            "judge_error": True,
            "valid": False,
            "contradiction_id": None,
            "reason": "The judge could not rule on this. Try again.",
        }

    except Exception as e:
        logger.error(f"Error in judge LLM call: {e}")

    # Network / API error — same safe no-penalty response
    return {
        "judge_error": True,
        "valid": False,
        "contradiction_id": None,
        "reason": "The judge could not rule on this. Try again.",
    }

