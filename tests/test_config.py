"""Configuration and credential-handling tests."""

from __future__ import annotations

import os

import pytest

from backend.config.env import load_env
from backend.config.secrets import mask as _mask


def write_env(tmp_path, body: str):
    p = tmp_path / ".env"
    p.write_text(body)
    return p


def test_parses_comments_quotes_and_export(tmp_path, monkeypatch):
    monkeypatch.delenv("WINBACK_API_KEY", raising=False)
    monkeypatch.delenv("RAZORPAY_KEY_SECRET", raising=False)
    monkeypatch.delenv("WINBACK_MODEL", raising=False)

    p = write_env(
        tmp_path,
        '# a comment\n'
        '\n'
        'export WINBACK_API_KEY="gsk_live_value"\n'
        "RAZORPAY_KEY_SECRET='single quoted'\n"
        "WINBACK_MODEL=bare-value\n"
        "MALFORMED LINE WITHOUT EQUALS\n",
    )
    found = load_env(p)

    assert found["WINBACK_API_KEY"] == "gsk_live_value"
    assert found["RAZORPAY_KEY_SECRET"] == "single quoted"
    assert found["WINBACK_MODEL"] == "bare-value"
    assert os.environ["WINBACK_API_KEY"] == "gsk_live_value"


def test_exported_environment_beats_the_file(tmp_path, monkeypatch):
    """CI and `export VAR=... python ...` must override the file, not lose to it."""
    monkeypatch.setenv("WINBACK_MODEL", "from-environment")
    p = write_env(tmp_path, "WINBACK_MODEL=from-file\n")
    load_env(p)
    assert os.environ["WINBACK_MODEL"] == "from-environment"


def test_override_flag_reverses_precedence(tmp_path, monkeypatch):
    monkeypatch.setenv("WINBACK_MODEL", "from-environment")
    p = write_env(tmp_path, "WINBACK_MODEL=from-file\n")
    load_env(p, override=True)
    assert os.environ["WINBACK_MODEL"] == "from-file"


def test_missing_file_is_not_an_error(tmp_path):
    """Running with no .env at all is a supported mode, not a failure."""
    assert load_env(tmp_path / "does_not_exist") == {}


def test_secrets_are_masked_never_printed_whole():
    masked = _mask("gsk_abcdefgh12345678wxyz")
    assert "abcdefgh" not in masked
    assert masked.startswith("gsk_") and masked.endswith("wxyz")
    assert _mask("short") == "*****"


def test_a_live_razorpay_key_is_refused(monkeypatch):
    """The system creates orders. A live key would create real ones, for real
    customers, from a batch of synthetic test data."""
    from backend.executor.razorpay_gateway import RazorpayGateway

    monkeypatch.setenv("RAZORPAY_KEY_ID", "rzp_live_DANGER")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "x")
    monkeypatch.delenv("WINBACK_ALLOW_LIVE_KEYS", raising=False)

    with pytest.raises(RuntimeError, match="LIVE key"):
        RazorpayGateway()


def test_a_test_key_is_accepted(monkeypatch):
    from backend.executor.razorpay_gateway import RazorpayGateway

    monkeypatch.setenv("RAZORPAY_KEY_ID", "rzp_test_SAFE")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "x")
    assert RazorpayGateway().key_id == "rzp_test_SAFE"


def test_env_example_holds_no_real_values():
    """The committed example must never carry a credential."""
    from pathlib import Path

    text = (Path(__file__).resolve().parent.parent / ".env.example").read_text()
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        if key.strip() in {"WINBACK_API_KEY", "RAZORPAY_KEY_ID", "RAZORPAY_KEY_SECRET"}:
            assert value.strip() == "", f"{key} has a value committed in .env.example"


def test_dotenv_is_gitignored():
    from pathlib import Path

    ignored = (Path(__file__).resolve().parent.parent / ".gitignore").read_text().split()
    assert ".env" in ignored
