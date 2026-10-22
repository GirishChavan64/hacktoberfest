/**
 * INTERROGATION ROOM — Vanilla JavaScript Game Controller
 * Precision Noir Detective Experience
 */

(function () {
    "use strict";

    // Application State
    const state = {
        sessionId: null,
        caseId: null,
        caseData: null,
        questionsLeft: 15,
        pressure: 0,
        strikes: 0,
        statements: [],
        solvedContradictions: [],
        status: "in_progress",
        gameOver: false,
        resultReason: null,
        score: 0,
        model: "",
        pairingMode: "evidence" // 'evidence' | 'quote'
    };

    // DOM Element References
    const elements = {
        // Top status bar
        statsBar: document.getElementById("game-stats-bar"),
        pressureVal: document.getElementById("pressure-val"),
        pressureFill: document.getElementById("pressure-fill"),
        demeanorTag: document.getElementById("demeanor-tag"),
        questionsVal: document.getElementById("questions-val"),
        strikesContainer: document.getElementById("strikes-container"),
        btnBackCases: document.getElementById("btn-back-cases"),

        // Screens
        screenCaseSelect: document.getElementById("screen-case-select"),
        screenInterrogation: document.getElementById("screen-interrogation"),
        screenGameOver: document.getElementById("screen-game-over"),

        // Case select
        casesGrid: document.getElementById("cases-grid"),

        // Interrogation view
        currentCaseId: document.getElementById("current-case-id"),
        currentCaseTitle: document.getElementById("current-case-title"),
        currentSuspectName: document.getElementById("current-suspect-name"),
        currentCaseBriefing: document.getElementById("current-case-briefing"),
        currentCaseSetting: document.getElementById("current-case-setting"),
        transcriptFeed: document.getElementById("transcript-feed"),
        statementCounterBadge: document.getElementById("statement-counter-badge"),
        evidenceList: document.getElementById("evidence-list"),
        evidenceCountBadge: document.getElementById("evidence-count-badge"),
        suspectPersonality: document.getElementById("suspect-personality"),
        suspectStyle: document.getElementById("suspect-style"),
        suspectCoverStory: document.getElementById("suspect-cover-story"),

        // Form controls
        askForm: document.getElementById("ask-form"),
        questionInput: document.getElementById("question-input"),
        btnAsk: document.getElementById("btn-ask"),
        btnOpenAccuse: document.getElementById("btn-open-accuse"),

        // Accusation modal
        accuseModal: document.getElementById("accuse-modal"),
        accuseForm: document.getElementById("accuse-form"),
        btnModalClose: document.getElementById("btn-modal-close"),
        btnAccuseCancel: document.getElementById("btn-accuse-cancel"),
        btnAccuseSubmit: document.getElementById("btn-accuse-submit"),
        accuseQuote1: document.getElementById("accuse-quote-1"),
        accuseQuote2: document.getElementById("accuse-quote-2"),
        accuseEvidence: document.getElementById("accuse-evidence"),
        accuseExplanation: document.getElementById("accuse-explanation"),
        accuseFeedback: document.getElementById("accuse-feedback"),
        tabEvidence: document.getElementById("tab-evidence"),
        tabSecondQuote: document.getElementById("tab-second-quote"),
        pairingEvidenceContainer: document.getElementById("pairing-evidence-container"),
        pairingQuoteContainer: document.getElementById("pairing-quote-container"),

        // Game over screen
        gameOverStamp: document.getElementById("game-over-stamp"),
        gameOverTitle: document.getElementById("game-over-title"),
        gameOverBody: document.getElementById("game-over-body"),
        finalPressure: document.getElementById("final-pressure"),
        finalContradictions: document.getElementById("final-contradictions"),
        finalStrikes: document.getElementById("final-strikes"),
        finalQuestions: document.getElementById("final-questions"),
        btnReplayCase: document.getElementById("btn-replay-case"),
        btnSelectAnother: document.getElementById("btn-select-another"),

        // Utilities
        toast: document.getElementById("toast")
    };

    // Synthesized Web Audio Typewriter / Impact Sound Effect (Zero external dependencies)
    let audioCtx = null;
    function playSfx(type) {
        try {
            if (!audioCtx) {
                const AudioCtxClass = window.AudioContext || window.webkitAudioContext;
                if (AudioCtxClass) audioCtx = new AudioCtxClass();
            }
            if (!audioCtx) return;

            const now = audioCtx.currentTime;
            const osc = audioCtx.createOscillator();
            const gain = audioCtx.createGain();
            osc.connect(gain);
            gain.connect(audioCtx.destination);

            if (type === "typewriter") {
                // Short snappy typewriter key strike
                osc.type = "triangle";
                osc.frequency.setValueAtTime(800 + Math.random() * 400, now);
                gain.gain.setValueAtTime(0.08, now);
                gain.gain.exponentialRampToValueAtTime(0.001, now + 0.04);
                osc.start(now);
                osc.stop(now + 0.04);
            } else if (type === "valid") {
                // Brass chime for valid contradiction
                osc.type = "sine";
                osc.frequency.setValueAtTime(440, now);
                osc.frequency.exponentialRampToValueAtTime(880, now + 0.2);
                gain.gain.setValueAtTime(0.12, now);
                gain.gain.exponentialRampToValueAtTime(0.001, now + 0.4);
                osc.start(now);
                osc.stop(now + 0.4);
            } else if (type === "strike") {
                // Heavy dull thud for strike
                osc.type = "sawtooth";
                osc.frequency.setValueAtTime(140, now);
                osc.frequency.exponentialRampToValueAtTime(40, now + 0.25);
                gain.gain.setValueAtTime(0.2, now);
                gain.gain.exponentialRampToValueAtTime(0.001, now + 0.3);
                osc.start(now);
                osc.stop(now + 0.3);
            }
        } catch (e) {
            // Audio context policy safe ignore
        }
    }

    // Toast notifications
    let toastTimer = null;
    function showToast(msg) {
        elements.toast.textContent = msg;
        elements.toast.classList.remove("hidden");
        if (toastTimer) clearTimeout(toastTimer);
        toastTimer = setTimeout(() => {
            elements.toast.classList.add("hidden");
        }, 3500);
    }

    // =========================================================================
    // API SERVICE CALLS
    // =========================================================================

    async function loadModels() {
        const select = document.getElementById("model-select");
        if (!select) return;
        try {
            const res = await fetch("/api/models");
            const data = await res.json();
            select.innerHTML = "";
            (data.models || []).forEach(m => {
                const opt = document.createElement("option");
                opt.value = m;
                opt.textContent = m;
                if (m === data.default) opt.selected = true;
                select.appendChild(opt);
            });
        } catch (err) {
            console.error("Error loading models:", err);
            select.innerHTML = '<option value="">default</option>';
        }
    }

    async function loadCases() {
        try {
            const res = await fetch("/api/cases");
            const data = await res.json();
            if (data.cases) {
                renderCaseCards(data.cases);
            } else {
                elements.casesGrid.innerHTML = "<p>No active case files found.</p>";
            }
        } catch (err) {
            console.error("Error loading cases:", err);
            elements.casesGrid.innerHTML = `<div class="loading-spinner"><p>ERROR ACCESSING ARCHIVES: ${err.message}</p></div>`;
        }
    }

    async function startInterrogation(caseId) {
        try {
            const res = await fetch("/api/start", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    case_id: caseId,
                    model: (document.getElementById("model-select") || {}).value || undefined
                })
            });

            if (!res.ok) {
                const errData = await res.json();
                throw new Error(errData.error || "Failed to start case");
            }

            const data = await res.json();
            state.sessionId = data.session_id;
            state.caseId = caseId;
            state.caseData = data.case;
            const poweredBy = document.getElementById("powered-by");
            if (poweredBy && data.model) {
                poweredBy.textContent = "Powered by open-weight model: " + data.model;
                poweredBy.classList.remove("hidden");
            }
            state.questionsLeft = data.questions_left;
            state.pressure = data.pressure;
            state.strikes = data.strikes;
            state.statements = [];
            state.solvedContradictions = [];
            state.status = data.status || "in_progress";
            state.gameOver = false;
            state.score = 0;
            state.model = data.model || "";
            state.resultReason = null;

            setupInterrogationUI();
            switchScreen("interrogation");
        } catch (err) {
            console.error("Failed to start interrogation:", err);
            showToast(`Error starting case: ${err.message}`);
        }
    }

    // =========================================================================
    // SUSPECT VOICE (browser speechSynthesis, frontend only)
    // =========================================================================
    const voice = { enabled: false, muted: false };
    const VOICE_PROFILES = {
        case_01: { pitch: 0.8, rate: 0.92 },
        case_02: { pitch: 1.25, rate: 1.0 },
        case_03: { pitch: 0.6, rate: 0.85 }
    };
    const voiceSupported = "speechSynthesis" in window;

    function stopSpeaking() {
        if (voiceSupported) window.speechSynthesis.cancel();
    }

    function speakSuspect(text) {
        if (!voiceSupported || !voice.enabled || voice.muted || !text) return;
        stopSpeaking();
        const profile = VOICE_PROFILES[state.caseId] || { pitch: 1, rate: 1 };
        const utter = new SpeechSynthesisUtterance(text);
        utter.pitch = profile.pitch;
        utter.rate = profile.rate;
        window.speechSynthesis.speak(utter);
    }

    function updateVoiceButtons() {
        const vBtn = document.getElementById("btn-voice");
        const mBtn = document.getElementById("btn-mute");
        if (!vBtn || !mBtn) return;
        vBtn.textContent = voice.enabled ? "\uD83D\uDD0A VOICE: ON" : "\uD83D\uDD0A VOICE: OFF";
        vBtn.setAttribute("aria-pressed", String(voice.enabled));
        mBtn.classList.toggle("hidden", !voice.enabled);
        mBtn.textContent = voice.muted ? "\uD83D\uDD08 UNMUTE" : "\uD83D\uDD07 MUTE";
    }

    function initVoiceControls() {
        const vBtn = document.getElementById("btn-voice");
        const mBtn = document.getElementById("btn-mute");
        if (!vBtn || !mBtn) return;
        if (!voiceSupported) {
            vBtn.disabled = true;
            vBtn.title = "Speech is not supported in this browser";
            return;
        }
        vBtn.addEventListener("click", () => {
            voice.enabled = !voice.enabled;
            if (!voice.enabled) { voice.muted = false; stopSpeaking(); }
            updateVoiceButtons();
        });
        mBtn.addEventListener("click", () => {
            voice.muted = !voice.muted;
            if (voice.muted) stopSpeaking();
            updateVoiceButtons();
        });
        document.getElementById("btn-back-cases")?.addEventListener("click", stopSpeaking);
        window.addEventListener("beforeunload", stopSpeaking);
        updateVoiceButtons();
    }

    async function handleAskQuestion(e) {
        e.preventDefault();
        const question = elements.questionInput.value.trim();
        if (!question || state.gameOver) return;
        stopSpeaking();

        // UI Detective Message
        appendDetectiveMessage(question);
        elements.questionInput.value = "";
        elements.questionInput.disabled = true;
        elements.btnAsk.disabled = true;
        elements.btnAsk.textContent = "INTERROGATING...";

        // Show typing indicator in transcript feed
        const typingEl = showTypingIndicator();

        try {
            const res = await fetch("/api/ask", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    session_id: state.sessionId,
                    question: question
                })
            });

            const data = await res.json();
            if (!res.ok) {
                throw new Error(data.error || "Question rejected by server");
            }

            // Remove typing indicator
            if (typingEl) typingEl.remove();

            // Record statement in state
            const statement = {
                id: data.statement_id,
                question: question,
                text: data.answer
            };
            state.statements.push(statement);
            state.questionsLeft = data.questions_left;
            state.pressure = data.pressure;
            state.status = data.status;
            state.gameOver = data.game_over;
            state.resultReason = data.result_reason;
            state.score = data.score || 0;

            // Speak (if voice is on) while the typewriter renders the reply
            speakSuspect(statement.text);
            await appendSuspectMessageWithTypewriter(statement);
            updateStatsUI();

            if (state.gameOver) {
                setTimeout(() => triggerGameOver(), 1200);
            }
        } catch (err) {
            if (typingEl) typingEl.remove();
            console.error("Error asking question:", err);
            showToast(`Interrogation interrupted: ${err.message}`);
        } finally {
            elements.questionInput.disabled = false;
            elements.btnAsk.disabled = false;
            elements.btnAsk.textContent = "ASK QUESTION";
            elements.questionInput.focus();
        }
    }

    async function handleAccusation(e) {
        e.preventDefault();
        const quote1 = elements.accuseQuote1.value;
        const explanation = elements.accuseExplanation.value.trim();

        if (!quote1) {
            showAccuseFeedback("Please select a suspect statement to challenge.");
            return;
        }
        if (!explanation) {
            showAccuseFeedback("You must provide your reasoning for the contradiction.");
            return;
        }

        let quoteIds = [quote1];
        let evidenceId = null;

        if (state.pairingMode === "evidence") {
            evidenceId = elements.accuseEvidence.value;
            if (!evidenceId) {
                showAccuseFeedback("Please select an evidence item to contradict against.");
                return;
            }
        } else {
            const quote2 = elements.accuseQuote2.value;
            if (!quote2) {
                showAccuseFeedback("Please select a second suspect statement.");
                return;
            }
            if (quote2 === quote1) {
                showAccuseFeedback("You must select two distinct statements.");
                return;
            }
            quoteIds.push(quote2);
        }

        elements.btnAccuseSubmit.disabled = true;
        elements.btnAccuseSubmit.textContent = "JUDGE DELIBERATING...";
        elements.accuseFeedback.classList.add("hidden");

        try {
            const res = await fetch("/api/accuse", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    session_id: state.sessionId,
                    quote_ids: quoteIds,
                    evidence_id: evidenceId,
                    explanation: explanation
                })
            });

            const data = await res.json();
            if (!res.ok) {
                throw new Error(data.error || "Accusation failed");
            }

            // Update state
            state.pressure = data.pressure;
            state.strikes = data.strikes;
            state.status = data.status;
            state.gameOver = data.game_over;
            state.resultReason = data.result_reason;
            state.score = data.score || 0;
            if (data.valid && data.contradiction_id && !state.solvedContradictions.includes(data.contradiction_id)) {
                state.solvedContradictions.push(data.contradiction_id);
            }

            // Close modal
            closeAccuseModal();

            // Append verdict banner into transcript
            appendVerdictBanner(data, explanation, quoteIds, evidenceId);
            updateStatsUI();

            if (data.valid) {
                playSfx("valid");
            } else {
                playSfx("strike");
            }

            if (state.gameOver) {
                setTimeout(() => triggerGameOver(), 1500);
            }
        } catch (err) {
            console.error("Accusation error:", err);
            showAccuseFeedback(err.message);
        } finally {
            elements.btnAccuseSubmit.disabled = false;
            elements.btnAccuseSubmit.textContent = "SUBMIT ACCUSATION";
        }
    }

    // =========================================================================
    // UI RENDERING
    // =========================================================================

    function switchScreen(screen) {
        elements.screenCaseSelect.classList.add("hidden");
        elements.screenInterrogation.classList.add("hidden");
        elements.screenGameOver.classList.add("hidden");

        if (screen === "cases") {
            elements.screenCaseSelect.classList.remove("hidden");
            elements.statsBar.classList.add("hidden");
        } else if (screen === "interrogation") {
            elements.screenInterrogation.classList.remove("hidden");
            elements.statsBar.classList.remove("hidden");
        } else if (screen === "gameover") {
            elements.screenGameOver.classList.remove("hidden");
            elements.statsBar.classList.add("hidden");
        }
        window.scrollTo({ top: 0, behavior: "smooth" });
    }

    function renderCaseCards(cases) {
        elements.casesGrid.innerHTML = "";
        cases.forEach(c => {
            const card = document.createElement("div");
            card.className = "case-card";
            card.innerHTML = `
                <div class="case-card-header">
                    <span class="case-badge-pill">${c.id.toUpperCase()}</span>
                    <h3 class="case-card-title">${escapeHtml(c.title)}</h3>
                </div>
                <p class="case-card-blurb">${escapeHtml(c.blurb)}</p>
                <div class="case-card-meta">
                    <p><strong>Suspect:</strong> ${escapeHtml(c.suspect?.name || "Unknown")}</p>
                    <p><strong>Evidence:</strong> ${c.evidence?.length || 5} pieces on file</p>
                </div>
                <button class="btn-primary btn-open-case" data-id="${c.id}">
                    COMMENCE INTERROGATION &rarr;
                </button>
            `;
            elements.casesGrid.appendChild(card);
        });

        // Attach click handlers
        document.querySelectorAll(".btn-open-case").forEach(btn => {
            btn.addEventListener("click", () => {
                const caseId = btn.getAttribute("data-id");
                startInterrogation(caseId);
            });
        });
    }

    function setupInterrogationUI() {
        const c = state.caseData;
        elements.currentCaseId.textContent = state.caseId.toUpperCase();
        elements.currentCaseTitle.textContent = c.title;
        elements.currentSuspectName.textContent = c.suspect?.name || "Suspect";
        elements.currentCaseBriefing.textContent = c.briefing;
        elements.currentCaseSetting.textContent = c.setting;

        elements.suspectPersonality.textContent = c.suspect?.personality || "Guarded";
        elements.suspectStyle.textContent = c.suspect?.speech_style || "Noir tone";
        elements.suspectCoverStory.textContent = `"${c.cover_story || ''}"`;

        // Clear transcript
        elements.transcriptFeed.innerHTML = `
            <div class="transcript-empty-state">
                <p class="typewriter-text">The tape recorder clicks on. Suspect is seated beneath the desk lamp. Begin interrogation.</p>
            </div>
        `;
        elements.statementCounterBadge.textContent = "0 STATEMENTS LOGGED";

        // Render Evidence Cards
        elements.evidenceList.innerHTML = "";
        (c.evidence || []).forEach(ev => {
            const card = document.createElement("div");
            card.className = "evidence-item-card";
            card.innerHTML = `
                <div>
                    <span class="evidence-id-tag">${ev.id}</span>
                    <strong class="evidence-title">${escapeHtml(ev.name)}</strong>
                </div>
                <p class="evidence-desc">${escapeHtml(ev.description)}</p>
                <span class="evidence-action-hint">⚡ Click to confront suspect with this item</span>
            `;
            // Clicking evidence directly primes the contradiction modal
            card.addEventListener("click", () => {
                openAccuseModalWithEvidence(ev.id);
            });
            elements.evidenceList.appendChild(card);
        });
        elements.evidenceCountBadge.textContent = `${(c.evidence || []).length} ITEMS`;

        updateStatsUI();
        elements.questionInput.focus();
    }

    function updateStatsUI() {
        elements.pressureVal.textContent = `${state.pressure}%`;
        elements.pressureFill.style.width = `${state.pressure}%`;
        elements.questionsVal.textContent = state.questionsLeft;

        // Demeanor tag
        let demeanor = "CALM";
        if (state.pressure >= 100) demeanor = "BROKEN / CONFESSED";
        else if (state.pressure >= 67) demeanor = "CORNERED / DESPERATE";
        else if (state.pressure >= 34) demeanor = "SHAKEN / AGITATED";
        elements.demeanorTag.textContent = `DEMEANOR: ${demeanor}`;

        // Glow effect on Accusation button when pressure is high
        if (state.pressure >= 67 && !state.gameOver) {
            elements.btnOpenAccuse.classList.add("pulse-glow");
        } else {
            elements.btnOpenAccuse.classList.remove("pulse-glow");
        }

        // Strike pips
        const pips = elements.strikesContainer.querySelectorAll(".strike-pip");
        pips.forEach((pip, idx) => {
            if (idx < state.strikes) {
                pip.classList.add("active");
            } else {
                pip.classList.remove("active");
            }
        });

        // Statements badge
        elements.statementCounterBadge.textContent = `${state.statements.length} STATEMENTS LOGGED`;
    }

    function showTypingIndicator() {
        const row = document.createElement("div");
        row.className = "statement-row";
        row.innerHTML = `
            <div class="typing-indicator">
                <span class="typing-dot"></span>
                <span class="typing-dot"></span>
                <span class="typing-dot"></span>
                <span class="typing-label">SUSPECT IS HESITATING...</span>
            </div>
        `;
        elements.transcriptFeed.appendChild(row);
        elements.transcriptFeed.scrollTop = elements.transcriptFeed.scrollHeight;
        return row;
    }

    function appendDetectiveMessage(question) {
        // Clear empty state if present
        const empty = elements.transcriptFeed.querySelector(".transcript-empty-state");
        if (empty) empty.remove();

        const row = document.createElement("div");
        row.className = "statement-row";
        row.innerHTML = `
            <div class="message-detective">
                <span class="speaker-label">DETECTIVE:</span>
                <p class="msg-text">${escapeHtml(question)}</p>
            </div>
        `;
        elements.transcriptFeed.appendChild(row);
        elements.transcriptFeed.scrollTop = elements.transcriptFeed.scrollHeight;
    }

    function appendSuspectMessage(statement) {
        const row = document.createElement("div");
        row.className = "statement-row";
        row.innerHTML = `
            <div class="message-suspect">
                <div class="statement-meta-row">
                    <span class="statement-tag">${statement.id}</span>
                    <span class="suspect-name-badge">${escapeHtml(state.caseData.suspect?.name || "SUSPECT")}</span>
                </div>
                <p class="typewriter-text">${escapeHtml(statement.text)}</p>
            </div>
        `;

        // Click suspect statement to quick-launch contradiction modal
        row.querySelector(".message-suspect").addEventListener("click", () => {
            openAccuseModalWithStatement(statement.id);
        });

        elements.transcriptFeed.appendChild(row);
        elements.transcriptFeed.scrollTop = elements.transcriptFeed.scrollHeight;
    }

    function appendSuspectMessageWithTypewriter(statement) {
        return new Promise((resolve) => {
            const row = document.createElement("div");
            row.className = "statement-row";
            row.innerHTML = `
                <div class="message-suspect">
                    <div class="statement-meta-row">
                        <span class="statement-tag">${statement.id}</span>
                        <span class="suspect-name-badge">${escapeHtml(state.caseData.suspect?.name || "SUSPECT")}</span>
                    </div>
                    <p class="typewriter-text"><span class="typed-content"></span><span class="typewriter-cursor"></span></p>
                </div>
            `;

            row.querySelector(".message-suspect").addEventListener("click", () => {
                openAccuseModalWithStatement(statement.id);
            });

            elements.transcriptFeed.appendChild(row);
            const contentEl = row.querySelector(".typed-content");
            const cursorEl = row.querySelector(".typewriter-cursor");

            const fullText = statement.text;
            let charIndex = 0;
            const speed = 10; // fast responsive typewriter

            const interval = setInterval(() => {
                if (charIndex < fullText.length) {
                    contentEl.textContent += fullText[charIndex];
                    charIndex++;
                    if (charIndex % 3 === 0) playSfx("typewriter");
                    elements.transcriptFeed.scrollTop = elements.transcriptFeed.scrollHeight;
                } else {
                    clearInterval(interval);
                    if (cursorEl) cursorEl.remove();
                    resolve();
                }
            }, speed);
        });
    }

    function appendVerdictBanner(result, explanation, quoteIds, evidenceId) {
        const row = document.createElement("div");
        row.className = "statement-row";
        const isValid = result.valid;

        // Strip any quotation marks the player typed around their own text,
        // so the wrapper quotes below are not doubled.
        const cleanExplanation = String(explanation).trim().replace(/^["'\u201C\u201D\u2018\u2019]+|["'\u201C\u201D\u2018\u2019]+$/g, "").trim();

        let detailText = `Quoting [${quoteIds.join(", ")}]`;
        if (evidenceId) detailText += ` vs [${evidenceId}]`;

        row.innerHTML = `
            <div class="verdict-banner ${isValid ? 'valid' : 'invalid'}">
                <span class="verdict-title">
                    ${isValid ? '⚖️ CONTRADICTION SUSTAINED' : '❌ ACCUSATION DISMISSED'}
                    ${result.contradiction_id ? `(${result.contradiction_id})` : ''}
                </span>
                <p style="margin-bottom: 4px;"><strong>Detective's Case:</strong> &ldquo;${escapeHtml(cleanExplanation)}&rdquo;</p>
                <p><strong>Verdict:</strong> ${escapeHtml(result.reason)}</p>
                <div style="font-size: 11px; margin-top: 6px; opacity: 0.8;">
                    ${detailText} &bull; Pressure: ${result.pressure}% &bull; Strikes: ${result.strikes}/3
                </div>
            </div>
        `;
        elements.transcriptFeed.appendChild(row);
        elements.transcriptFeed.scrollTop = elements.transcriptFeed.scrollHeight;
    }

    function triggerGameOver() {
        switchScreen("gameover");

        const isWin = state.status === "won";
        elements.gameOverStamp.className = `game-over-stamp ${isWin ? 'won' : 'lost'}`;
        elements.gameOverStamp.textContent = isWin ? "CASE CLOSED — CONFESSION" : "CASE COMPROMISED";
        elements.gameOverTitle.textContent = isWin ? "FULL CONFESSION SECURED" : "INVESTIGATION TERMINATED";

        let bodyHtml = "";
        if (isWin) {
            // Find suspect confession or last statement
            const confessionStmt = state.statements[state.statements.length - 1];
            bodyHtml = `
                <p style="margin-bottom: 12px; font-weight: bold; color: var(--text-green);">
                    The suspect broke under relentless pressure and signed a voluntary confession.
                </p>
                <p class="typewriter-text" style="color: #f0f0c0;">
                    ${escapeHtml(state.resultReason || (confessionStmt ? confessionStmt.text : "I did it."))}
                </p>
            `;
        } else {
            bodyHtml = `
                <p style="margin-bottom: 12px; font-weight: bold; color: var(--text-red);">
                    ${escapeHtml(state.resultReason || "The suspect could not be broken. Investigation closed.")}
                </p>
                <p style="color: #aaa; font-size: 13px;">
                    Review the evidence and timeline carefully. Every contradiction must be tied directly to physical facts.
                </p>
            `;
        }
        elements.gameOverBody.innerHTML = bodyHtml;

        elements.finalPressure.textContent = `${state.pressure}%`;
        elements.finalContradictions.textContent = `${state.solvedContradictions.length} / 3`;
        elements.finalStrikes.textContent = `${state.strikes} / 3`;
        elements.finalQuestions.textContent = state.questionsLeft;

        renderResultCard();
    }

    // =========================================================================
    // RESULT CARD (score + copyable summary)
    // =========================================================================

    function buildResultSummary() {
        const title = state.caseData?.title || state.caseId || "Unknown case";
        const used = 15 - state.questionsLeft;
        const outcome = state.status === "won" ? "CONFESSION SECURED" : "SUSPECT WALKED";
        return [
            "INTERROGATION ROOM - CASE CLOSED",
            `Case: ${title}`,
            `Result: ${outcome}`,
            `Score: ${state.score}`,
            `Questions used: ${used}/15`,
            `Strikes: ${state.strikes}/3`,
            `Suspect's brain: ${state.model || "default"}`
        ].join("\n");
    }

    function renderResultCard() {
        const card = document.getElementById("result-card");
        if (!card) return;
        const used = 15 - state.questionsLeft;
        const isWin = state.status === "won";
        card.className = `result-card ${isWin ? "won" : "lost"}`;
        document.getElementById("result-case-title").textContent = state.caseData?.title || state.caseId || "";
        document.getElementById("result-score").textContent = String(state.score);
        document.getElementById("result-questions").textContent = `${used} / 15`;
        document.getElementById("result-strikes").textContent = `${state.strikes} / 3`;
        document.getElementById("result-model").textContent = state.model || "default";
        const copyBtn = document.getElementById("btn-copy-result");
        copyBtn.textContent = "COPY RESULT";
        copyBtn.onclick = async () => {
            const text = buildResultSummary();
            try {
                await navigator.clipboard.writeText(text);
            } catch (err) {
                const ta = document.createElement("textarea");
                ta.value = text;
                document.body.appendChild(ta);
                ta.select();
                try { document.execCommand("copy"); } catch (e) { /* ignore */ }
                ta.remove();
            }
            copyBtn.textContent = "COPIED \u2713";
            setTimeout(() => { copyBtn.textContent = "COPY RESULT"; }, 1800);
        };
    }

    // =========================================================================
    // MODAL DIALOG MANAGEMENT
    // =========================================================================

    function populateModalDropdowns() {
        // Statement 1
        elements.accuseQuote1.innerHTML = '<option value="">-- Choose a recorded statement --</option>';
        state.statements.forEach(s => {
            const opt = document.createElement("option");
            opt.value = s.id;
            opt.textContent = `[${s.id}] "${s.text.length > 55 ? s.text.slice(0, 55) + '...' : s.text}"`;
            elements.accuseQuote1.appendChild(opt);
        });

        // Statement 2
        elements.accuseQuote2.innerHTML = '<option value="">-- Select second statement --</option>';
        state.statements.forEach(s => {
            const opt = document.createElement("option");
            opt.value = s.id;
            opt.textContent = `[${s.id}] "${s.text.length > 55 ? s.text.slice(0, 55) + '...' : s.text}"`;
            elements.accuseQuote2.appendChild(opt);
        });

        // Evidence
        elements.accuseEvidence.innerHTML = '<option value="">-- Select evidence item --</option>';
        (state.caseData?.evidence || []).forEach(ev => {
            const opt = document.createElement("option");
            opt.value = ev.id;
            opt.textContent = `[${ev.id}] ${ev.name}`;
            elements.accuseEvidence.appendChild(opt);
        });
    }

    function openAccuseModal() {
        if (state.statements.length === 0) {
            showToast("You must interrogate the suspect and log at least one statement first.");
            return;
        }
        populateModalDropdowns();
        elements.accuseExplanation.value = "";
        elements.accuseFeedback.classList.add("hidden");
        elements.accuseModal.classList.remove("hidden");
        elements.accuseQuote1.focus();
    }

    function openAccuseModalWithStatement(statementId) {
        openAccuseModal();
        elements.accuseQuote1.value = statementId;
    }

    function openAccuseModalWithEvidence(evidenceId) {
        openAccuseModal();
        setPairingMode("evidence");
        elements.accuseEvidence.value = evidenceId;
    }

    function closeAccuseModal() {
        elements.accuseModal.classList.add("hidden");
        elements.accuseFeedback.classList.add("hidden");
    }

    function showAccuseFeedback(msg) {
        elements.accuseFeedback.textContent = msg;
        elements.accuseFeedback.classList.remove("hidden");
    }

    function setPairingMode(mode) {
        state.pairingMode = mode;
        if (mode === "evidence") {
            elements.tabEvidence.classList.add("active");
            elements.tabSecondQuote.classList.remove("active");
            elements.pairingEvidenceContainer.classList.remove("hidden");
            elements.pairingQuoteContainer.classList.add("hidden");
        } else {
            elements.tabEvidence.classList.remove("active");
            elements.tabSecondQuote.classList.add("active");
            elements.pairingEvidenceContainer.classList.add("hidden");
            elements.pairingQuoteContainer.classList.remove("hidden");
        }
    }

    function escapeHtml(str) {
        if (!str) return "";
        return str
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    // =========================================================================
    // EVENT LISTENERS & BOOTSTRAP
    // =========================================================================

    function init() {
        // Forms & buttons
        elements.askForm.addEventListener("submit", handleAskQuestion);
        elements.btnOpenAccuse.addEventListener("click", openAccuseModal);
        elements.btnModalClose.addEventListener("click", closeAccuseModal);
        elements.btnAccuseCancel.addEventListener("click", closeAccuseModal);
        elements.accuseForm.addEventListener("submit", handleAccuseContradiction);

        // Pairing tabs
        elements.tabEvidence.addEventListener("click", () => setPairingMode("evidence"));
        elements.tabSecondQuote.addEventListener("click", () => setPairingMode("quote"));

        // Navigation
        elements.btnBackCases.addEventListener("click", () => {
            if (confirm("Abandon current interrogation and return to case files?")) {
                switchScreen("cases");
            }
        });

        elements.btnReplayCase.addEventListener("click", () => {
            if (state.caseId) startInterrogation(state.caseId);
        });

        elements.btnSelectAnother.addEventListener("click", () => {
            switchScreen("cases");
        });

        // Submit contradiction on Ctrl+Enter / Cmd+Enter
        elements.accuseExplanation.addEventListener("keydown", (e) => {
            if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
                e.preventDefault();
                handleAccuseContradiction(e);
            }
        });

        // Close modal on Escape
        window.addEventListener("keydown", (e) => {
            if (e.key === "Escape" && !elements.accuseModal.classList.contains("hidden")) {
                closeAccuseModal();
            }
        });

        // Initial Load
        loadModels();
        initVoiceControls();
        loadCases();
    }

    function handleAccuseContradiction(e) {
        handleAccusation(e);
    }

    // Start on DOM ready
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
