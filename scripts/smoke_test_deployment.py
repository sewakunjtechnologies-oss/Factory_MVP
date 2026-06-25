#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request


def request(method: str, url: str, payload: dict | None = None, token: str | None = None) -> tuple[int, object]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="ignore")
        try:
            body = json.loads(raw)
        except Exception:
            body = raw
        return exc.code, body


def check(name: str, ok: bool, detail: str = "") -> bool:
    print(f"{'PASS' if ok else 'FAIL'} {name}{' - ' + detail if detail else ''}")
    return ok


def main() -> int:
    base = (os.environ.get("FACTORY_BASE_URL") or (sys.argv[1] if len(sys.argv) > 1 else "")).rstrip("/")
    email = os.environ.get("OWNER_EMAIL")
    password = os.environ.get("OWNER_PASSWORD")
    if not base:
        print("Set FACTORY_BASE_URL or pass base URL as first argument.", file=sys.stderr)
        return 2
    failures = 0

    status, body = request("GET", f"{base}/health")
    failures += not check("health", status == 200 and isinstance(body, dict), str(body))

    if not email or not password:
        print("Skipping authenticated checks. Set OWNER_EMAIL and OWNER_PASSWORD.")
        return failures

    status, body = request("POST", f"{base}/api/v1/auth/login", {"email": email, "password": password})
    token = body.get("access_token") if isinstance(body, dict) else None
    failures += not check("login", status == 200 and bool(token))
    if not token:
        return failures or 1

    checks = [
        ("owner dashboard", "GET", "/api/v1/dashboard/owner", None),
        ("purchase orders", "GET", "/api/v1/purchase-orders", None),
        ("fabric operations", "GET", "/api/v1/fabric-operations/mill-orders", None),
        ("alerts", "GET", "/api/v1/alerts", None),
        ("reminders", "GET", "/api/v1/reminders", None),
        ("pdf reports", "GET", "/api/v1/reports/pdf", None),
        ("ai text question", "POST", "/api/v1/voice/ask", {"message": "What needs my attention today?"}),
    ]
    for name, method, path, payload in checks:
        status, body = request(method, f"{base}{path}", payload, token)
        failures += not check(name, 200 <= status < 300, f"status={status}")

    return failures


if __name__ == "__main__":
    raise SystemExit(main())
