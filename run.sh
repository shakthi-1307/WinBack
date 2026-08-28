#!/usr/bin/env bash
# Everything, in the order a reviewer would want it.
set -e

echo "== configuration =="
python -m backend.config
echo
echo "== batch evaluation (measurement — no network) =="
python -m backend.evaluation.harness --replay
echo
echo "== sensitivity =="
python -m backend.evaluation.sensitivity
echo
echo "== attack suite =="
python -m backend.attacks.suite
echo
echo "== tests =="
python -m pytest tests/ -q
echo
echo "Integration proof (needs Razorpay test keys in .env):"
echo "  python -m backend.evaluation.live_proof"
echo
echo "Console:"
echo "  uvicorn backend.api.app:app --reload   then open http://localhost:8000"
