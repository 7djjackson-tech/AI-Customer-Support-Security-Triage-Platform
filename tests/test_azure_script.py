"""Mocked CLI checks prove script choices, not Azure availability/deployment."""
import json
import os
from pathlib import Path
import subprocess

import pytest

pytestmark = pytest.mark.skipif(os.name == "nt", reason="Azure Cloud Shell deployment script requires Linux Bash")


@pytest.fixture
def run_deployment(tmp_path):
    binary = tmp_path / 'az'
    log = tmp_path / 'calls.jsonl'
    binary.write_text('''#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
with open(os.environ['MOCK_AZ_LOG'], 'a') as log:
    log.write(json.dumps(args) + '\\n')
if args[:2] == ['account', 'show']:
    if '--query' in args: print('Test subscription')
elif args[:3] == ['appservice', 'plan', 'show']:
    name = args[args.index('--name') + 1]
    if os.environ.get('MOCK_EXISTING_PAID') == 'true' and name.endswith('-westus'):
        print(json.dumps({'sku': {'name':'B1'}, 'reserved':True, 'location':'westus'}))
    else: sys.exit(1)
elif args[:3] == ['appservice', 'plan', 'create']:
    location = args[args.index('--location') + 1]
    assert args[args.index('--sku') + 1] == 'F1'
    assert '--is-linux' in args
    if location != os.environ.get('MOCK_SUCCESS_REGION'):
        print('Mock Azure rejection for ' + location, file=sys.stderr)
        sys.exit(1)
elif args[:2] == ['webapp', 'show']:
    if args[args.index('--query') + 1] == 'defaultHostName':
        print('mock-supportshield.invalid')
''')
    binary.chmod(0o755)

    def run(**variables):
        env = dict(os.environ, PATH=str(tmp_path) + os.pathsep + os.environ['PATH'],
                   MOCK_AZ_LOG=str(log), APP_NAME='supportshield-test-only')
        env.pop('AZURE_LOCATION', None)
        env.pop('APP_SERVICE_SKU', None)
        env.update(variables)
        result = subprocess.run(['bash', 'scripts/deploy-azure.sh'], env=env,
                                text=True, capture_output=True)
        calls = [json.loads(line) for line in log.read_text().splitlines()]
        return result, calls
    return run


def plan_calls(calls):
    return [call for call in calls if call[:3] == ['appservice', 'plan', 'create']]


def test_allowed_region_fallback_order_and_linux_f1_only(run_deployment):
    result, calls = run_deployment(MOCK_SUCCESS_REGION='westus2')
    assert result.returncode == 0, result.stderr
    plans = plan_calls(calls)
    assert [p[p.index('--location') + 1] for p in plans] == ['westus', 'canadacentral', 'westus2']
    assert all(p[p.index('--sku') + 1] == 'F1' and '--is-linux' in p for p in plans)
    assert any(c[:2] == ['webapp', 'deploy'] for c in calls)


def test_westus_success_stops_fallback(run_deployment):
    result, calls = run_deployment(MOCK_SUCCESS_REGION='westus')
    assert result.returncode == 0
    assert len(plan_calls(calls)) == 1


def test_all_failures_stop_before_app_creation(run_deployment):
    result, calls = run_deployment()
    assert result.returncode != 0
    assert len(plan_calls(calls)) == 3
    assert not any(c[:2] == ['webapp', 'create'] for c in calls)
    assert 'No paid plan was requested' in result.stderr


@pytest.mark.parametrize('variables', [{'AZURE_LOCATION':'eastus'}, {'APP_SERVICE_SKU':'B1'}])
def test_disallowed_regions_and_paid_tiers_rejected(run_deployment, variables):
    result, calls = run_deployment(**variables)
    assert result.returncode != 0
    assert not plan_calls(calls)
    assert not any(c[:2] == ['group', 'create'] for c in calls)


def test_existing_paid_plan_is_left_unchanged(run_deployment):
    result, calls = run_deployment(MOCK_EXISTING_PAID='true', MOCK_SUCCESS_REGION='canadacentral')
    assert result.returncode == 0
    assert [p[p.index('--location') + 1] for p in plan_calls(calls)] == ['canadacentral']
    assert 'leaving it unchanged' in result.stderr
