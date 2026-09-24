import sys
sys.path.insert(0, r"E:\PythonProject\mcp_fbo")
from trace_profile.connection import resolve_profiler_connection, run_sql
from fastbusiness_mcp.mcp_app import get_config

cfg = get_config()
FP = r"\\172.168.5.14\CustomerPro\FBI\HAOHOA\FBISP2421\App_Data\Controllers\Report\Config\MRTran.ent"
conn = resolve_profiler_connection(FP, "app", cfg)
parsed = conn["parsed"]
path = (r"E:\Program Install\Microsoft SQL Server\MSSQL10_50.SQL2008\MSSQL\Log"
        r"\fbo_mcp_20260922_151029_xa38771az.trc")

res = run_sql(parsed, f"""
SELECT t.EventSequence, te.name AS EventName,
       CAST(t.TextData AS nvarchar(300)) AS TextData, t.ApplicationName, t.LoginName
FROM sys.fn_trace_gettable(N'{path}', default) t
LEFT JOIN sys.trace_events te ON te.trace_event_id = t.EventClass
WHERE t.DatabaseName = N'HAOHOA_FBISP2421_A'
ORDER BY t.EventSequence""")
rows = (res.get("result_sets") or [{}])[0]
for r in rows.get("rows", []):
    print("  ", r[0], "|", r[1], "|", r[3], "|", r[4], "|", str(r[2])[:110].replace("\n", " "))
