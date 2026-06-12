"""Check RunYourAI auth header shape and print the provider's raw error body.

Usage:
    python3 scripts/check_runyourai_error.py
    python3 scripts/check_runyourai_error.py --model openai/gpt-4.1-2025-04-14
    python3 scripts/check_runyourai_error.py --client sdk
    python3 scripts/check_runyourai_error.py --show-sensitive
    python3 scripts/check_runyourai_error.py --no-request
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import httpx


DEFAULT_BASE_URL = "https://api.runyour.ai/v1"
DEFAULT_MODEL = "openai/gpt-4.1-2025-04-14"


def _parse_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values

    for line in path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value

    return values


def _load_api_key(env_file: Path) -> str:
    return os.getenv("RUNYOUR_API_KEY") or _parse_dotenv(env_file).get("RUNYOUR_API_KEY", "")


def _mask_header(value: str) -> str:
    if len(value) <= 12:
        return "***"
    return f"{value[:12]}***"


def _visible_header_value(name: str, value: str, *, show_sensitive: bool) -> str:
    if show_sensitive:
        return value
    if name.lower() == "authorization":
        return _mask_header(value)
    return value


def _print_headers(title: str, headers: httpx.Headers, *, show_sensitive: bool) -> None:
    print(title)
    for name, value in headers.items():
        print(f"{name}: {_visible_header_value(name, value, show_sensitive=show_sensitive)}")


def _print_response(response: httpx.Response, *, show_sensitive: bool) -> None:
    print("=== RESPONSE STATUS ===")
    print(response.status_code)
    print()
    _print_headers("=== RESPONSE HEADERS ===", response.headers, show_sensitive=show_sensitive)
    print()
    print("=== RESPONSE BODY ===")
    try:
        print(json.dumps(response.json(), ensure_ascii=False, indent=2))
    except ValueError:
        print(response.text)


def _request_with_httpx(
    *,
    url: str,
    payload: dict[str, object],
    auth_header: str,
    timeout: float,
    show_sensitive: bool,
) -> int:
    request = httpx.Request(
        "POST",
        url,
        headers={
            "Authorization": auth_header,
            "Content-Type": "application/json",
        },
        json=payload,
    )

    _print_headers("=== REQUEST HEADERS ===", request.headers, show_sensitive=show_sensitive)
    print()

    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.send(request)
    except httpx.HTTPError as exc:
        print("request failed:", f"{type(exc).__name__}: {exc}")
        return 2

    _print_response(response, show_sensitive=show_sensitive)
    return 0


def _print_httpx_request_headers(
    *,
    url: str,
    payload: dict[str, object],
    auth_header: str,
    show_sensitive: bool,
) -> None:
    request = httpx.Request(
        "POST",
        url,
        headers={
            "Authorization": auth_header,
            "Content-Type": "application/json",
        },
        json=payload,
    )
    _print_headers("=== REQUEST HEADERS ===", request.headers, show_sensitive=show_sensitive)


def _request_with_openai_sdk(
    *,
    base_url: str,
    model: str,
    message: str,
    api_key: str,
    timeout: float,
    show_sensitive: bool,
) -> int:
    try:
        from openai import APIStatusError, OpenAI, OpenAIError
    except ImportError:
        print("openai package is not installed. Install requirements or use --client httpx.")
        return 3

    def print_request(request: httpx.Request) -> None:
        _print_headers("=== REQUEST HEADERS ===", request.headers, show_sensitive=show_sensitive)
        print()

    http_client = httpx.Client(timeout=timeout, event_hooks={"request": [print_request]})
    client = OpenAI(api_key=api_key, base_url=base_url, http_client=http_client)

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": message}],
            max_tokens=1,
        )
    except APIStatusError as exc:
        _print_response(exc.response, show_sensitive=show_sensitive)
        return 0
    except OpenAIError as exc:
        print("request failed:", f"{type(exc).__name__}: {exc}")
        return 2
    finally:
        http_client.close()

    print("=== RESPONSE BODY ===")
    print(response.model_dump_json(indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Print whether Bearer auth is attached and show RunYourAI's raw response."
    )
    parser.add_argument("--env-file", default=".env", help="dotenv file path. Default: .env")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help=f"Default: {DEFAULT_BASE_URL}")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Default: {DEFAULT_MODEL}")
    parser.add_argument("--message", default="ping", help="Test user message. Default: ping")
    parser.add_argument("--timeout", type=float, default=20.0, help="Request timeout seconds. Default: 20")
    parser.add_argument(
        "--client",
        choices=("httpx", "sdk"),
        default="httpx",
        help="Use raw httpx or the official OpenAI SDK style. Default: httpx",
    )
    parser.add_argument(
        "--show-sensitive",
        action="store_true",
        help="Print full sensitive headers, including the full Authorization API key.",
    )
    parser.add_argument(
        "--no-request",
        action="store_true",
        help="Only print local header/key checks without calling RunYourAI.",
    )
    args = parser.parse_args()

    api_key = _load_api_key(Path(args.env_file))
    if not api_key:
        print("RUNYOUR_API_KEY is missing. Set it in the environment or .env.")
        return 1

    auth_header = f"Bearer {api_key}"
    print("Authorization header starts with Bearer:", auth_header.startswith("Bearer "))
    print(
        "Authorization header:",
        _visible_header_value("authorization", auth_header, show_sensitive=args.show_sensitive),
    )
    print("API key length:", len(api_key))
    print("API key has surrounding spaces:", api_key != api_key.strip())
    print("API key contains quote chars:", any(char in api_key for char in ("'", '"')))
    print()

    url = args.base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": args.model,
        "messages": [{"role": "user", "content": args.message}],
        "max_tokens": 1,
    }

    if args.no_request:
        if args.client == "sdk":
            print("SDK request headers are created inside the OpenAI client when a request is sent.")
            print("Run without --no-request to see the SDK-generated request headers.")
            return 0
        _print_httpx_request_headers(
            url=url,
            payload=payload,
            auth_header=auth_header,
            show_sensitive=args.show_sensitive,
        )
        return 0

    if args.client == "sdk":
        return _request_with_openai_sdk(
            base_url=args.base_url,
            model=args.model,
            message=args.message,
            api_key=api_key,
            timeout=args.timeout,
            show_sensitive=args.show_sensitive,
        )

    return _request_with_httpx(
        url=url,
        payload=payload,
        auth_header=auth_header,
        timeout=args.timeout,
        show_sensitive=args.show_sensitive,
    )


if __name__ == "__main__":
    raise SystemExit(main())
