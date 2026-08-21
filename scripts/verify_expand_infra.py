"""Quick check: expand infra bare name."""
from unittest.mock import MagicMock

from queryDatabase.bridges.summary_bridge import summary_object
from queryDatabase.object_catalog.models import DbObjectMeta
from tests.sql_object_summary.test_analyze_proc import FIXTURE_INTEREST_PROC

INFRA_NAME = "FastBusiness$Balance$BContract"
INFRA_DEF = f"CREATE PROC dbo.{INFRA_NAME} AS SELECT * FROM cdku;"

mf = MagicMock()
mf.fetch_one.return_value = DbObjectMeta(
    schema_name="dbo",
    name="rs_rptInterestDetailedByLoanContract",
    object_id=1,
    type_desc="P",
    sys_type="P",
    definition=FIXTURE_INTEREST_PROC,
    modify_date=None,
    parameters=[],
)
mf.fetch_many.return_value = {
    f"dbo.{INFRA_NAME}": DbObjectMeta(
        schema_name="dbo",
        name=INFRA_NAME,
        object_id=2,
        type_desc="P",
        sys_type="P",
        definition=INFRA_DEF,
        modify_date=None,
        parameters=[],
    )
}

res = summary_object(
    file_path="x.xml",
    object_name="dbo.rs_rptInterestDetailedByLoanContract",
    mode="summary",
    max_depth=1,
    expand=[INFRA_NAME],
    use_cache=False,
    fetcher_override=mf,
)

nodes = (res.get("call_graph") or {}).get("nodes", {})
print("fetch_many_calls:", mf.fetch_many.call_count)
print("infra_in_nodes:", f"dbo.{INFRA_NAME}" in nodes)
print("ok:", mf.fetch_many.call_count >= 1 and f"dbo.{INFRA_NAME}" in nodes)
