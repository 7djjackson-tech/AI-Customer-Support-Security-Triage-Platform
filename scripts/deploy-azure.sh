#!/usr/bin/env bash
# Run in authenticated Azure Cloud Shell (Bash), from the cloned repository.
set -euo pipefail
# Never enable shell tracing: settings include the private session-signing key.
set +x
command -v az >/dev/null || { echo 'Run this in Azure Cloud Shell (Bash), where az is installed.' >&2; exit 1; }
az account show --output none
project_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$project_root"
resource_group=${RESOURCE_GROUP:-supportshield-demo-rg}
location=${AZURE_LOCATION:-eastus}
app_name=${APP_NAME:-supportshield-$(python3 -c 'import secrets; print(secrets.token_hex(5))')}
plan_name=${PLAN_NAME:-supportshield-free-plan}
# Free tier only. Never silently fall back to a paid plan.
if [[ ${APP_SERVICE_SKU:-F1} != F1 ]]; then
  echo 'This script only creates the F1 free tier. Review Azure prices before choosing a paid alternative.' >&2
  exit 1
fi
subscription_type=$(az account show --query name --output tsv)
echo "Selected subscription: $subscription_type"
echo "Application: $app_name; resource group: $resource_group; region: $location; SKU: F1 (free tier)"
az group create --name "$resource_group" --location "$location" --output none
existing_sku=$(az appservice plan show --name "$plan_name" --resource-group "$resource_group" --query sku.name --output tsv 2>/dev/null || true)
if [[ -n $existing_sku && $existing_sku != F1 ]]; then
  echo 'An existing plan with this name has another SKU. Choose a new PLAN_NAME; this script will not change that plan.' >&2
  exit 1
fi
if ! az appservice plan create --name "$plan_name" --resource-group "$resource_group" --is-linux --sku F1 --output none; then
  echo 'Free Linux capacity/SKU is unavailable in this region or subscription. No paid plan was selected. Review the Azure error and choose another supported region.' >&2
  exit 1
fi
az webapp create --name "$app_name" --resource-group "$resource_group" --plan "$plan_name" --runtime 'PYTHON:3.12' --output none
az webapp update --name "$app_name" --resource-group "$resource_group" --https-only true --output none
# Preserve a pre-existing signing key during a deliberate redeployment.
signing_key=$(az webapp config appsettings list --name "$app_name" --resource-group "$resource_group" --query "[?name=='SECRET_KEY'].value | [0]" --output tsv)
if [[ -z $signing_key ]]; then
  signing_key=$(python3 -c 'import secrets; print(secrets.token_hex(32))')
fi
# JSON settings file keeps private values out of command arguments and Git.
settings_file=$(mktemp)
archive_file=$(mktemp --suffix=.zip)
chmod 600 "$settings_file"
trap 'rm -f "$settings_file" "$archive_file"' EXIT
export SUPPORTSHIELD_DEPLOY_KEY="$signing_key"
python3 - "$settings_file" <<'PY'
import json, os, sys
with open(sys.argv[1], 'w') as file:
    json.dump({'SECRET_KEY': os.environ['SUPPORTSHIELD_DEPLOY_KEY'],
               'DATABASE_PATH': '/home/supportshield/supportshield.sqlite3',
               'COOKIE_SECURE': 'true', 'PRODUCTION': 'true',
               'LIVE_AI_ENABLED': 'false', 'SCM_DO_BUILD_DURING_DEPLOYMENT': 'true'}, file)
PY
unset SUPPORTSHIELD_DEPLOY_KEY signing_key
az webapp config appsettings set --name "$app_name" --resource-group "$resource_group" --settings "@$settings_file" --output none
az webapp config set --name "$app_name" --resource-group "$resource_group" --startup-file "gunicorn --bind 0.0.0.0:8000 --workers 1 --threads 2 --timeout 60 'app:create_app()'" --output none
git archive --format=zip --output="$archive_file" HEAD
az webapp deploy --name "$app_name" --resource-group "$resource_group" --src-path "$archive_file" --type zip --output none
hostname=$(az webapp show --name "$app_name" --resource-group "$resource_group" --query defaultHostName --output tsv)
echo "Deployment command finished. Public demo: https://$hostname/demo"
echo "Health check: https://$hostname/health"
echo 'Verify both URLs in your browser before claiming the site is online.'
echo 'No staff account exists on a new deployment. The public demo needs none.'
echo 'To enable private staff access, open App Service > SSH and run:'
echo 'cd /home/site/wwwroot && python -m flask --app app:create_app create-staff --username admin --role admin'
echo "Delete resources when no longer needed: az group delete --name $resource_group"
