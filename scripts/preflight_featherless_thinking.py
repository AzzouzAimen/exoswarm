from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

ROOT = Path(__file__).resolve().parents[1]
API_SRC = ROOT / "apps" / "api" / "src"
if str(API_SRC) not in sys.path:
    sys.path.insert(0, str(API_SRC))

from exoswarm.config import Settings


def debug_chat_format_url(base_url: str, model: str) -> str:
    """Build Featherless's model-specific debug endpoint from the v1 API URL."""

    if "/" not in model:
        raise ValueError("model identity must include owner/model")
    owner, model_name = model.split("/", 1)
    api_origin = base_url.rstrip("/").removesuffix("/v1")
    return (
        f"{api_origin}/models/{quote(owner, safe='')}/"
        f"{quote(model_name, safe='')}/debug/chat-format"
    )


def _format_fingerprint(payload: dict[str, Any]) -> dict[str, Any]:
    formatted = payload.get("formatted_prompt")
    if not isinstance(formatted, str) or not formatted:
        raise RuntimeError("debug response omitted formatted_prompt")
    return {
        "formatted_prompt_sha256": hashlib.sha256(formatted.encode()).hexdigest(),
        "token_count": payload.get("token_count"),
        "template_info": payload.get("template_info"),
    }


def run_preflight(
    *, api_key: str, base_url: str, model: str, timeout_seconds: float = 30.0
) -> dict[str, Any]:
    endpoint = debug_chat_format_url(base_url, model)
    common = {
        "model": model,
        "messages": [
            {"role": "system", "content": "Return one concise JSON object."},
            {"role": "user", "content": "Confirm the response format."},
        ],
    }
    reports: dict[str, dict[str, Any]] = {}
    with httpx.Client(timeout=timeout_seconds) as client:
        for label, enabled in (("off", False), ("on", True)):
            response = client.post(
                endpoint,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    **common,
                    "chat_template_kwargs": {"thinking": enabled},
                },
            )
            response.raise_for_status()
            reports[label] = _format_fingerprint(response.json())
    confirmed = (
        reports["off"]["formatted_prompt_sha256"]
        != reports["on"]["formatted_prompt_sha256"]
    )
    return {
        "schema_version": "1",
        "model_identity": model,
        "debug_endpoint": endpoint,
        "thinking_toggle_effect_confirmed": confirmed,
        "modes": reports,
        "secret_persisted": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify Featherless thinking on/off formatting for the exact model."
    )
    parser.add_argument("--model")
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    args = parser.parse_args()
    # Match the application and live-canary configuration boundary: local demo
    # credentials may be supplied by the repository's ignored .env file.
    settings = Settings()
    key = os.environ.get("FEATHERLESS_API_KEY", "").strip()
    if not key and settings.featherless_api_key is not None:
        key = settings.featherless_api_key.get_secret_value()
    if not key:
        print(
            json.dumps(
                {
                    "schema_version": "1",
                    "status": "SKIPPED",
                    "reason": "FEATHERLESS_API_KEY is absent",
                },
                sort_keys=True,
            )
        )
        return 2
    report = run_preflight(
        api_key=key,
        base_url=settings.featherless_base_url,
        model=args.model or settings.model,
        timeout_seconds=args.timeout_seconds,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["thinking_toggle_effect_confirmed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
