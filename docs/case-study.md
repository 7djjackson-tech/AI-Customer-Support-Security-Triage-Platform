# SupportShield case study

## Business problem

A fictional retailer receives routine returns and delivery questions alongside account-access and suspicious-activity reports. Staff need a consistent queue, security handoffs, draft responses grounded in company policy, and records of human decisions. Retail customer-service experience provides the workflow context; software and cybersecurity coursework inform the implementation.

## Design decisions

Python/Flask with server-rendered HTML keeps the stack small and understandable. SQLite avoids an external database dependency. There are two core application modules and no frontend build pipeline. CSV imports validate the entire batch before transactional writes; unique external IDs prevent duplicate intake. All examples and policies are fictional.

Staff authenticate with established scrypt password hashing. Roles restrict both queue queries and individual routes; hiding links alone is insufficient. Administrators manage roles and import datasets. Security routing is sticky so a later AI recommendation cannot silently move a flagged ticket back to ordinary support. Exact pattern matches appear as evidence alongside uncertainty.

The rules-based demo precedes optional live AI so the project works offline and remains honest about what is being evaluated. Provider output is structurally validated; mandatory takeover rules run after it. Failed live requests get separately labeled demo fallback. Each recommendation version retains its source, and stale review forms cannot approve a different newer version. Staff can approve, manually edit, or reject; audit entries commit with actions. No sending or account changes occur.

## Measured outcomes

On 24 separate author-labeled evaluation examples, the deterministic demo classified **21 correctly (87.5%)**. It produced **zero false security alerts among 16 ordinary examples**, and **missed one of eight security incidents (12.5%)**. It missed “Somebody else is using my profile to buy things”, misclassified a double charge as a general question, and treated a refund-related embedded instruction as a refund request. The embedded command was not executed.

These errors show how keyword rules lack semantic understanding. I retained the results instead of tuning against evaluation labels to claim a perfect score. The dataset is small and authored alongside the project, so it is not independent external validation. Development examples are stored separately. No live AI accuracy or time savings are claimed.

The validation report records actual unit/integration and HTTP smoke results. Tests exercise role boundaries, direct URL access, CSRF, import validation, review records, stale versions, schema rejection, API failures, and reproduction of metrics. Live-provider responses are mocked in tests; no paid request was made.

## Limits and next steps

This is a portfolio prototype for fictional data. Structural checks do not guarantee semantic grounding or eliminate prompt injection. Audit data is not tamper-proof against machine/database administrators. Basic throttling, mutually exclusive staff roles, final reviews, and sticky flags are intentional scope choices. Production adoption would require deeper threat modeling, broader labeled data, a clearance/reopen workflow, backup/retention controls, MFA/recovery, robust rate limiting, and concurrency/scaling work.

Azure for Students deployment has been prepared in documentation, not executed. A small single-instance App Service with persistent SQLite is a possible demo host; credit eligibility and service prices must be verified before creation.
