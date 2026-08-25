#!/usr/bin/env bash
# Everything, in the order a reviewer would want it.
set -e

echo "== configuration =="
python -m backend.config
echo
echo "== batch evaluation =="
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
echo "Console:  uvicorn backend.api.app:app --reload   then open http://localhost:8000"
