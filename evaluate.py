"""Evaluate separate labeled data; no invented metrics or silent live fallback scoring."""

import argparse
import csv
import json
import os
from pathlib import Path
from triage import recommend


def evaluate(mode="demo"):
    if mode == "live" and (
        os.environ.get("LIVE_AI_ENABLED") != "true"
        or not os.environ.get("SUPPORTSHIELD_AI_KEY")
    ):
        raise ValueError(
            "Live evaluation requires LIVE_AI_ENABLED=true and SUPPORTSHIELD_AI_KEY; it is billable."
        )
    details = []
    with Path("data/evaluation.csv").open(encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            value, source, error = recommend(
                row["subject"] + "\n" + row["message"], mode
            )
            details.append(
                {
                    "id": row["external_id"],
                    "expected": row["expected_category"],
                    "predicted": value["category"],
                    "expected_security": row["expected_security"] == "1",
                    "predicted_security": value["routing"] == "security",
                    "source": source,
                    "error": bool(error),
                }
            )
    scored = [d for d in details if not d["error"]]
    correct = sum(d["expected"] == d["predicted"] for d in scored)
    actual_security = sum(d["expected_security"] for d in scored)
    ordinary = len(scored) - actual_security
    false_alerts = sum(
        d["predicted_security"] and not d["expected_security"] for d in scored
    )
    misses = sum(d["expected_security"] and not d["predicted_security"] for d in scored)
    return {
        "mode": mode,
        "label": (
            "Deterministic rules-based demo; not live AI"
            if mode == "demo"
            else "Live AI plus mandatory security rules"
        ),
        "dataset": "data/evaluation.csv",
        "total": len(details),
        "scored": len(scored),
        "service_failures_excluded": len(details) - len(scored),
        "correct_categories": correct,
        "classification_accuracy": correct / len(scored) if scored else None,
        "false_security_alerts": false_alerts,
        "ordinary_cases": ordinary,
        "false_alert_rate": false_alerts / ordinary if ordinary else None,
        "missed_security_incidents": misses,
        "security_cases": actual_security,
        "miss_rate": misses / actual_security if actual_security else None,
        "details": details,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["demo", "live"], default="demo")
    parser.add_argument("--output", default="docs/evaluation-demo.json")
    args = parser.parse_args()
    if args.mode == "live" and args.output == "docs/evaluation-demo.json":
        parser.error(
            "Use a separate --output path for live results, e.g. instance/evaluation-live.json"
        )
    try:
        result = evaluate(args.mode)
    except ValueError as error:
        parser.error(str(error))
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "details"}, indent=2))
