# TrapLine — Feature Ticket List

*Each ticket is self-contained enough to paste directly into an AI coding tool (e.g., Claude Code) as a build prompt. Priority: **P0 = must-have**, **P1 = should-have**, **P2 = nice-to-have**.*

---

### TICKET-001 — Database Schema & Models
**Priority:** P0
**Description:** Create the PostgreSQL schema and matching SQLAlchemy ORM models for `conversations`, `personas`, `messages`, `threat_indicators`, `risk_assessments`, and `audit_logs`, exactly as specified in the Technical Architecture Document §3. Include an Alembic migration that creates all tables with correct foreign keys and defaults.
**Acceptance criteria:**
- All six tables exist with the fields, types, and foreign-key relationships listed in the architecture doc.
- Running the migration on a fresh database succeeds with no errors.
- A basic seed script can insert one persona and one conversation without constraint violations.
**Dependencies:** None — this is the foundation everything else builds on.

---

### TICKET-002 — Honeypot Persona Agent
**Priority:** P0
**Description:** Build `persona_agent.get_honeypot_reply(conversation_history, persona)` — a function that formats the conversation history and persona backstory into an LLM API call, enforces structured JSON output `{reply: str, flagged_action: str | null}`, and validates the response against that schema before returning it. `flagged_action` must be set to `"payment_request"` or `"platform_move"` when the scammer's most recent message asks for money or requests moving to another app; otherwise null.
**Acceptance criteria:**
- Given a hardcoded sample conversation ending in a payment request, the function returns `flagged_action: "payment_request"`.
- Given a benign small-talk exchange, it returns `flagged_action: null`.
- If the LLM API call fails or returns invalid JSON, the function raises a specific, catchable exception rather than crashing the caller or returning malformed data.
- The persona never includes real payment details, real personal identifiers, or a real working link in its own generated reply (verified with a basic regex safety check on the output, per the Security & Access Document's edge-case guidance).
**Dependencies:** TICKET-001 (needs the `personas` table shape for backstory data).

---

### TICKET-003 — Simulated Scammer Bot
**Priority:** P0
**Description:** Build `scammer_bot.get_simulated_scammer_reply(conversation_history, turn_number)` — a second LLM-prompted function that plays a scripted pig-butchering-style scammer, following a loose turn-based arc: turns 1–3 small talk, turns 4–6 introduce an investment "bait," turn 7+ request payment to a fake, clearly-fictional wallet address seeded for the demo.
**Acceptance criteria:**
- Running a full loop of persona agent ↔ scammer bot for at least 10 turns produces a coherent conversation without either side breaking character.
- The scammer bot's seeded fake payment handle is a constant, reusable value (needed later for TICKET-007's cross-conversation correlation).
- The bot never actually requires or waits on real infrastructure — this runs entirely as two LLM calls talking to each other.
**Dependencies:** TICKET-002 (the persona agent it's conversing with must exist first, even if tested with a stub).

---

### TICKET-004 — Twilio SMS Webhook (Inbound + Outbound)
**Priority:** P0
**Description:** Build `POST /webhook/sms`, which receives Twilio's inbound webhook payload, looks up or creates the matching `conversations` row (keyed on the sender's phone number), saves the message, calls the persona agent, and — if `flagged_action` is null — sends the reply via the Twilio outbound API immediately; if set, saves it with `review_status = "pending"` instead of sending.
**Acceptance criteria:**
- A test POST matching Twilio's real payload shape creates a new conversation on first contact and appends to an existing one on a repeat number.
- A non-flagged reply is sent via Twilio and saved with `review_status = "not_needed"`.
- A flagged reply is saved with `review_status = "pending"` and is NOT sent to Twilio.
- Malformed webhook payloads (missing `From` or `Body`) return HTTP 400 without crashing the process.
**Dependencies:** TICKET-001, TICKET-002.

---

### TICKET-005 — Human Review Queue (Backend + API)
**Priority:** P0
**Description:** Build the review-queue endpoints: `GET /review-queue` (list all messages with `review_status = "pending"`), `POST /review-queue/{message_id}/approve` (sends the reply as-is via Twilio or marks it delivered for simulated conversations), `POST /review-queue/{message_id}/edit` (accepts edited text, then sends it), `POST /review-queue/{message_id}/halt` (marks the conversation `status = "halted"` and does not send). Every action writes a row to `audit_logs`.
**Acceptance criteria:**
- Approving a pending message changes its `review_status` to `approved` and triggers the send (real or simulated).
- Editing replaces the stored text before sending and sets `review_status` to `edited`.
- Halting sets the conversation's status to `halted` and no further messages are sent for it.
- Two simultaneous approve requests on the same message result in exactly one send, not two (see Security & Access Document's race-condition edge case).
**Dependencies:** TICKET-004.

---

### TICKET-006 — Indicator Extraction
**Priority:** P0
**Description:** Build `extraction.extract_indicators(transcript_text)` — a regex-based function returning a list of `{indicator_type, value}` for crypto wallet address patterns, phone numbers, URLs, and payment-app handles (`$cashtag`, `@handle`-style). Run this after every new message is saved, writing any new (not-already-seen-in-this-conversation) indicators to the `threat_indicators` table.
**Acceptance criteria:**
- Given a transcript containing one of each indicator type, all four are correctly extracted with the correct `indicator_type` label.
- Running extraction twice on the same growing transcript does not create duplicate `threat_indicators` rows for the same value within the same conversation.
- A normal sentence with no real indicators produces an empty list (no false positives on plain text).
**Dependencies:** TICKET-001, TICKET-004 or TICKET-003 (needs messages to extract from).

---

### TICKET-007 — Risk Scoring Agent
**Priority:** P0
**Description:** Build `risk_agent.run_risk_agent(transcript_text)` — an LLM call returning structured `{risk_score: int, classification: str, reasons: [str]}`, run after each new message and upserted into the conversation's single `risk_assessments` row (update, not insert, on subsequent runs).
**Acceptance criteria:**
- Given the full scripted demo conversation from TICKET-003, returns a risk score above 80 with at least three specific, transcript-grounded reasons (not generic boilerplate).
- Given a benign small-talk-only transcript, returns a low risk score (below 30).
- Calling this twice on the same conversation updates the existing `risk_assessments` row rather than creating a second one.
**Dependencies:** TICKET-001, TICKET-006 (reasons are stronger with indicators available as context, though not strictly required).

---

### TICKET-008 — Analyst Dashboard (Frontend)
**Priority:** P0
**Description:** Build the Analyst Dashboard page: a list of conversations (labeled `sms` or `simulated` per the Frontend Spec's Info color), each opening into a Conversation View showing the transcript as chat bubbles, a risk score gauge, an indicator table, and a review-queue panel with Approve/Edit/Halt buttons for any pending message.
**Acceptance criteria:**
- Conversation list correctly distinguishes real SMS vs. simulated conversations visually.
- Opening a conversation shows all messages in order with correct sender styling (scammer vs. persona bubbles visually distinct per the design system).
- A pending review item is visibly highlighted and its three action buttons call the correct backend endpoints from TICKET-005.
- Risk score gauge color matches the palette rule (green under 30, amber 30–70, red above 70 — confirm exact thresholds with design intent, adjust if specified otherwise).
**Dependencies:** TICKET-004, TICKET-005, TICKET-006, TICKET-007 (needs all backend pieces returning real data).

---

### TICKET-009 — Institution Dashboard (Frontend + Backend)
**Priority:** P0
**Description:** Build `GET /indicators` (all threat_indicators with status and source conversation's risk score, but NOT the raw transcript — see Security & Access Document's role separation) and `POST /indicators/{id}/block` (flips `status` to `blocked`, writes an audit log entry). Build the frontend Institution Dashboard page: a table of indicators with type, value, risk score, status, and a Block button.
**Acceptance criteria:**
- The `/indicators` endpoint never includes conversation transcript or persona data in its response — only indicator + risk-score-level data, enforced server-side.
- Clicking Block updates the row's status live without a full page reload and is idempotent (clicking twice on an already-blocked row doesn't error or duplicate the audit log entry).
- Table is sortable/filterable by risk score at minimum.
**Dependencies:** TICKET-006, TICKET-007.

---

### TICKET-010 — Multi-Conversation Correlation (Should-Have)
**Priority:** P1
**Description:** Extend the Institution Dashboard to flag when the same indicator `value` appears across more than one conversation, displaying a count (e.g., "seen in 3 conversations") next to that row.
**Acceptance criteria:**
- Running TICKET-003's simulated bot with its constant seeded fake payment handle across 2–3 separate demo conversations results in that indicator showing a count of 2–3 on the Institution Dashboard.
- Count updates correctly as new matching indicators are extracted.
**Dependencies:** TICKET-009.

---

### TICKET-011 — n8n Enrichment Workflow (Should-Have)
**Priority:** P1
**Description:** Build the n8n workflow per the Frontend Spec's integration section: on receiving a new URL-type indicator, call a public WHOIS/RDAP endpoint and a public URL blocklist API, then callback to `POST /webhook/enrichment-result` to update that indicator's record with `known_bad` and `domain_age_days`.
**Acceptance criteria:**
- A newly extracted URL indicator triggers the workflow automatically (via the backend calling n8n's webhook after TICKET-006 runs).
- The workflow completes and updates the indicator record within a reasonable demo-friendly time (a few seconds), with retry-with-backoff on the two HTTP Request nodes per the earlier architecture discussion.
- A failure in either external API call does not crash the workflow for other indicators being processed.
**Dependencies:** TICKET-006, TICKET-009 (needs indicators to enrich and a place to show the result).

---

### TICKET-012 — Explanation Agent (Should-Have)
**Priority:** P1
**Description:** Build a second, separate LLM call, `risk_agent.explain_for_demo(risk_assessment)`, that rewrites the risk-scoring reasons into a warmer, narrative paragraph suitable for the demo screen, without altering the underlying score/classification.
**Acceptance criteria:**
- Output is a single paragraph, clearly distinct in tone from the technical `reasons` list, but factually consistent with it (no new claims not supported by the original reasons).
- Displayed alongside (not replacing) the original structured reasons on the Conversation View.
**Dependencies:** TICKET-007.

---

### TICKET-013 — MMS/Image Support (Nice-to-Have)
**Priority:** P2
**Description:** Extend the Twilio webhook to detect `MediaUrl0` on inbound messages, fetch the image, caption it via a vision-capable model call, and inject the caption into the conversation history as if it were text.
**Acceptance criteria:**
- An inbound MMS with an image produces a saved message with a `[Image: <caption>]`-style text representation, not a crash or silent drop.
- The persona agent's next reply can meaningfully reference the captioned content.
**Dependencies:** TICKET-002, TICKET-004.

---

### TICKET-014 — Basic Multi-Role Access Control (Nice-to-Have)
**Priority:** P2
**Description:** Extend the single-API-key auth to support the three roles from the Security & Access Document (Analyst, Institution Viewer, Admin), each with a distinct key and enforced permission checks per the row-level rules in that document.
**Acceptance criteria:**
- An Institution Viewer key can successfully call `GET /indicators` and `POST /indicators/{id}/block` but receives HTTP 403 on any conversation/message/transcript endpoint.
- An Analyst key can access conversation/review-queue endpoints but receives HTTP 403 calling `POST /indicators/{id}/block`.
**Dependencies:** TICKET-005, TICKET-009.
