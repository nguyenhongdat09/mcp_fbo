import json

def format_search_result(result: dict) -> str:
    return json.dumps(result, ensure_ascii=False, indent=2)
