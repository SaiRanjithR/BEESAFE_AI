# TrapLine — Project Memory & Build State

This document tracks all completed tickets, architectural decisions, and the current project state.

---

## 1. Completed Tickets (Settled & Verified)

### TICKET-001 — Database Schema & Models (P0)
- **Status:** COMPLETE
- **Artifacts:**
  - `docker-compose.yml`: PostgreSQL 16 container (`trapline_postgres`) running on port `5432`.
  - `backend/app/db/database.py`: SQLAlchemy engine, `SessionLocal`, `get_db` generator.
  - `backend/app/db/models.py`: 6 ORM models (`personas`, `conversations`, `messages`, `threat_indicators`, `risk_assessments`, `audit_logs`).
  - `backend/app/db/migrations/`: Alembic migration `35b5fb6bfaf9_create_initial_schema.py` applied to PostgreSQL.
  - `backend/app/db/seed.py`: Seed script creating initial persona (Margaret) and test conversation.
  - `backend/tests/test_schema.py`: 7 tests verifying tables, columns, foreign keys, constraints, and relational inserts.

### TICKET-002 — Honeypot Persona Agent (P0)
- **Status:** COMPLETE
- **Artifacts:**
  - `backend/app/schemas.py`: `HoneypotReply` schema (`reply`, `flagged_action`).
  - `backend/app/services/persona_agent.py`:
    - `get_honeypot_reply`: Generates in-character SMS replies via Anthropic Claude; formats conversation history and handles context truncation.
    - `check_reply_safety`: Outgoing safety net checking credit cards, crypto addresses (BTC/ETH/SOL), bank routing/account numbers, SSNs, URLs, and emails.
    - Exception hierarchy: `PersonaAgentError`, `LLMAPIError`, `LLMResponseValidationError`, `PersonaSafetyViolationError`.
  - `backend/tests/test_persona_agent.py`: 10 unit tests verifying payment request flagging, benign small talk handling, safety violation rejection, and error propagation.

### TICKET-003 — Simulated Scammer Bot (P0)
- **Status:** COMPLETE
- **Artifacts:**
  - `backend/app/services/scammer_bot.py`:
    - `get_simulated_scammer_reply`: 3-stage pig-butchering arc (turns 1–3 small talk, turns 4–6 investment bait, turns 7+ payment request).
    - Seeded constants for reproducible testing and correlation:
      - `SEEDED_FAKE_WALLET = "0x71C63303741cAE444856075c0c457bf433270c35"`
      - `SEEDED_FAKE_PAYMENT_HANDLE = "$ApexYieldVIP"`
      - `SEEDED_FAKE_URL = "https://apex-yield-trade.com/portal"`
      - `SEEDED_FAKE_PHONE = "+1-555-019-2834"`
    - Exception hierarchy: `ScammerBotError`, `ScammerAPIError`.
  - `backend/tests/test_scammer_bot.py`: 5 tests verifying constants, stage prompt transitions, and a complete 10-turn persona ↔ scammer simulated loop.

### TICKET-004 — Twilio SMS Webhook (Inbound + Outbound) (P0)
- **Status:** COMPLETE
- **Artifacts:**
  - `backend/app/services/twilio_client.py`: `send_sms` wrapper with `TwilioSendError` / `TwilioConfigurationError`.
  - `backend/app/routers/sms_webhook.py`: `POST /webhook/sms` endpoint.
    - Creates or appends to active conversations based on sender phone number.
    - Saves scammer message.
    - Calls `persona_agent.get_honeypot_reply`.
    - Automatically sends non-flagged reply via Twilio; holds flagged reply in review queue with `review_status = "pending"` without sending.
    - Returns HTTP 400 on missing or blank `From`/`Body`.
  - `backend/tests/test_sms_webhook.py`: 5 integration tests using FastAPI `TestClient`.

### TICKET-005 — Human Review Queue (Backend + API) (P0)
- **Status:** COMPLETE
- **Artifacts:**
  - `backend/app/auth.py`: `verify_api_key` enforcing `x-api-key` header matching `INTERNAL_API_KEY`.
  - `backend/app/routers/review_queue.py`:
    - `GET /review-queue`: Lists pending review messages.
    - `POST /review-queue/{message_id}/approve`: Row-level locked (`with_for_update`) to prevent duplicate sends; marks `approved`; dispatches via Twilio if SMS; records `AuditLog`.
    - `POST /review-queue/{message_id}/edit`: Validates safety of edited text; updates message; marks `edited`; dispatches via Twilio if SMS; records `AuditLog`.
    - `POST /review-queue/{message_id}/halt`: Marks message and conversation `halted`; blocks sending; records `AuditLog`.
  - `backend/tests/test_review_queue.py`: 8 tests covering auth, approve (SMS & simulated), edit, safety rejection, halt, and race condition duplicate send prevention (HTTP 409).

### TICKET-006 — Indicator Extraction (P0)
- **Status:** COMPLETE
- **Artifacts:**
  - `backend/app/services/extraction.py`:
    - `extract_indicators(transcript_text)`: High-precision regex extraction for `crypto_wallet`, `url`, `phone_number`, and `payment_handle`.
    - `extract_and_persist_indicators(db, conversation_id, transcript_text)`: Saves newly discovered indicators with `status="pending"`, deduplicating per conversation.
  - `backend/app/routers/sms_webhook.py`: Integrated `extract_and_persist_indicators` upon saving incoming messages.
  - `backend/tests/test_extraction.py`: 5 tests verifying extraction of all four types, multi-crypto formats, plain text false-positive resistance, trailing punctuation cleaning, and multi-turn DB persistence deduplication.

### TICKET-007 — Risk Scoring Agent (P0)
- **Status:** COMPLETE
- **Artifacts:**
  - `backend/app/schemas.py`: Added `RiskAssessmentResult` (`risk_score: int 0..100`, `classification: str`, `reasons: List[str]`).
  - `backend/app/services/risk_agent.py`:
    - `run_risk_agent(transcript, client=None)`: Evaluates transcript against fraud typologies (pig butchering, advance fee, impersonation); returns validated structured JSON.
    - `assess_and_upsert_risk(db, conversation_id, transcript, client=None)`: Upserts the risk score into the conversation's single `risk_assessments` row (updating rather than creating duplicates).
    - Exception hierarchy: `RiskAgentError`, `RiskAPIError`, `RiskResponseValidationError`.
  - `backend/app/routers/sms_webhook.py`: Integrated risk assessment trigger after message handling.
  - `backend/tests/test_risk_agent.py`: 5 tests verifying high risk scoring (>80 with >=3 grounded reasons on demo script), low risk (<30 on benign chat), idempotent DB upsert on repeated runs, and error handling.

### TICKET-008 — Analyst Dashboard (Frontend) (P0)
- **Status:** COMPLETE
- **Artifacts:**
  - `backend/app/routers/conversations.py`: `GET /conversations` (list with channel, message count, risk score, pending review status), `GET /conversations/{id}` (full detail with messages, indicators, risk assessment, persona backstory).
  - `backend/app/routers/simulated_bot.py`: `POST /simulate/start-conversation` (initializes simulated bot thread), `POST /simulate/{id}/next-turn` (advances turns between persona and simulated scammer bot).
  - `backend/tests/test_conversations.py`: Integration tests for conversation listing, detail view, and simulated conversation initiation.
  - `frontend/src/api/client.js`: API client wrapper with auto `x-api-key` header injection.
  - `frontend/src/components/ConversationBubble.jsx`: Scammer vs persona bubbles, review badges, and timestamps.
  - `frontend/src/components/RiskScoreGauge.jsx`: 40px/800 font, palette rule (green < 30, amber 30–70, red > 70), plain-language evidence.
  - `frontend/src/components/IndicatorTable.jsx`: Entity icons and status badges.
  - `frontend/src/components/BlockButton.jsx`: Action button with optimistic updates and idempotency.
  - `frontend/src/components/ReviewModal.jsx`: Approve / Edit / Halt modal with live safety validation.
  - `frontend/src/pages/AnalystDashboard.jsx`: Filter chips, search, simulated vs real SMS badge (`#0891B2` Info), simulation runner.
  - `frontend/src/pages/ConversationView.jsx`: Two-column layout (60% chat, 40% risk gauge & indicators, simulation turn controls).
  - `frontend/src/pages/ReviewQueue.jsx`: Dedicated review queue page.
  - `frontend/src/App.jsx`: 240px fixed left sidebar navigation, max-width 1200px container, API key management modal.

---

### TICKET-009 — Institution Dashboard (Frontend + Backend) (P0)
- **Status:** COMPLETE
- **Artifacts:**
  - `backend/app/schemas.py`: Added `InstitutionIndicatorOut` (strictly sanitized indicator entity + risk score/evidence, no transcripts or persona data) and `BlockIndicatorResponse`.
  - `backend/app/routers/indicators.py`:
    - `GET /indicators`: Returns threat indicators with source conversation's risk score and classification. Query parameters for filtering by type, status, and min risk, plus sort order. Strictly excludes transcripts, messages, and personas per Security & Access Document §2.
    - `POST /indicators/{id}/block`: Flips status to `blocked`, writes an `audit_logs` entry (`actor="institution_viewer"`, `action="blocked_indicator"`). Fully idempotent: subsequent calls return `already_blocked` without duplicate audit logs.
  - `backend/app/main.py`: Registered `indicators.router`.
  - `backend/tests/test_indicators.py`: 7 tests verifying auth, data structure, server-side privacy/role-boundary enforcement, sorting/filtering, block action, idempotency, and 404 handling.
  - `frontend/src/api/client.js`: Enhanced `listIndicators(params)` and `blockIndicator(id)`.
  - `frontend/src/pages/InstitutionDashboard.jsx`:
    - Full SecOps institution interface for banks, crypto exchanges, and telcos.
    - Privacy boundary notice highlighting strict transcript/persona quarantine.
    - Live Block button updating state without page reload.
    - Filterable by entity type chips (`crypto_wallet`, `url`, `phone_number`, `payment_handle`), status, and risk level.
    - Sortable by risk score (descending/ascending) and detection timestamp.
    - KPI cards: Total Indicators, High Risk (70+), Active Block Rules, Pending Action.
    - Search input for real-time text matching across values, types, and classifications.
    - Expandable rows for viewing algorithmic risk reasons/evidence.

---

### TICKET-010 — Multi-Conversation Correlation (Should-Have) (P1)
- **Status:** COMPLETE
- **Artifacts:**
  - `backend/app/schemas.py`: Added `conversation_count` field to `InstitutionIndicatorOut` (tracks distinct conversations where an indicator value was observed).
  - `backend/app/routers/indicators.py`:
    - Updated `list_indicators` to execute a correlation subquery: `COUNT(DISTINCT conversation_id) GROUP BY value`.
    - Added query parameters: `correlated_only: bool` (filters to indicators observed across >1 conversation) and `sort_by="correlated_desc"`.
  - `backend/tests/test_indicators.py`: Added 3 tests covering multi-conversation correlation count (testing seeded constants across 3+ conversations), dynamic count increment as new conversations extract the indicator, `correlated_only` filtering, and correlation descending sorting.
  - `frontend/src/api/client.js`: Added `correlated_only` support to `listIndicators` options.
  - `frontend/src/pages/InstitutionDashboard.jsx`:
    - Distinct badge next to correlated indicators: `seen in X conversations`.
    - "Correlated Threats" KPI card tracking syndicates observed across multiple conversations.
    - "Correlated Only" quick-filter toggle.
    - "Most Correlated First" sort option.

---

### TICKET-011 — n8n Enrichment Workflow (Should-Have) (P1)
- **Status:** COMPLETE
- **Artifacts:**
  - `backend/app/db/models.py`: Added `known_bad` (Boolean) and `domain_age_days` (Integer) to `ThreatIndicator` model.
  - `backend/app/db/migrations/versions/9e2d7a4e671a_add_enrichment_columns_to_threat_.py`: Alembic migration applied to PostgreSQL.
  - `backend/app/schemas.py`: Added `known_bad` and `domain_age_days` to `ThreatIndicatorOut` and `InstitutionIndicatorOut`; added `EnrichmentCallbackRequest` and `EnrichmentCallbackResponse`.
  - `backend/app/services/enrichment.py`:
    - `parse_domain`: Cleans URLs and isolates hostnames.
    - `lookup_rdap_domain_age`: Queries RDAP WHOIS for registration date; simulates 4-day age for seeded malicious domains; resilient timeout/error handling.
    - `lookup_url_blocklist`: Checks domain/path against known fraud indicators and phishing patterns.
    - `perform_local_enrichment`: Standalone resilient enrichment pipeline.
    - `trigger_url_enrichment`: Dispatches to n8n webhook when enabled; falls back gracefully to local enrichment without crashing.
  - `backend/app/services/extraction.py`: Automatically invokes `trigger_url_enrichment` upon extracting and saving new URL-type indicators.
  - `backend/app/routers/enrichment_webhook.py`: `POST /webhook/enrichment-result` endpoint updating `threat_indicators` record.
  - `backend/app/main.py`: Registered `enrichment_webhook.router`.
  - `n8n/enrichment-workflow.json`: Exported n8n workflow with Webhook trigger, Domain Parsing, RDAP WHOIS HTTP request, Threat Blocklist HTTP request, Risk & Age Synthesis, and Backend Callback HTTP request with retry/backoff.
  - `docker-compose.yml`: Added optional `n8n` container configuration.
  - `frontend/src/pages/InstitutionDashboard.jsx`: Displays domain age badges (e.g. `New Domain (4d)`), and blocklist badges (`Blocklist Flagged` / `Blocklist Clean`) alongside threat entities.
  - `backend/tests/test_enrichment.py`: 9 unit/integration tests verifying domain parsing, RDAP lookup, blocklist detection, local enrichment, webhook callback persistence, automatic trigger on extraction, and n8n dispatch.

---

### TICKET-012 — Explanation Agent (Should-Have) (P1)
- **Status:** COMPLETE
- **Artifacts:**
  - `backend/app/db/models.py`: Added `explanation = Column(Text, nullable=True)` to `RiskAssessment` model.
  - `backend/app/db/migrations/versions/bdd55cc09a02_add_explanation_to_risk_assessments.py`: Alembic migration applied to PostgreSQL.
  - `backend/app/schemas.py`: Added `explanation: Optional[str] = None` to `RiskAssessmentOut`.
  - `backend/app/services/risk_agent.py`:
    - `explain_for_demo(risk_assessment, client=None)`: Separate, dedicated LLM call with `EXPLANATION_SYSTEM_PROMPT` generating a warm, executive narrative paragraph grounded strictly in the technical reasons without changing the underlying score/classification.
    - `assess_and_upsert_risk(..., generate_explanation=False)`: Supports optional on-the-fly narrative generation.
  - `backend/app/routers/conversations.py`: Added `POST /conversations/{conversation_id}/explain` to generate and persist narrative explanation on demand.
  - `frontend/src/api/client.js`: Added `explainRisk: (id) => request('/conversations/' + id + '/explain', { method: 'POST' })`.
  - `frontend/src/components/RiskScoreGauge.jsx`: Renders "Narrative Threat Briefing" with `Sparkles` icon alongside (not replacing) the original bulleted `Transcript-Grounded Evidence` list; includes generate/refresh controls.
  - `frontend/src/pages/ConversationView.jsx`: Wired `handleExplain` and state management to trigger explanation on demand and refresh risk assessment.
  - `backend/tests/test_risk_agent.py`: Added unit and integration tests verifying single-paragraph narrative output without bullet points, factual consistency, immutable score/classification, and DB persistence via `POST /conversations/{id}/explain`.

### TICKET-013 — MMS/Image Support (Nice-to-Have) (P2)
- **Status:** COMPLETE
- **Artifacts:**
  - `backend/app/services/vision_service.py`:
    - `caption_image(image_url, content_type, client, image_bytes)`: Downloads inbound MMS media with optional Twilio basic authentication, base64 encodes image, and requests a concise 1-2 sentence caption from Claude 3.5 Sonnet Vision.
    - `normalize_media_type`: Handles and normalizes MIME types (`image/jpeg`, `image/png`, `image/webp`, `image/gif`).
    - Fallback resilience: Catches all network/LLM/parsing errors and returns a graceful fallback caption (`attached photo or screenshot from sender`) guaranteeing that webhook requests never crash or drop messages.
  - `backend/app/routers/sms_webhook.py`:
    - Updated `twilio_sms_webhook` to accept `MediaUrl0`, `MediaContentType0`, and `NumMedia`.
    - Handles text-only SMS, media-only MMS, and combined text + media MMS (`{body}\n[Image: {caption}]`).
    - Validates that either `Body` or `MediaUrl0` is provided; raises HTTP 400 only if neither is present.
    - Saves scammer message with `[Image: <caption>]` representation to DB and feeds it into indicator extraction and honeypot persona conversation history.
  - `backend/app/services/persona_agent.py`:
    - Added behavior rule 6 to persona system prompt instructing the agent to react naturally and in character to `[Image: <caption>]` descriptions (e.g., commenting on account screenshots, luxury items, certificates, or charts).
  - `frontend/src/components/ConversationBubble.jsx`:
    - Renders structured visual attachment boxes with `ImageIcon` for `[Image: <caption>]` captions within chat bubbles.
  - `backend/tests/test_vision_service.py`: 5 unit tests verifying MIME normalization, base64 vision call with bytes, HTTP image download, network error fallback resilience, and LLM error fallback resilience.
  - `backend/tests/test_sms_webhook.py`: Added 3 integration tests verifying media-only MMS captioning and DB persistence, combined text+image MMS formatting, and captioning failure fallback.

---

### TICKET-014 — Basic Multi-Role Access Control (Nice-to-Have) (P2)
- **Status:** COMPLETE
- **Artifacts:**
  - `backend/app/config.py`: Added `ADMIN_API_KEY`, `ANALYST_API_KEY`, and `INSTITUTION_API_KEY` to `Settings` alongside legacy `INTERNAL_API_KEY`.
  - `.env` & `.env.example`: Configured multi-role keys.
  - `backend/app/auth.py`:
    - `UserRole` enum (`admin`, `analyst`, `institution_viewer`).
    - `get_current_role`: Validates `x-api-key` header and resolves user role; raises HTTP 401 if missing or invalid.
    - `require_roles`: Reusable dependency factory enforcing permitted roles and raising HTTP 403 Forbidden on disallowed operations.
    - Pre-configured dependencies: `verify_api_key` (any valid role), `require_analyst` (Admin + Analyst), `require_institution` (Admin + Institution Viewer), `require_admin` (Admin only).
  - `backend/app/routers/indicators.py`:
    - `GET /indicators`: Accessible by all authenticated roles (`verify_api_key`).
    - `POST /indicators/{indicator_id}/block`: Restricted to Institution Viewer and Admin (`require_institution`). Analysts receive HTTP 403 Forbidden.
  - `backend/app/routers/conversations.py`:
    - `GET /conversations`, `GET /conversations/{id}`, `POST /conversations/{id}/explain`: Restricted to Analyst and Admin (`require_analyst`). Institution Viewers receive HTTP 403 Forbidden.
  - `backend/app/routers/review_queue.py`:
    - All review queue endpoints (`GET`, `POST approve/edit/halt`): Restricted to Analyst and Admin (`require_analyst`). Institution Viewers receive HTTP 403 Forbidden.
  - `backend/app/routers/simulated_bot.py`:
    - Simulation endpoints (`POST /simulate/start-conversation`, `POST /simulate/{id}/next-turn`): Restricted to Analyst and Admin (`require_analyst`). Institution Viewers receive HTTP 403 Forbidden.
  - `frontend/src/App.jsx`:
    - Added one-click role key preset buttons ("Admin Key", "Analyst Key", "Institution Key") inside the API Key Modal for instant role switching and demoing.
  - `backend/tests/test_rbac.py`: 4 comprehensive integration tests verifying 401 on missing/bogus keys, Institution Viewer permissions (200 on indicators/block, 403 on conversations/review/simulations), Analyst permissions (200 on conversations/review/indicators, 403 on block), and unrestricted Admin access.

---

## 2. Test Suite Status
- Total passing tests: 81 / 81 across all test suites.
- Frontend build: Vite compilation clean (0 errors, 935ms).

---

## 3. Project Status & Roadmap
- **All 14 Feature Tickets Complete (100%):**
  - **P0 Must-Haves:** TICKET-001 through TICKET-009 (Database Schema, Honeypot Persona Agent, Simulated Scammer Bot, Twilio SMS Webhook, Human Review Queue, Indicator Extraction, Risk Scoring Agent, Analyst Dashboard Frontend, Institution Dashboard Frontend + Backend).
  - **P1 Should-Haves:** TICKET-010 (Multi-Conversation Correlation), TICKET-011 (n8n Enrichment Workflow), TICKET-012 (Explanation Agent).
  - **P2 Nice-to-Haves:** TICKET-013 (MMS/Image Support), TICKET-014 (Basic Multi-Role Access Control).
- All acceptance criteria across all tickets have been implemented, verified, and backed by automated test coverage.




