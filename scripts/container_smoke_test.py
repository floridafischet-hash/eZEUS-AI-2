from __future__ import annotations

import argparse
import json
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4


def request_json(
    url: str,
    *,
    method: str = "GET",
    payload: dict[str, object] | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, object]:
    body = json.dumps(payload).encode() if payload is not None else None
    request = Request(
        url,
        data=body,
        method=method,
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    with urlopen(request, timeout=10) as response:  # nosec B310
        return json.load(response)


def wait_for_ready(base_url: str, deadline: float) -> None:
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            payload = request_json(f"{base_url}/ready")
            if payload.get("status") == "ready":
                return
        except (HTTPError, URLError, TimeoutError) as exc:
            last_error = exc
        time.sleep(1)
    raise RuntimeError(f"API did not become ready: {last_error}")


def wait_for_job(base_url: str, job_id: str, deadline: float) -> dict[str, object]:
    while time.monotonic() < deadline:
        payload = request_json(f"{base_url}/api/logs?limit=100")
        entries = payload.get("entries")
        if isinstance(entries, list):
            entry = next(
                (
                    item
                    for item in entries
                    if isinstance(item, dict) and item.get("job_id") == job_id
                ),
                None,
            )
            if entry is not None:
                status = entry.get("status")
                if status in {"COMPLETED", "COMPLETED_WITH_WARNINGS"}:
                    return entry
                if status == "FAILED":
                    raise RuntimeError(f"Container smoke job failed: {entry.get('error_message')}")
        time.sleep(1)
    raise RuntimeError(f"Job {job_id} did not finish before timeout")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--mock-url", default="http://127.0.0.1:18083")
    parser.add_argument("--timeout", type=float, default=120)
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")
    deadline = time.monotonic() + args.timeout

    wait_for_ready(base_url, deadline)
    download_request = Request(
        f"{args.mock_url.rstrip('/')}/api/documents/128/download/",
        headers={"Authorization": "Token example-paperless-api-token"},
    )
    with urlopen(  # nosec B310
        download_request,
        timeout=10,
    ) as download_response:
        if download_response.read(5) != b"%PDF-":
            raise RuntimeError("Paperless mock download fixture is unavailable")
    accepted = request_json(
        f"{base_url}/webhooks/paperless",
        method="POST",
        payload={"document_id": 128, "event_id": f"smoke-{uuid4()}"},
        headers={"X-EZEUS-Webhook-Secret": "example-webhook-secret"},
    )
    job_id = str(accepted["job_id"])
    entry = wait_for_job(base_url, job_id, deadline)
    if entry.get("status") != "COMPLETED":
        raise RuntimeError(f"Smoke job completed with warnings: {entry}")

    state = request_json(f"{args.mock_url.rstrip('/')}/debug/state")
    document = state.get("document")
    if not isinstance(document, dict) or document.get("title") != "RE-2026-128":
        raise RuntimeError(f"Paperless mock title was not updated: {document}")
    fields = document.get("custom_fields")
    if not isinstance(fields, list):
        raise RuntimeError(f"Paperless mock returned invalid custom fields: {fields}")
    values = {
        str(item.get("field")): item.get("value")
        for item in fields
        if isinstance(item, dict) and item.get("field") is not None
    }
    if values.get("14") != "RE-2026-128" or str(values.get("15")) != "123.45":
        raise RuntimeError(f"Paperless mock fields were not updated: {values}")
    print(f"Container smoke test passed for job {job_id}")


if __name__ == "__main__":
    main()
