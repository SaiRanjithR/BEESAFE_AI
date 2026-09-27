# TrapLine — Frontend Specification Document

## 1. Design System

### Color Palette

| Name | Hex | Usage |
|---|---|---|
| Ink (primary text) | `#111827` | Body text, headings |
| Slate (secondary text) | `#6B7280` | Timestamps, captions, muted labels |
| Surface | `#FFFFFF` | Card/panel backgrounds |
| Background | `#F3F4F6` | Page background |
| Border | `#E5E7EB` | Card borders, dividers |
| Primary (brand accent) | `#2563EB` | Primary buttons, links, active states |
| Primary Hover | `#1D4ED8` | Button hover state |
| Danger / High Risk | `#DC2626` | High risk score badge, "Block" button, halt actions |
| Warning / Medium Risk | `#D97706` | Medium risk score badge, pending-review indicators |
| Success / Low Risk | `#16A34A` | Low risk score badge, "blocked successfully" confirmation |
| Info | `#0891B2` | Simulated-conversation badge (to visually distinguish from real SMS) |

### Typography

| Use | Font | Size | Weight |
|---|---|---|---|
| Page titles | Inter (or system-ui fallback) | 24px | 700 |
| Section headers | Inter | 18px | 600 |
| Body text | Inter | 14px | 400 |
| Conversation bubble text | Inter | 15px | 400 |
| Captions/timestamps | Inter | 12px | 400, color: Slate |
| Risk score number (large display) | Inter | 40px | 800 |

### Component Styles

**Buttons**
- Primary: background `#2563EB`, text white, 8px border radius, 10px/16px vertical/horizontal padding, hover darkens to `#1D4ED8`.
- Danger (Block/Halt): background `#DC2626`, text white, same shape as primary.
- Secondary/ghost (Edit): transparent background, 1px `#E5E7EB` border, `#111827` text.

**Inputs**
- White background, 1px `#E5E7EB` border, 8px radius, 10px padding, focus state adds a 2px `#2563EB` outline ring.

**Cards**
- White (`#FFFFFF`) background, 1px `#E5E7EB` border, 12px radius, 16px internal padding, subtle shadow (`0 1px 2px rgba(0,0,0,0.05)`).

**Modals** (used for the review-queue Approve/Edit/Halt confirmation)
- Centered overlay, `rgba(0,0,0,0.4)` backdrop, white modal card, 16px radius, max-width 480px, close button top-right.

### Spacing & Layout Rules

- Base spacing unit: **4px** — all margins/paddings are multiples of 4 (4, 8, 12, 16, 24, 32).
- Page layout: fixed left sidebar (nav between Analyst Dashboard / Institution Dashboard) at 240px width, main content area fills remaining space with 24px padding.
- Conversation view: two-column layout — transcript on the left (60% width), risk score + indicator panel on the right (40% width), stacking vertically on narrow/mobile viewports.
- Max content width for readability: 1200px, centered.

---

## 2. Full API & Integration Spec — Third-Party Services

### Twilio (Programmable SMS)

**What it does:** sends and receives real SMS messages on your behalf via a phone number you provision through them.

**Inbound (webhook, Twilio calls you):**
```
POST https://your-backend.com/webhook/sms
Content-Type: application/x-www-form-urlencoded

Fields received: From, To, Body, MessageSid, (MediaUrl0+ if MMS)
```
Your backend must respond with HTTP 200 (an empty response, or valid TwiML) quickly — Twilio expects a fast acknowledgment and will retry if it doesn't get one.

**Outbound (you call Twilio):**
```
POST https://api.twilio.com/2010-04-01/Accounts/{AccountSid}/Messages.json
Auth: Basic (AccountSid : AuthToken)

Body sent: To=<scammer number>, From=<your Twilio number>, Body=<persona's reply text>
Response expected: 201 Created, JSON with a "sid" (message ID) and "status" field
```

### LLM Provider (Anthropic API)

**What it does:** two separate uses — (1) generates the honeypot persona's next reply, (2) analyzes a full transcript for risk.

**Persona reply call:**
```
POST https://api.anthropic.com/v1/messages
Headers: x-api-key, anthropic-version

Body sent: { model, system: <persona system prompt>, messages: [...conversation turns...],
             max_tokens: 300 }
Response expected: content block containing structured JSON:
  { "reply": "...", "flagged_action": "payment_request" | "platform_move" | null }
```

**Risk analysis call:**
```
POST https://api.anthropic.com/v1/messages
Body sent: { model, system: <risk-analysis instructions>, messages: [{"role":"user",
             "content": <full transcript text>}], max_tokens: 500 }
Response expected: structured JSON:
  { "risk_score": 0-100, "classification": "...", "reasons": ["...", "..."] }
```
**Note:** validate both responses against the expected schema before use — see the Error Handling Guide in the Security & Access Document.

### n8n (should-have enrichment)

**What it does:** runs the background enrichment workflow (WHOIS/domain-age + public blocklist check) on extracted URLs, outside the main request path.

**Trigger (your backend calls n8n):**
```
POST https://your-n8n-instance.com/webhook/enrich
Body sent: { "analysis_id": "...", "indicators": [ { "type": "url", "value": "..." }, ... ] }
```

**Callback (n8n calls your backend when done):**
```
POST https://your-backend.com/webhook/enrichment-result
Body sent: { "indicator_id": "...", "known_bad": true|false, "domain_age_days": 12 }
Response expected: HTTP 200
```

### Public WHOIS/RDAP Lookup (used inside the n8n workflow)
**What it does:** returns a domain's registration date, used to flag very-recently-registered domains as suspicious.
```
GET https://rdap.org/domain/<domain>
Response expected: JSON including an "events" array with an event of type "registration" and its date
```

### Public URL/Domain Blocklist API (used inside the n8n workflow)
**What it does:** checks whether a URL/domain has already been reported as malicious.
```
GET https://<chosen-blocklist-provider>/api/v1/check?url=<url>
Response expected: JSON with a boolean or category field indicating known-malicious status
```
*(Pick one free-tier provider at build time and fill in the exact endpoint — several exist; this is a placeholder shape, not a specific vendor endorsement.)*
