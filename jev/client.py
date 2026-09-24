"""HTTP client gọi TypeSafe Jev — POST /v1/systemone (urllib stdlib)."""
from __future__ import annotations

import json
import urllib.error
import urllib.request


def post_systemone(cfg: dict, state, questions: dict) -> dict:
    """Gọi Jev. Trả {"ok": True, "answers": {...}, "usage": {...}}
    hoặc {"ok": False, "error": <code>, "detail": <str>}."""
    url = f"{cfg['base_url'].rstrip('/')}/v1/systemone"
    payload = {
        "model": cfg.get("model") or "jev-latest",
        "state": state,
        "questions": questions,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {cfg['api_key']}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    timeout = cfg.get("timeout_seconds", 15)
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
        code = "unauthorized" if e.code == 401 else "api_loi"
        return {"ok": False, "error": code, "detail": f"HTTP {e.code}"}
    except urllib.error.URLError as e:
        return {"ok": False, "error": "khong_ket_noi_api",
                "detail": f"{e.reason}"}
    except Exception as e:
        return {"ok": False, "error": "jev_error", "detail": str(e)[:200]}
