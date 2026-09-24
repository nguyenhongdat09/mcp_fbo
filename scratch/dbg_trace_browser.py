import sys, time, json
sys.path.insert(0, r"E:\PythonProject\mcp_fbo")
from trace_profile import service as PS
from fastbusiness_mcp.mcp_app import get_config
from fastbusiness_mcp import mcp_app

cfg = get_config()
FP = r"\\172.168.5.14\CustomerPro\FBI\HAOHOA\FBISP2421\App_Data\Controllers\Report\Config\MRTran.ent"

# db_type='app' — giống test5
r = PS.profiler(file_path=FP, action="start", db_type="app", config=cfg)
tid = r.get("trace_id")
print("trace_id:", tid, "| db:", r.get("database"), "| filters:", r.get("filters"))

# query_database của MCP — login khác 'profile', hit HAOHOA_FBISP2421_A.dmkh
r2 = mcp_app.query_database(file_path=FP, query="SELECT TOP 3 ma_kh, ten_kh FROM dmkh", query_type=1)
print("query_database ok:", "ma_kh" in str(r2).lower() or "dmkh" in str(r2).lower())

time.sleep(4)
r = PS.profiler(file_path=FP, action="read", trace_id=tid, since_seq=-1, config=cfg)
rows = r.get("rows") or []
print(f"read: {len(rows)} rows")
for x in rows[:10]:
    print("  ", {k: str(v)[:70] for k, v in x.items()
                 if k in ("EventName", "TextData", "LoginName", "ApplicationName", "DatabaseName")})

PS.profiler(file_path=FP, action="stop", trace_id=tid, config=cfg)
print("DONE")
