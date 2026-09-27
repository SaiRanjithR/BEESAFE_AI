# TrapLine — Security & Access Document

*Written in plain English for a non-technical founder. Where a technical term is unavoidable, it's explained the first time it's used.*

## 1. Authentication Method — What Fits This Use Case

TrapLine has **no public sign-up and no real end users** — everyone who touches it is your own team, during a demo. That means you do **not** need heavy authentication (like requiring email/password logins with password reset flows, social login, etc.) — that would be real engineering effort spent on a problem you don't actually have in v1.

**Recommended: a single shared "API key"** — think of it like a password that every screen of your dashboard has to include when it talks to the backend. It's stored in one place (an environment variable, explained in the Technical Architecture Document) and typed into the frontend once per session. It is **not** meant to protect against a determined attacker — it's meant to stop the backend from being wide open to literally anyone on the internet who finds the URL.

**When you'd need to upgrade this:** the moment you have more than one person needing *different* levels of access (see roles below), or the moment this becomes a real product with real institutional customers, you'd move to a real login system with individual accounts — flagged here as a known future need, not something to build now.

## 2. User Roles — What Each Can and Cannot Do

| Role | Can do | Cannot do |
|---|---|---|
| **Analyst** | View all conversations; approve, edit, or halt a flagged reply in the review queue; view extracted indicators and risk scores | Cannot "Block" an indicator on the Institution Dashboard (that's a different role's action, kept separate so one screen doesn't do everything) |
| **Institution Viewer** (represents a bank/exchange/telco user, simulated for the demo) | View flagged indicators and their risk scores/evidence; click "Block" to mark an indicator as actioned | Cannot see the raw conversation transcript or persona details — a real institution would only ever receive the extracted indicator, never your internal decoy operation's private data |
| **Admin** (you, running the demo) | Everything above, plus: start/stop simulated-scammer-bot conversations, view audit logs, regenerate the API key | — |

**Why the Institution Viewer can't see the raw transcript:** this isn't just a technical nicety — it mirrors a real privacy boundary. A real bank should receive "this wallet address is confirmed fraudulent" as a fact, not the full private conversation your decoy had. Keeping this separation in your demo, even as a simulation, is the correct design and a good thing to say out loud to judges.

## 3. Row-Level Security Rules (Database)

"Row-level security" means: rules that decide which *rows* of a database table a given request is allowed to see or change, enforced by the database itself rather than trusted to each screen of the app remembering to filter correctly.

For TrapLine's scope, the rules are simple:

- **Every request must present a valid API key** (checked before touching the database at all) — no key, no data, full stop.
- **Institution Viewer requests may only read from `threat_indicators`**, and may only update the `status` field of a row (to `blocked`) — never read `messages` or `personas`, never write anything else.
- **Analyst requests may read `conversations`, `messages`, `threat_indicators`, and `risk_assessments`**, and may only write to `messages.review_status` (approve/edit/halt) — never directly edit a `risk_assessment` or an indicator's `status`.
- **Only the Twilio webhook endpoint may write new rows to `messages` with `role = scammer`** — this is enforced by that endpoint being the only code path allowed to write that specific combination, not by a database rule per se, but it's worth stating as a rule: nothing else in the system should ever be able to fabricate a fake "scammer said this" message.

For a hackathon build, these rules are enforced **in your backend code** (e.g., a permissions check function called at the top of each route) rather than as literal database-level policies (which Postgres does support, via a feature also called "row-level security," but setting that up is more setup than a time-boxed build needs) — note this as a real future upgrade if this becomes a production system with untrusted external users.

## 4. Error Handling Guide (Major Failure Points)

| Failure point | What could go wrong | What the system should do |
|---|---|---|
| Twilio webhook receives a malformed request | Missing `From` or `Body` field | Return HTTP 400, log it, do not crash the process |
| LLM API call fails or times out | Provider outage, rate limit, network blip | Retry once with backoff; if it still fails, hold the message in the review queue flagged as `system_error` rather than silently dropping it or sending a broken reply |
| LLM returns invalid/unparseable structured output | Model doesn't follow the JSON schema | Validate the response against the expected shape before using it; on failure, treat it the same as an API failure (above) — never pass raw unvalidated model output straight to Twilio or the database |
| Twilio send fails (e.g., number is invalid, account out of credit) | Reply approved but never delivered | Mark the message `send_failed` in the database (don't silently mark it as sent), surface this clearly on the dashboard |
| Two analysts try to approve the same queued reply at once | Race condition — same item, two clicks | Whoever's request reaches the database first wins; the second request gets a "this was already handled" response, not a duplicate send |
| Database connection drops mid-request | Backend can't reach Postgres | Return a clear error to the frontend ("system temporarily unavailable"), never show a blank/broken screen with no explanation |
| Extracted "indicator" is garbage (e.g., regex false-positive) | A normal sentence accidentally matches a wallet-address pattern | Don't silently trust extraction — display extracted indicators with a way for an analyst to dismiss a bad one, rather than treating extraction as infallible |
| Someone submits an extremely long conversation history | Hits LLM context-length limits | Truncate to the most recent N turns before sending to the LLM, and note in the persona's system prompt that earlier context may be summarized rather than exact |

## 5. Edge Cases to Handle Before Launch (or Demo)

- **The scammer (or simulated bot) sends something in a language other than English** — decide explicitly: does the persona agent respond in kind, or reply in English regardless? Pick one and be consistent; don't leave it undefined.
- **The scammer sends an image (MMS) when your MVP only supports text** — the system should acknowledge gracefully ("received but not processed" state) rather than crash or silently drop the message.
- **The same phone number contacts you twice, far apart in time** — decide whether this resumes the old conversation or starts a new one; don't let it silently merge into a confusing single thread with a large time gap.
- **A flagged reply sits in the review queue and nobody approves it for a long time** — during a live demo this could stall the whole conversation; have a visible "pending" state and a way to manually nudge/expire it rather than the demo silently hanging.
- **The simulated scammer bot and the real Twilio number both get used in the same demo session** — make sure the dashboard clearly labels which conversations are `simulated` vs `sms` (this field already exists in the schema) so nobody — team or judges — mistakes one for the other.
- **Someone clicks "Block" on an indicator that's already blocked** — should be a harmless no-op, not an error or a duplicate audit-log entry.
- **The persona agent tries to send a reply containing something it absolutely should never send** (a real-looking bank detail, an actual working link, anything resembling real PII) — this is the most important edge case in the whole system: your review-queue logic should treat "does this reply contain something risky" as a genuine content check, not just a check on whether the LLM flagged its own output as risky, since a model can fail to self-flag. A simple backend-side regex safety net (checking the *outgoing* persona reply, not just the *incoming* scammer message) catches this even if the LLM's self-reported `flagged_action` is wrong.
