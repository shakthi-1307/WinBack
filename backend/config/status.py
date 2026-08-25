"""Human-readable report of what is configured. Reads nothing else."""

from __future__ import annotations

import os

from backend.config.env import ENV_PATH, ensure_loaded
from backend.config.mode import fake_gateway_permitted
from backend.config.secrets import mask

KNOWN_KEYS = {
    "WINBACK_API_KEY": "Model API key (Groq, OpenAI, or any compatible endpoint)",
    "WINBACK_BASE_URL": "Model endpoint. Defaults to Groq",
    "WINBACK_MODEL": "Model name. Defaults to llama-3.1-8b-instant",
    "RAZORPAY_KEY_ID": "Razorpay TEST key id (rzp_test_...)",
    "RAZORPAY_KEY_SECRET": "Razorpay TEST key secret",
}


def model_is_live() -> bool:
    return bool(os.environ.get("WINBACK_API_KEY"))


def gateway_is_live() -> bool:
    return bool(os.environ.get("RAZORPAY_KEY_ID") and os.environ.get("RAZORPAY_KEY_SECRET"))


def status() -> str:
    ensure_loaded()
    lines = [
        f".env file          {'found' if ENV_PATH.exists() else 'not present (optional)'}",
        f"                   {ENV_PATH}",
        "",
    ]
    for key, description in KNOWN_KEYS.items():
        value = os.environ.get(key)
        lines.append(f"  {key:<22}{(mask(value) if value else '— not set'):<22}{description}")

    lines += ["", "Effective mode:"]
    lines.append(
        "  model     LIVE (calls a real endpoint)" if model_is_live()
        else "  model     OFFLINE scripted stand-in — deterministic, no key needed"
    )
    lines.append(
        "  gateway   LIVE Razorpay test mode (creates real test orders)" if gateway_is_live()
        else ("  gateway   TEST DOUBLE — permitted by WINBACK_ALLOW_FAKE_GATEWAY"
              if fake_gateway_permitted()
              else "  gateway   NOT CONFIGURED — runs are REFUSED, never faked")
    )
    lines.append("")
    lines.append(
        "  Strict mode: without Razorpay test credentials a run is refused,\n"
        "  not quietly substituted."
        if not fake_gateway_permitted() else
        "  WARNING: a gateway test double is permitted in this shell. That is for\n"
        "  the test suite only — a normal run should never see it."
    )
    return "\n".join(lines)


if __name__ == "__main__":
    print(status())
