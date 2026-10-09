"""HTTP client gọi TypeSafe Jev — POST /v1/systemone (urllib stdlib)."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

# Docs TypeSafe: 429 (rate limit) / 529 (overloaded) → retry backoff.
_RETRY_STATUS = {429, 529}
_MAX_RETRIES = 2
_BACKOFF_SECONDS = (0.5, 1.0)
_RETRY_AFTER_CAP = 3.0

_sleep = time.sleep  # test hook


def _retry_delay(attempt: int, headers) -> float:
    delay = _BACKOFF_SECONDS[min(attempt, len(_BACKOFF_SECONDS) - 1)]
    try:
        ra = float((headers or {}).get("retry-after") or 0)
        if ra > 0:
            delay = min(ra, _RETRY_AFTER_CAP)
    except (TypeError, ValueError):
        pass
    return delay


def _http_error(e: urllib.error.HTTPError) -> dict:
    if e.code == 401:
        return {"ok": False, "error": "unauthorized", "detail": "HTTP 401"}
    if e.code == 422:
        body = ""
        try:
            body = e.read().decode("utf-8", "replace")[:300]
        except Exception:
            pass
        return {"ok": False, "error": "invalid_request",
                "detail": f"HTTP 422 {body}".strip()}
    if e.code == 429:
        return {"ok": False, "error": "rate_limited", "detail": "HTTP 429"}
    if e.code == 529:
        return {"ok": False, "error": "overloaded", "detail": "HTTP 529"}
    return {"ok": False, "error": "api_loi", "detail": f"HTTP {e.code}"}


def post_systemone(cfg: dict, state, questions: dict) -> dict:
    """Gọi Jev. Trả {"ok": True, "answers": {...}, "usage": {...}, "model"}
    hoặc {"ok": False, "error": <code>, "detail": <str>}.

    429/529 và timeout mạng được retry tối đa ``_MAX_RETRIES`` lần.
    """
    url = f"{cfg['base_url'].rstrip('/')}/v1/systemone"
    payload = {
        "model": cfg.get("model") or "jev-latest",
        "state": state,
        "questions": questions,
    }
    data = json.dumps(payload, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {cfg['api_key']}",
        "Content-Type": "application/json",
    }
    timeout = cfg.get("timeout_seconds", 15)
    last: dict = {"ok": False, "error": "jev_error", "detail": "no attempt"}
    for attempt in range(_MAX_RETRIES + 1):
        req = urllib.request.Request(url, data=data, headers=headers,
                                     method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
                return {
                    "ok": True,
                    "answers": body.get("answers") or {},
                    "usage": body.get("usage") or {},
                    "model": body.get("model"),
                }
        except urllib.error.HTTPError as e:
            last = _http_error(e)
            if e.code not in _RETRY_STATUS or attempt == _MAX_RETRIES:
                return last
            _sleep(_retry_delay(attempt, getattr(e, "headers", None)))
        except urllib.error.URLError as e:
            last = {"ok": False, "error": "khong_ket_noi_api",
                    "detail": f"{e.reason}"}
            if "timed out" not in str(e.reason) or attempt == _MAX_RETRIES:
                return last
            _sleep(_retry_delay(attempt, None))
        except TimeoutError as e:
            last = {"ok": False, "error": "timeout", "detail": str(e)[:200]}
            if attempt == _MAX_RETRIES:
                return last
            _sleep(_retry_delay(attempt, None))
        except Exception as e:
            return {"ok": False, "error": "jev_error", "detail": str(e)[:200]}
    return last
