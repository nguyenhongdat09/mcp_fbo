"""Smoke: default MCP_BASE paths + config_path.yaml override (no mcp_app import)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.pop("FBOGRAPH_KUZU_BASE", None)
os.environ.pop("CLONE_THINGS_SQL_TEMP_FOLDER", None)
os.environ.pop("FASTBUSINESS_CONFIG_PATH_FILE", None)

from clone_things.file_manager import resolve_output_file
from fastbusiness_mcp.config_paths import (
    get_effective_kuzu_db_base,
    get_effective_sql_temp_folder,
    get_mcp_base_dir,
    load_machine_paths,
    merge_config_with_machine_paths,
)

PROJECT = r"\\172.168.5.14\CustomerPro\FBO\VLOTUS\SP228"


def main() -> None:
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8")) or {}
    cfg_a = merge_config_with_machine_paths(cfg, {})
    print("MCP_BASE", get_mcp_base_dir())
    print("A sql", get_effective_sql_temp_folder(cfg_a))
    print("A kuzu", get_effective_kuzu_db_base(cfg_a))
    out_a, err_a = resolve_output_file("", "dbo.zc_sctnt", cfg_a, project_source=PROJECT, is_antigravity=False)
    print("A file", out_a, err_a)

    test_sql = ROOT / "scripts" / "_clone_things_live" / "_sql_temp_yaml_test"
    test_kuzu = ROOT / "scripts" / "_clone_things_live" / "_kuzu_yaml_test"
    test_sql.mkdir(parents=True, exist_ok=True)
    test_kuzu.mkdir(parents=True, exist_ok=True)
    yaml_tmp = ROOT / "scripts" / "_clone_things_live" / "_tmp_config_path.yaml"
    yaml_tmp.write_text(
        "fbograph:\n"
        f"  kuzu_db_base: '{test_kuzu.resolve().as_posix()}'\n"
        "clone_things:\n"
        f"  sql_temp_folder: '{test_sql.resolve().as_posix()}'\n",
        encoding="utf-8",
    )
    machine = load_machine_paths(yaml_tmp)
    cfg_b = merge_config_with_machine_paths(cfg, machine)
    print("B machine", machine)
    print("B sql", get_effective_sql_temp_folder(cfg_b))
    print("B kuzu", get_effective_kuzu_db_base(cfg_b))
    out_b, err_b = resolve_output_file("", "dbo.zc_sctnt", cfg_b, project_source=PROJECT, is_antigravity=False)
    print("B file", out_b, err_b)
    ok = bool(out_b) and str(test_sql.resolve()).lower() in out_b.lower()
    print("B PASS" if ok and not err_b else "B FAIL")


if __name__ == "__main__":
    main()
