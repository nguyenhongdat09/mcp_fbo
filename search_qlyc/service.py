from typing import Optional
from .client import post_search_api

def search_qlyc(
    query: str,
    ma_da: Optional[str] = None,
    bp_lt: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    max_total: int = 100,
    config: Optional[dict] = None,
) -> dict:
    if not query or not query.strip():
        return {
            "ok": False,
            "error": "query_thieu",
            "detail": "query is missing or empty"
        }
        
    if not config:
        return {
            "ok": False,
            "error": "config_thieu",
            "detail": "config dict is missing"
        }
        
    base_url = config.get("base_url")
    api_key = config.get("api_key")
    
    if not base_url or not str(base_url).strip() or not api_key or not str(api_key).strip():
        return {
            "ok": False,
            "error": "config_thieu",
            "detail": "base_url or api_key is missing in config"
        }
        
    timeout_seconds = config.get("timeout_seconds", 30)
    
    payload = {
        "query": query,
        "page": max(1, page),
        "page_size": max(1, min(50, page_size)),
        "max_total": max(1, min(100, max_total))
    }
    if ma_da and ma_da.strip():
        payload["ma_da"] = ma_da.strip()
    if bp_lt and bp_lt.strip():
        payload["bp_lt"] = bp_lt.strip()
        
    result = post_search_api(
        base_url=str(base_url).strip(),
        api_key=str(api_key).strip(),
        timeout=int(timeout_seconds),
        payload=payload
    )
    
    if result.get("ok") is False:
        return result
        
    # Result success
    result["ok"] = True
    return result
