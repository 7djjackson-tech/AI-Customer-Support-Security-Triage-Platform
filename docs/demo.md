# Five-minute interview walkthrough

1. Follow the README Windows or Linux instructions, create your private administrator, and sign in. Explain the fictional Northstar Goods retailer and the no-automatic-actions boundary.
2. Import `data/development.csv`: eight fictional tickets appear. Reimport it to show zero new tickets and eight skipped IDs. Explain whole-file validation and unique IDs.
3. Create a customer-service user and a security user in **Staff access**, using private passwords. Sign out and in as customer service. Only ordinary tickets are visible. Search for “Missing” and open the missing-parcel ticket.
4. Generate a **rules-based demo**. Show source, summary, category, routing, draft, uncertainty, and policy references. Edit the response, enter a concise rationale, and save manual/edited review. The response is stored, never sent. Update status and show audit history.
5. Sign in as security and open the account-takeover example. Show quoted evidence and mandatory routing. Explain why a flag means “investigate”, not “confirmed breach”. An ordinary user attempting its URL receives HTTP 403.
6. Open **Demo evaluation**: 87.5% category accuracy, no false alerts among 16 ordinary examples, one miss among eight incident examples. Explain the small dataset and missed unfamiliar wording; these are not live AI metrics.
7. Describe optional live AI configuration, validation, source separation, timeout/failure fallback, and manual review. No live call is required for this demo.

Interview pitch: “Retail customer-service experience helped me design an organized inbox and clear handoffs. My cybersecurity coursework informed server-side permissions, quoted security evidence, and untrusted-input handling. I chose Flask, templates, and SQLite so I can explain every component. I measured the demo rules and documented their missed incident rather than claiming perfect AI accuracy.”
