# TrapLine — Technical Architecture Document

## 1. Recommended Tech Stack (with reasoning)

| Layer | Choice | Why |
|---|---|---|
| Frontend | **React + Vite + Tailwind CSS** | Fast scaffolding for a time-boxed build; Tailwind avoids hand-rolled CSS under deadline pressure; huge ecosystem for dashboard/table components. |
| Backend | **FastAPI (Python)** | Best ecosystem for regex/text-processing and LLM SDKs; async support suits webhook-driven traffic (Twilio); automatic OpenAPI docs at `/docs` useful for both the team and demo credibility. |
| Database | **PostgreSQL** | Data is inherently relational (one conversation → many messages → many indicators → one risk assessment); easy to inspect/demo live; every managed-hosting option supports it. |
| SMS channel | **Twilio Programmable SMS** | Official, sanctioned API built exactly for "receive inbound texts from unknown numbers, reply programmatically" — no ToS gray area, unlike WhatsApp/Instagram automation (see prior discussion). |
| LLM provider | **Anthropic API (Claude)** or equivalent | Needed for both the persona agent and the risk-scoring agent; structured/JSON output mode keeps responses machine-parseable. |
| Automation (should-have) | **n8n** | Good fit for the *enrichment side-path only* (WHOIS/blocklist lookups) — keep it out of the core request/response path the analyst is waiting on. |
| Hosting — backend | **Railway or Render** | Fast, simple deploys for a Python/Postgres app without needing to hand-roll infra during a hackathon. |
| Hosting — frontend | **Vercel or Netlify** | One-command static/SPA deploy, generous free tier. |
| Auth | Simple API-key header (see Security & Access Document) | Internal-tool-grade auth is sufficient for v1; no public signup exists. |

## 2. Complete File & Folder Structure

```
trapline/
├── backend/
│   ├── app/
│   │   ├── main.py                     # FastAPI app entrypoint, route registration
│   │   ├── config.py                   # env var loading/validation
│   │   ├── db/
│   │   │   ├── database.py             # SQLAlchemy engine/session setup
│   │   │   ├── models.py               # ORM models (mirrors schema in §3)
│   │   │   └── migrations/             # Alembic migration files
│   │   ├── routers/
│   │   │   ├── sms_webhook.py          # POST /webhook/sms (Twilio inbound)
│   │   │   ├── conversations.py        # GET conversation list/detail
│   │   │   ├── review_queue.py         # GET/POST pending-review actions
│   │   │   ├── indicators.py           # GET indicators, POST /block
│   │   │   └── simulated_bot.py        # POST /simulate/start-conversation
│   │   ├── services/
│   │   │   ├── persona_agent.py        # get_honeypot_reply(conversation_history)
│   │   │   ├── scammer_bot.py          # get_simulated_scammer_reply(...)
│   │   │   ├── extraction.py           # extract_indicators(transcript) — regex
│   │   │   ├── risk_agent.py           # run_risk_agent(transcript)
│   │   │   └── twilio_client.py        # thin wrapper around Twilio SDK
│   │   └── schemas.py                  # Pydantic request/response models
│   ├── tests/
│   │   ├── test_persona_agent.py
│   │   ├── test_extraction.py
│   │   └── test_risk_agent.py
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── main.jsx
│   │   ├── App.jsx
│   │   ├── pages/
│   │   │   ├── AnalystDashboard.jsx
│   │   │   ├── ConversationView.jsx
│   │   │   ├── ReviewQueue.jsx
│   │   │   └── InstitutionDashboard.jsx
│   │   ├── components/
│   │   │   ├── ConversationBubble.jsx
│   │   │   ├── RiskScoreGauge.jsx
│   │   │   ├── IndicatorTable.jsx
│   │   │   └── BlockButton.jsx
│   │   ├── api/
│   │   │   └── client.js               # fetch wrapper, base URL + API key header
│   │   └── styles/
│   │       └── tailwind.css
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
├── n8n/
│   └── enrichment-workflow.json        # exported n8n workflow (should-have)
├── docker-compose.yml                  # local dev: backend + postgres + n8n
├── .env.example
└── README.md
```

## 3. Full Database Schema (plain English + structure)

**`conversations`** — one row per distinct scammer contact (real or simulated).
| Field | Type | Meaning |
|---|---|---|
| id | uuid, PK | Unique conversation ID |
| channel | text | `sms` or `simulated` |
| scammer_contact | text | The scammer's phone number (or a fake ID for simulated conversations) |
| persona_id | uuid, FK → personas | Which persona is playing the decoy in this conversation |
| status | text | `active`, `halted`, `completed` |
| created_at | timestamp | When first contact happened |

**`personas`** — the decoy identities the honeypot agent can play.
| Field | Type | Meaning |
|---|---|---|
| id | uuid, PK | Unique persona ID |
| name | text | Persona's first name |
| backstory_json | jsonb | Age, occupation, hobbies, financial posture — fed into the system prompt |
| created_at | timestamp | — |

**`messages`** — every turn of every conversation, in order.
| Field | Type | Meaning |
|---|---|---|
| id | uuid, PK | Unique message ID |
| conversation_id | uuid, FK → conversations | Which conversation this belongs to |
| role | text | `scammer` or `persona` |
| text | text | The message content |
| flagged_action | text, nullable | `payment_request`, `platform_move`, or null — set when the persona agent's reply needs human review |
| review_status | text | `not_needed`, `pending`, `approved`, `edited`, `halted` |
| created_at | timestamp | When this turn happened |

**`threat_indicators`** — extracted entities from a conversation's transcript.
| Field | Type | Meaning |
|---|---|---|
| id | uuid, PK | Unique indicator ID |
| conversation_id | uuid, FK → conversations | Source conversation |
| indicator_type | text | `crypto_wallet`, `phone_number`, `url`, `payment_handle` |
| value | text | The actual extracted string |
| status | text | `pending`, `blocked` — this is what the Institution Dashboard's "Block" button flips |
| created_at | timestamp | When extracted |

**`risk_assessments`** — one per conversation, updated as the conversation grows.
| Field | Type | Meaning |
|---|---|---|
| id | uuid, PK | — |
| conversation_id | uuid, FK → conversations, unique | 1:1 with a conversation |
| risk_score | int (0–100) | Latest score |
| classification | text | e.g. `pig_butchering_suspected` |
| reasons | jsonb (array of strings) | Plain-language reasons behind the score |
| updated_at | timestamp | Last time this was recalculated |

**`audit_logs`** — append-only log of every human action taken.
| Field | Type | Meaning |
|---|---|---|
| id | uuid, PK | — |
| conversation_id | uuid, FK → conversations, nullable | What this action relates to |
| actor | text | Who/what took the action (analyst name or "system") |
| action | text | e.g. `approved_reply`, `blocked_indicator`, `halted_conversation` |
| created_at | timestamp | — |

**Relationships in plain English:** A **conversation** belongs to one **persona** and contains many **messages**, in order. A conversation can produce many **threat indicators** and has exactly one **risk assessment**, which gets updated (not duplicated) as the conversation continues. Every meaningful human action — approving a reply, blocking an indicator — writes a row to **audit_logs**, so there's a full trail of who did what, when.

## 4. Environment Variables & Configuration Notes

```
# .env.example

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/trapline

# LLM provider
ANTHROPIC_API_KEY=sk-ant-...
LLM_MODEL=claude-...              # pin an exact model string, don't leave it implicit

# Twilio
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=+1555...
TWILIO_WEBHOOK_URL=https://your-backend.com/webhook/sms   # must be publicly reachable — use ngrok in local dev

# Internal API auth
INTERNAL_API_KEY=<random-generated-string>   # required on every dashboard/API request except the Twilio webhook itself

# n8n (should-have)
N8N_WEBHOOK_URL=...
N8N_ENRICHMENT_ENABLED=false     # feature-flag it — keep the core path working even if n8n isn't set up yet

# Misc
ENVIRONMENT=development           # development | production
LOG_LEVEL=info
```

**Configuration notes to be aware of before you start building:**
- **Twilio webhook must be a public URL** — in local development, Twilio cannot reach `localhost`; run `ngrok http 8000` (or similar) and put that URL in the Twilio console, not in your `.env` alone — the console configuration and your env var need to match.
- **Never commit `.env`** — only `.env.example` (with placeholder values) belongs in the repo.
- **Pin the exact LLM model string** — don't rely on a default/latest alias for a demo; you want reproducible behavior on demo day, not a silent model swap the morning of.
- **Feature-flag anything optional** (`N8N_ENRICHMENT_ENABLED`) so a should-have integration failing doesn't take down the must-have core path.
- **The `INTERNAL_API_KEY` is not real security** — it's a placeholder appropriate for an internal hackathon tool with no public signup; see the Security & Access Document for what this does and doesn't protect against.
