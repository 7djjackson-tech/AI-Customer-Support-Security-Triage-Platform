# Put SupportShield online with Azure for Students

The repository is deployment-ready, but **no Azure deployment has been executed from the development workspace**: it has no authenticated session for your Azure subscription. Run the included script in your own authenticated Azure Cloud Shell. There is no need to share credentials in chat.

## What visitors will see

The home page opens a public demo with eight bundled fictional scenarios. Visitors select a scenario and inspect its summary, category, priority, routing, security evidence, uncertainty, and policy-grounded draft. The demo needs no account, makes no paid AI calls, stores no visitor text, and cannot mutate or display private SQLite tickets. Staff still sign in to use import, review, audit history, and administrator controls. Never publish a shared administrator password.

## Deploy from your browser

1. Open https://portal.azure.com and sign in with the account that has **Azure for Students**.
2. Click the **Cloud Shell** button (`>_`) in the top toolbar. Select **Bash** (not PowerShell). If prompted, choose your Azure for Students subscription. Use the temporary/no-storage session when available to avoid creating a separate storage resource. Cloud Shell options may vary.
3. Confirm your active subscription with `az account show --query name --output tsv`. If it is wrong, select the right subscription before continuing with `az account set --subscription "YOUR SUBSCRIPTION NAME"`.
4. Paste this into Cloud Shell:

```bash
git clone https://github.com/7djjackson-tech/AI-Customer-Support-Security-Triage-Platform.git
cd AI-Customer-Support-Security-Triage-Platform
bash scripts/deploy-azure.sh
```

If already cloned in that Cloud Shell, run `git pull` inside the project instead of cloning again. The script creates a dedicated resource group, a Linux App Service **F1 free-tier** plan, and a uniquely named app. It sets HTTPS-only, secure cookies, a private stable signing key, persistent database path, and live AI off. It archives committed source only and deploys with a dependency build and Gunicorn startup command. The private signing key is never printed or committed.

The script does not request a paid SKU or silently upgrade if F1 is unavailable. Free-tier availability, quotas, and subscription support differ by region. A failure is not evidence that a paid upgrade is required. Review the error first. You can try a supported region with `AZURE_LOCATION=YOUR_REGION bash scripts/deploy-azure.sh`. A resource group may remain after a failure; inspect it in the portal and remove unused resources. Do not change another existing App Service plan to make deployment pass.

After a successful deployment command, the terminal prints the **actual app URL**, such as `https://supportshield-<generated-name>.azurewebsites.net/demo`. Open the printed URL. It also prints `/health`, which should return `{"status":"ok"}`. Free-tier cold starts can take time. A printed URL alone is not proof of a working website: verify both pages.

## Optional private staff setup

The public demo works without creating any staff account. To enable your private staff workspace:

1. Open the new App Service resource in the portal and choose **SSH** (under Development Tools; UI placement may vary).
2. In its shell, run:

```bash
cd /home/site/wwwroot
python -m flask --app app:create_app create-staff --username admin --role admin
```

3. Enter a private password of at least 12 characters twice; it is not displayed. Open your site's `/login`, sign in, and import `data/development.csv`. Create individual staff accounts using Staff access. Never post your administrator credentials publicly.

## Persistence, redeployment, and limits

SQLite uses `/home/supportshield/supportshield.sqlite3`; App Service Linux persistent `/home` storage must be verified in your chosen hosting mode. The command uses one Gunicorn worker and two threads. Keep this SQLite demo on one instance; do not scale horizontally. The F1 tier has CPU/resource limits and cold starts, so it is a portfolio demo, not a production service or availability guarantee. Confirm the selected offer's current terms and your spending controls in the Azure portal.

For redeployment, preserve the app identity: set `APP_NAME` to the existing app name, pull the source, and run the script again. Optional `RESOURCE_GROUP`, `PLAN_NAME`, and `AZURE_LOCATION` must match the existing resources. Existing SECRET_KEY is preserved. Omitting APP_NAME generates a new app each time. Do not commit the SQLite database or your local `.venv`.

## Verify before sharing

- Open `/demo` without logging in and try every scenario. Check `/health`.
- Verify Secure/HTTP-only cookies, HTTPS-only, and no public staff registration.
- If using staff features, check role-specific list/detail/review/status access and forbidden URLs.
- Restart the App Service and confirm staff/tickets/audit records persist.
- Back up SQLite using its supported backup operation; test restoration separately before relying on it.
- Check logs and costs; do not enable live AI without explicit budget and provider configuration.

To remove the dedicated demo resources when finished, review the group contents in the portal and delete only that dedicated group. The script prints a cleanup command. No paid resources or live AI have been provisioned from this workspace.

Current evidence: local public-demo tests and Linux HTTP smoke pass. Azure authentication, actual resource creation, remote dependency build, public HTTPS behavior, persistence/restore, and free-tier eligibility remain unverified until you execute and check the deployment. Official Python App Service guide: https://learn.microsoft.com/azure/app-service/quickstart-python
