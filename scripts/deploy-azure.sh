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
regions=(westus canadacentral westus2)
if [[ -n ${AZURE_LOCATION:-} ]]; then
  case "$AZURE_LOCATION" in
    westus|canadacentral|westus2) regions=("$AZURE_LOCATION") ;;
    *) echo "Allowed regions are westus, canadacentral, westus2 only." >&2; exit 1 ;;
  esac
fi
app_name=${APP_NAME:-supportshield-$(python3 -c 'import secrets; print(secrets.token_hex(5))')}
plan_name=${PLAN_NAME:-supportshield-free-plan}
# Free tier only. Never silently fall back to a paid plan.
if [[ ${APP_SERVICE_SKU:-F1} != F1 ]]; then
  echo 'This script only creates the F1 free tier. Review Azure prices before choosing a paid alternative.' >&2
  exit 1
fi
subscription_type=$(az account show --query name --output tsv)
echo "Selected subscription: $subscription_type"
echo "Application: $app_name; resource group: $resource_group; SKU: Linux F1 only"
# Resource-group metadata stays in an allowed region. Plans get an explicit location.
group_exists=$(az group exists --name "$resource_group" --output tsv)
if [[ $group_exists == true ]]; then
  echo "Reusing existing resource group $resource_group without changing its metadata location."
else
  az group create --name "$resource_group" --location "${regions[0]}" --output none
fi
plan_base="$plan_name"
selected_plan=''
plan_error=$(mktemp)
trap 'rm -f "$plan_error"' EXIT
for location in "${regions[@]}"; do
  candidate_plan="${plan_base}-${location}"
  existing_plan=$(az appservice plan show --name "$candidate_plan" --resource-group "$resource_group" --output json 2>/dev/null || true)
  if [[ -n $existing_plan ]]; then
    # Never downgrade, relocate, or convert an existing plan.
    if ! printf '%s' "$existing_plan" | python3 -c '
import json, sys
plan = json.load(sys.stdin)
region = plan.get("location", "").lower().replace(" ", "")
sys.exit(0 if plan.get("sku", {}).get("name") == "F1" and plan.get("reserved") is True and region == sys.argv[1] else 1)
' "$location"; then
      echo "Existing plan $candidate_plan does not match Linux F1 in $location; leaving it unchanged." >&2
      continue
    fi
    selected_plan="$candidate_plan"
    echo "Reusing Linux F1 plan in $location."
    break
  fi
  echo "Trying Linux F1 in $location..."
  if az appservice plan create --name "$candidate_plan" --resource-group "$resource_group" --location "$location" --is-linux --sku F1 --output none 2>"$plan_error"; then
    selected_plan="$candidate_plan"
    echo "Linux F1 plan creation succeeded in $location."
    break
  fi
  echo "Azure rejected the Linux F1 attempt in $location. Error:" >&2
  cat "$plan_error" >&2
  # A rejection can mean capacity, quota, policy, or authorization; do not call it
  # proven SKU unavailability or change to a paid plan.
done
rm -f "$plan_error"
if [[ -z $selected_plan ]]; then
  echo 'No usable Linux F1 plan was established in the allowed regions. No paid plan was requested.' >&2
  echo 'Review the Azure errors above. The resource group may remain; no app was deployed by this run.' >&2
  exit 1
fi
plan_name="$selected_plan"
existing_app_plan=$(az webapp show --name "$app_name" --resource-group "$resource_group" --query serverFarmId --output tsv 2>/dev/null || true)
if [[ -n $existing_app_plan ]]; then
  selected_plan_id=$(az appservice plan show --name "$plan_name" --resource-group "$resource_group" --query id --output tsv)
  if [[ ${existing_app_plan,,} != ${selected_plan_id,,} ]]; then
    echo 'The existing app uses another plan. Leaving it unchanged; use its original region/plan or a new APP_NAME.' >&2
    exit 1
  fi
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
