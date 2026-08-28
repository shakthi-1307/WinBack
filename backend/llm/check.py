"""Diagnose the model connection, before a run depends on it.

    python -m backend.llm.check

Prints the provider's actual complaint rather than a stack trace, because
"HTTP 403" on its own has never helped anybody.
"""

from __future__ import annotations

import os
import sys

from backend.config.env import ensure_loaded
from backend.config.secrets import mask
from backend.llm.live_client import DEFAULT_BASE_URL, DEFAULT_MODEL, LiveClient

HINTS = {
    401: "The API key is wrong, revoked, or from a different provider.",
    403: ("The key is recognised but not permitted to use this model. Usually "
          "the model name is wrong or retired — check the provider's current "
          "model list and set WINBACK_MODEL to one you actually have access to."),
    404: "The model name does not exist at this endpoint. Check WINBACK_MODEL.",
    429: "Rate limited. Wait, or use a smaller model.",
}


def main() -> int:
    ensure_loaded()
    key = os.environ.get("WINBACK_API_KEY")

    print("model connection check")
    print(f"  endpoint  {os.environ.get('WINBACK_BASE_URL', DEFAULT_BASE_URL)}")
    print(f"  model     {os.environ.get('WINBACK_MODEL', DEFAULT_MODEL)}")
    print(f"  key       {mask(key) if key else '— not set'}")
    print()

    if not key:
        print("No WINBACK_API_KEY set. Winback will use the deterministic")
        print("scripted model, which is a supported mode — the rule tier")
        print("decides four fifths of every batch either way.")
        return 0

    client = LiveClient()
    result = client.complete_json(
        'Reply with JSON only.',
        'Return {"ok": true}',
        ["ok"],
    )

    if result:
        print("OK — the model answered.")
        print(f"  tokens in/out  {client.usage.prompt_tokens}/"
              f"{client.usage.completion_tokens}")
        return 0

    print("FAILED")
    print(f"  {client.usage.last_error}")
    for code, hint in HINTS.items():
        if f"HTTP {code}" in client.usage.last_error:
            print()
            print(f"  {hint}")
            break
    print()
    print("Winback will still run: model failures fall back to the rule tier,")
    print("which handles most of the batch anyway. But fix this to get the")
    print("gray-zone judgement the investigator is for.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
