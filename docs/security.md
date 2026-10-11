# Security model

All inputs and examples must be fictional. Authentication uses Werkzeug's scrypt implementation; no shared passwords are distributed. Sessions contain staff IDs only, expire after eight hours, and use HTTP-only/SameSite=Lax cookies. Roles are read from SQLite on every request so changes immediately affect existing sessions. Set COOKIE_SECURE=true on HTTPS hosting and use a stable private SECRET_KEY.

| Capability | Customer service | Security | Administrator |
| --- | --- | --- | --- |
| Ordinary ticket list/detail/review/status | Yes | No | Yes |
| Security ticket list/detail/review/status | No | Yes | Yes |
| CSV import | No | No | Yes |
| Create staff/change roles | No | No | Yes |
| Demo evaluation summary | Yes | Yes | Yes |

Every detail and mutation route checks role scope on the server, including direct URLs. The dashboard query applies the same scope; counts do not include another role's tickets. Recommendations that promote an ordinary ticket to security end customer-service access immediately. The last administrator cannot be demoted through the UI. Public health checks return no ticket data.

All POST forms require CSRF tokens. SQL uses bound values; the only interpolated schema/scope fragments come from fixed application constants. Jinja autoescaping is retained; no customer text is rendered as trusted HTML. Uploads have request/row/field limits and validate before inserts. Browser CSP disallows scripts and external assets; responses prevent caching and cross-origin referrer leakage.

Login throttling blocks a username for fifteen minutes after five failures. Unknown users also incur a password-hash check. This simple local throttle permits account-lockout abuse and is not a production distributed rate limiter. Database administrators and filesystem access remain trusted. There is no public registration, MFA, or recovery workflow.

## Mandatory escalation rules

`triage.security_evidence` matches bounded, case-insensitive patterns for:

- An account described as taken over, hacked, or compromised.
- Someone/attacker changing or accessing an account or placing an order.
- Unauthorized account/order/login/access/change/purchase reports.
- Email/password changes without permission or consent.
- An order or purchase the reporter says they did not authorize or place.
- A “not me” report associated with login/sign-in/order activity.

The exact matching substring is shown as evidence. These rules are applied after model validation and cannot be bypassed by an AI category. Import also uses the demo security routing guard, including suspicious-email signals. Once escalated, a ticket remains security-only until a future explicit clearance workflow is implemented. A flag requests investigation; it does not declare a breach.

Rules are intentionally simple: negations can cause false flags and unfamiliar wording can be missed. The evaluation includes a missed indirect report. Staff can manually escalate by selecting the security category. Customer instructions embedded in text never execute in demo mode. Live prompts place messages in a JSON data field and explicitly reject embedded instructions; output must match the schema, quote actual evidence, and cite known policies. This reduces risk but does not guarantee semantic safety.

## Audit and provider boundaries

Imports, recommendation generation, reviews, status changes, staff creation, and UI role changes are audited in the same write transaction as their changes. Audit rows contain actor, action, ticket reference, timestamp, and concise rationale. Recommendation runs are retained separately with source labels. App routes cannot edit audit history, but it is not cryptographically protected. Bootstrap CLI creation is a trusted local operator action and is not recorded as an authenticated reviewer action.

No customer messages or provider exception bodies are printed by app code. Tickets and recommendation history necessarily store fictional message content in SQLite. Review rationales should not contain secrets or full messages. No mail client or account-management integration exists. OpenAI calls go to one fixed HTTPS endpoint with TLS verification enabled and a timeout. There are no user-controlled provider URLs, tool calls, or automatic actions.
