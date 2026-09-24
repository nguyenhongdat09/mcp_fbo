import sys
sys.path.insert(0, r"E:\PythonProject\mcp_fbo")
from trace_profile.connection import resolve_profiler_connection, run_sql
from fastbusiness_mcp.mcp_app import get_config

cfg = get_config()
FP = r"\\172.168.5.14\CustomerPro\FBI\HAOHOA\FBISP2421\App_Data\Controllers\Report\Config\MRTran.ent"
conn = resolve_profiler_connection(FP, "app", cfg)
parsed = conn["parsed"]
path = (r"E:\Program Install\Microsoft SQL Server\MSSQL10_50.SQL2008\MSSQL\Log"
        r"\fbo_mcp_20260922_145758_x9f71d6dz.trc")

# trace 53 (db_type='app', filter _A) — đếm event + xem có _A events không
res = run_sql(parsed, f"""
SELECT COUNT(*) FROM sys.fn_trace_gettable(N'{path}', default) t""")
print("trace53 total rows:", (res.get("result_sets") or [{}])[0].get("rows"))

res = run_sql(parsed, f"""
SELECT TOP 20 t.EventSequence, te.name, CAST(t.TextData AS nvarchar(150)) AS td,
       t.DatabaseName, t.ApplicationName
FROM sys.fn_trace_gettable(N'{path}', default) t
LEFT JOIN sys.trace_events te ON te.trace_event_id = t.EventClass
ORDER BY t.EventSequence""")
for r in (res.get("result_sets") or [{}])[0].get("rows", []):
    print("  ", r[0], "|", r[1], "|", r[3], "|", str(r[2])[:80])
