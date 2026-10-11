# Optional live AI: choices and costs

Demo is deterministic, free of provider fees, and needs no API key. Keep it as the default for interviews. Live AI is optional and has not been called or evaluated during this build.

| Option | Fit | Cost/operational considerations |
| --- | --- | --- |
| OpenAI API | Small structured-output adapter included | Metered input/output tokens; separate API billing; model access varies. Chat subscriptions do not establish API credit. |
| Azure OpenAI | Future Azure integration | Requires an Azure OpenAI deployment, supported region, access and billing; student subscription eligibility and credits must be checked. No adapter implemented here. |
| Local model | Future offline experiment | No hosted token fee; hardware/RAM requirements and weaker structured-output compliance may complicate a small project. No adapter implemented here. |

For 1,000 fictional requests averaging 1,500 input and 300 output tokens: **estimated cost = 1.5 × current input price per million tokens + 0.3 × current output price per million tokens**. As a purely illustrative calculation, hypothetical rates of $0.20 input and $0.80 output would yield **$0.54** for those requests. Those are assumptions, not a quoted current provider price. Actual prompt lengths, retries, model choice, taxes, and hosting can increase cost. Check https://openai.com/api/pricing/ and https://azure.microsoft.com/pricing/details/cognitive-services/openai-service/ before enabling. Set provider budget controls; this app does not enforce a monetary budget.

## Enable deliberately

Set `LIVE_AI_ENABLED=true`, `SUPPORTSHIELD_AI_KEY` privately, and optionally `AI_MODEL` to a structured-output-compatible OpenAI model. The default is `gpt-4o-mini`, subject to account availability. In PowerShell:

```powershell
$env:LIVE_AI_ENABLED = "true"
# Set SUPPORTSHIELD_AI_KEY securely outside source control; do not paste it into screenshots or Git.
```

Restart the server. A separate live button appears. Each call requires confirmation that the fictional message may be sent to OpenAI. Output is marked `live` and stored separately from `demo`; failure produces a source-labeled `demo_fallback`, never a fabricated live result.

The request uses JSON schema structured output. Local validation checks exact fields, allowed categories/priority/routing, text bounds, evidence quoted from the supplied message, and known policy identifiers. Mandatory account-takeover rules then override an unsafe routing suggestion. Known policy IDs do not prove every draft sentence is supported: a human must review. No accounts or email tools are exposed to the model.

## Evaluate live only when configured

```powershell
.\.venv\Scripts\python.exe evaluate.py --mode live --output instance/evaluation-live.json
```

This makes 24 billable requests with fictional evaluation data. Live evaluation refuses to run without opt-in and key. Failed-provider/fallback cases are counted separately and excluded from live accuracy denominators, so demo results never inflate live metrics. Live output must use a separate path; never overwrite the committed demo report. No live metrics are reported in this project yet.
