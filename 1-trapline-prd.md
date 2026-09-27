# TrapLine — Product Requirements Document

*Assumption stated up front: this PRD covers the SMS honeypot + institution-dashboard system scoped across our conversation (Phases 1–7), built as a hackathon MVP. Rename "TrapLine" to whatever you're calling the project.*

---

## 1. What the App Does

TrapLine is a **B2B fraud-intelligence system** that uses an AI persona to hold real text-message conversations with suspected scammers, extracts the payment accounts and infrastructure they reveal (mule bank accounts, crypto wallets, phone numbers, malicious links), and surfaces that intelligence on a dashboard styled after a financial institution's fraud-operations screen — where a "Block" action represents what a bank, crypto exchange, or telco would do with that intelligence in production.

It does **not** talk to end consumers. The people protected by TrapLine never interact with it directly — protection happens because an institution acts on the intelligence it produces.

## 2. Who It's For

| Audience | Role |
|---|---|
| Financial institutions / banks | Primary target customer — receive mule-account intelligence to block/freeze transactions |
| Crypto exchanges | Target customer — receive wallet-address intelligence |
| Telcos | Target customer — receive scammer phone-number intelligence |
| Internal fraud/trust & safety analysts | Actual daily user of the product — review flagged conversations, approve/edit sensitive replies, action alerts |
| Hackathon judges (for this build specifically) | Demo audience, not a real user persona — but shapes MVP scope below |

## 3. What Problem It Solves

Trust-based scams (romance scams, pig butchering, investment fraud) succeed because the victim **willingly authorizes** the transaction after weeks of relationship-building — so transaction-anomaly-based fraud systems, which look for *unauthorized* or *out-of-pattern* activity, don't catch it. Institutions typically only learn about these scams after a victim reports a loss, by which point funds have already moved through the mule account. TrapLine closes this gap by extracting the mule account/wallet/number **before** it's used against a real victim, by getting the scammer to reveal it directly to an AI decoy.

## 4. Core Features — Must-Have vs. Nice-to-Have

### Must-have (MVP, required for the judged demo)
1. **Honeypot persona agent** — LLM-driven, holds a multi-turn SMS conversation staying in character, never sends real payment/personal info.
2. **Real SMS channel via Twilio** — inbound webhook + outbound send.
3. **Simulated scammer bot** — second LLM persona for reliable, repeatable demo conversations, independent of real-world scam timing.
4. **Human-in-the-loop review queue** — any reply flagged as sensitive (payment ask, platform-move request) holds for human approve/edit/halt before sending.
5. **Indicator extraction** — regex-based pull of wallet addresses, phone numbers, URLs, payment handles from the transcript.
6. **Risk scoring** — LLM-based classification + plain-language reasons, run against the full transcript.
7. **Analyst dashboard** — conversation view with extracted indicators and risk score visible.
8. **Institution dashboard (simulated)** — a table of flagged accounts/wallets/numbers with a "Block" action that flips a status flag.

### Should-have (build if MVP is solid early)
9. n8n enrichment workflow (WHOIS/domain-age lookup, public URL blocklist check) on extracted URLs.
10. Multi-conversation correlation — flag when the same wallet/handle appears across more than one conversation.
11. "Explanation Agent" — separate from the risk-scoring agent, rewrites the risk reasons in warmer, more narrative language for the demo screen.

### Nice-to-have (cut without regret under time pressure)
12. Multimedia (MMS image) support with captioning.
13. A second real channel (e.g., WhatsApp-styled simulated UI, per earlier discussion).
14. Authentication beyond a single shared API key.
15. Historical trend charts (e.g., risk-score distribution over time).

## 5. User Flow (End to End)

**Analyst-side flow:**
1. Analyst opens the dashboard → sees list of active conversations (real Twilio number + simulated demo conversations).
2. Opens a conversation → sees full transcript so far.
3. If a reply is pending review (flagged action), analyst sees it highlighted with Approve / Edit / Halt controls.
4. Approves → reply sends (real SMS or simulated bot turn) → conversation updates live.
5. As the conversation grows, analyst sees extracted indicators appear in a side panel with a running risk score.
6. When risk score crosses a threshold, the conversation's indicators appear on the Institution Dashboard.

**Institution-dashboard flow (simulated "customer" view):**
1. Institution-side user (played by the demo presenter) opens the Institution Dashboard.
2. Sees a table: indicator type, value, source conversation, risk score, status (`pending` / `blocked`).
3. Clicks "Block" on a row → status flips to `blocked`, timestamped.

## 6. What the MVP Looks Like

A working, deployed (not just localhost) system where:
- A real Twilio number can receive and reply to an actual SMS conversation.
- A simulated scammer bot can run a full, scripted pig-butchering-style conversation against the honeypot agent on demand, for demo reliability.
- Every conversation shows extracted indicators and a risk score.
- At least one sensitive reply in the demo conversation is visibly held for human approval and approved live.
- The Institution Dashboard shows at least one flagged account being "blocked" live.

## 7. Success Metrics

| Metric | For the hackathon | For a real future version |
|---|---|---|
| Demo reliability | Simulated conversation completes end-to-end with zero manual intervention beyond the scripted human-review clicks | N/A |
| Judge-visible "aha" moment | Institution Dashboard block action clearly demonstrated | N/A |
| Extraction accuracy | Correctly extracts 100% of indicators seeded into the scripted demo conversation | Precision/recall against a labeled real-conversation test set |
| Risk scoring quality | Risk score for the demo conversation lands convincingly "high" with legible reasons | False-positive rate on known-benign conversations |
| (Future) Real-world value | N/A | Number of mule accounts flagged before reuse against a second victim |

## 8. What We Are Deliberately NOT Building in Version One

- **No real institutional integrations.** No actual bank, crypto exchange, or telco API connection — the Institution Dashboard is a simulation of that customer surface, explicitly labeled as such in the demo narrative.
- **No live engagement with real scammers as the primary demo path.** The Twilio number may run live in the background, but the judged demo relies on the simulated scammer bot for reliability.
- **No consumer-facing app or warning feature.** That is a separate, later product idea (the "paste your own conversation and get warned" concept) and is out of scope here.
- **No cross-institution mule-account correlation graph database.** Multi-conversation correlation (should-have #10) is a simple "same value seen twice" check, not a real link-analysis graph engine.
- **No custom-trained ML models.** All classification/scoring runs through prompted LLM API calls, not trained models.
- **No production-grade authentication/authorization.** A single shared API key stands in for real auth in v1 (see Security & Access Document).
- **No multilingual support.**
- **No WhatsApp/Instagram live automation** — ToS and reliability concerns, covered earlier; only a simulated UI, if built at all.
