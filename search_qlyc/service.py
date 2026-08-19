from typing import Optional
from .client import post_search_api

def search_qlyc(
    query: str = "",
    fcode1: Optional[str] = None,
    ma_da: Optional[str] = None,
    bp_lt: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    max_total: int = 100,
    config: Optional[dict] = None,
) -> dict:
    query_str = (query or "").strip()
    fcode1_str = (fcode1 or "").strip()
    ma_da_str = (ma_da or "").strip()
    bp_lt_str = (bp_lt or "").strip()

    if not query_str and not fcode1_str and not ma_da_str:
        return {
            "ok": False,
            "error": "query_thieu",
            "detail": "Vui lòng cung cấp ít nhất một tiêu chí tìm kiếm (query, fcode1 hoặc ma_da)."
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
        "query": query_str,
        "page": max(1, page),
        "page_size": max(1, min(50, page_size)),
        "max_total": max(1, min(100, max_total))
    }
    if fcode1_str:
        payload["fcode1"] = fcode1_str
    if ma_da_str:
        payload["ma_da"] = ma_da_str
    if bp_lt_str:
        payload["bp_lt"] = bp_lt_str
        
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
