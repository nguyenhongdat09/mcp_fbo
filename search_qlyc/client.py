import json
import urllib.request
import urllib.error

def post_search_api(base_url: str, api_key: str, timeout: int, payload: dict) -> dict:
    url = f"{base_url.rstrip('/')}/api/search"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.status == 200:
                body = response.read().decode('utf-8')
                return json.loads(body)
            else:
                return {
                    "ok": False,
                    "error": "api_loi",
                    "detail": f"HTTP {response.status}"
                }
    except urllib.error.HTTPError as e:
        error_code = "api_loi"
        if e.code == 401:
            error_code = "unauthorized"
        return {
            "ok": False,
            "error": error_code,
            "detail": f"HTTP {e.code}"
        }
    except urllib.error.URLError as e:
        return {
            "ok": False,
            "error": "khong_ket_noi_api",
            "detail": f"{e.reason} | url={url}",
        }
    except Exception as e:
        return {
            "ok": False,
            "error": "khong_ket_noi_api",
            "detail": f"{e} | url={url}",
        }
