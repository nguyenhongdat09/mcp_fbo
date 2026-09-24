import sys, json
sys.path.insert(0, r"E:\PythonProject\mcp_fbo")
from trace_profile.connection import resolve_profiler_connection, run_sql
from fastbusiness_mcp.mcp_app import get_config

cfg = get_config()
FP = r"\\172.168.5.14\CustomerPro\FBI\HAOHOA\FBISP2421\App_Data\Controllers\Report\Config\MRTran.ent"
conn = resolve_profiler_connection(FP, "app", cfg)
parsed = conn["parsed"]

# liệt kê tất cả bảng trong sys DB
res = run_sql(parsed, "SELECT name FROM HAOHOA_FBISP2421_S.sys.tables ORDER BY name")
names = [r[0] for r in (res.get("result_sets") or [{}])[0].get("rows", [])]
print(f"{len(names)} tables in _S:", names[:60])
