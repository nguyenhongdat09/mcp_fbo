"""Unit tests for config_path.yaml machine paths loading and merging (TC-CP-*)."""

import os
from pathlib import Path
import pytest

from fastbusiness_mcp.config_paths import (
    load_machine_paths,
    merge_config_with_machine_paths,
    resolve_config_path_local,
    get_effective_kuzu_db_base,
    get_effective_sql_temp_folder,
)


def test_tc_cp_01_parse_yaml_correctly(tmp_path):
    """TC-CP-01: Parse YAML -> dict đúng cấu trúc."""
    yaml_content = """# Machine paths
fbograph:
  kuzu_db_base: "D:/MyKuzuDB"
clone_things:
  sql_temp_folder: "D:/MySqlTemp"
"""
    yaml_file = tmp_path / "config_path.yaml"
    yaml_file.write_text(yaml_content, encoding="utf-8")

    machine = load_machine_paths(yaml_file)
    assert machine == {
        "fbograph": {"kuzu_db_base": "D:/MyKuzuDB"},
        "clone_things": {"sql_temp_folder": "D:/MySqlTemp"},
    }


def test_tc_cp_02_merge_yaml_overrides_legacy_path():
    """TC-CP-02: Merge: YAML overrides legacy path; không đè open_file hay options khác."""
    yaml_cfg = {
        "fbograph": {
            "kuzu_db_base": "C:/OldKuzu",
            "user_multi_db_yn": 1,
            "access_log_retention_days": 30,
        },
        "clone_things": {
            "sql_temp_folder": "C:/OldSqlTemp",
            "open_file": True,
            "max_objects": 50,
            "open_editor_cmd": "auto",
        },
    }
    machine = {
        "fbograph": {"kuzu_db_base": "D:/NewKuzu"},
        "clone_things": {"sql_temp_folder": "D:/NewSqlTemp"},
    }

    merged = merge_config_with_machine_paths(yaml_cfg, machine)

    # Path keys are overridden by config_path.yaml
    assert merged["fbograph"]["kuzu_db_base"] == "D:/NewKuzu"
    assert merged["clone_things"]["sql_temp_folder"] == "D:/NewSqlTemp"

    # Non-path keys remain intact
    assert merged["fbograph"]["user_multi_db_yn"] == 1
    assert merged["fbograph"]["access_log_retention_days"] == 30
    assert merged["clone_things"]["open_file"] is True
    assert merged["clone_things"]["max_objects"] == 50
    assert merged["clone_things"]["open_editor_cmd"] == "auto"


def test_tc_cp_03_missing_yaml_fallback_defaults(tmp_path):
    """TC-CP-03: Missing YAML -> fallback giá trị legacy YAML hoặc MCP_BASE default."""
    yaml_cfg_legacy = {
        "fbograph": {"kuzu_db_base": "C:/LegacyKuzu"},
        "clone_things": {"sql_temp_folder": "C:/LegacySql"},
    }
    # No machine dict provided
    merged = merge_config_with_machine_paths(yaml_cfg_legacy, {})
    assert merged["fbograph"]["kuzu_db_base"] == "C:/LegacyKuzu"
    assert merged["clone_things"]["sql_temp_folder"] == "C:/LegacySql"

    # Empty yaml cfg -> effective functions return defaults
    empty_cfg = {"fbograph": {}, "clone_things": {}}
    kuzu_eff = get_effective_kuzu_db_base(empty_cfg)
    sql_eff = get_effective_sql_temp_folder(empty_cfg)
    assert kuzu_eff.endswith("KuzuDB")
    assert sql_eff.endswith("Scripts")


def test_tc_cp_04_empty_keys_treat_as_unset(tmp_path):
    """TC-CP-04: Empty string keys -> treat as unset, do not override legacy config."""
    yaml_content = """
fbograph:
  kuzu_db_base: "   "
clone_things:
  sql_temp_folder: ""
"""
    yaml_file = tmp_path / "config_path.yaml"
    yaml_file.write_text(yaml_content, encoding="utf-8")

    machine = load_machine_paths(yaml_file)
    assert machine == {}

    yaml_cfg = {
        "fbograph": {"kuzu_db_base": "C:/ExistingKuzu"},
        "clone_things": {"sql_temp_folder": "C:/ExistingSql"},
    }
    merged = merge_config_with_machine_paths(yaml_cfg, machine)
    assert merged["fbograph"]["kuzu_db_base"] == "C:/ExistingKuzu"
    assert merged["clone_things"]["sql_temp_folder"] == "C:/ExistingSql"


def test_tc_cp_05_env_kuzu_wins(monkeypatch):
    """TC-CP-05: Env FBOGRAPH_KUZU_BASE wins over config_path.yaml and config.yaml."""
    monkeypatch.setenv("FBOGRAPH_KUZU_BASE", "Z:/EnvKuzu")
    cfg = {
        "fbograph": {"kuzu_db_base": "D:/MachineKuzu"},
    }
    assert get_effective_kuzu_db_base(cfg) == "Z:/EnvKuzu"


def test_tc_cp_06_bad_yaml_no_throw(tmp_path):
    """TC-CP-06: Bad YAML -> empty machine dict + no throw."""
    bad_yaml = tmp_path / "broken_config_path.yaml"
    bad_yaml.write_text("fbograph: [unclosed list", encoding="utf-8")

    result = load_machine_paths(bad_yaml)
    assert result == {}

    # Non-dict YAML (e.g., list or scalar)
    scalar_yaml = tmp_path / "scalar_config_path.yaml"
    scalar_yaml.write_text("just a string", encoding="utf-8")
    assert load_machine_paths(scalar_yaml) == {}


def test_tc_cp_07_resolve_config_path_local_next_to_config_yaml(tmp_path, monkeypatch):
    """TC-CP-07: resolve_config_path_local finds config_path.yaml next to config.yaml."""
    fake_yaml = tmp_path / "config.yaml"
    fake_yaml.write_text("server: {name: test}", encoding="utf-8")

    fake_local = tmp_path / "config_path.yaml"
    fake_local.write_text("fbograph: {kuzu_db_base: ''}", encoding="utf-8")

    monkeypatch.setenv("FASTBUSINESS_CONFIG_PATH", str(fake_yaml))
    monkeypatch.delenv("FASTBUSINESS_CONFIG_PATH_FILE", raising=False)

    resolved = resolve_config_path_local("config_path.yaml")
    assert resolved is not None
    assert resolved.resolve() == fake_local.resolve()


def test_tc_cp_08_sql_temp_resolve_uses_merged_config(tmp_path):
    """TC-CP-08: resolve_output_file uses merged config."""
    from clone_things.file_manager import resolve_output_file

    custom_dir = tmp_path / "custom_temp"
    custom_dir.mkdir()

    cfg = {
        "clone_things": {
            "sql_temp_folder": str(custom_dir),
            "is_antigravity": False,
        }
    }

    out_file, err = resolve_output_file(
        path_to_pasted="",
        seed_object="test_proc",
        config=cfg,
        is_antigravity=False,
    )
    assert err is None
    assert str(custom_dir) in out_file
    assert Path(out_file).exists()
