"""Unit tests for compare_things inventory mode and list_identical.

Covers AC-INV-1 to AC-INV-4 from docs/doc/gemini/GEMINI-mcp-agent-gaps.md.
"""

from __future__ import annotations

import pytest
from pathlib import Path
from compare_things import compare_things


@pytest.fixture
def sample_folder(tmp_path):
    f_dir = tmp_path / "bin"
    f_dir.mkdir(parents=True, exist_ok=True)
    (f_dir / "fsdMail.dll").write_bytes(b"DATA_MAIL_1")
    (f_dir / "callMailXS.dll").write_bytes(b"DATA_MAIL_2")
    (f_dir / "other.dll").write_bytes(b"DATA_OTHER")
    (f_dir / "hidden.f").write_bytes(b"ENCRYPTED_F")
    return f_dir


def test_ac_inv_1_inventory_one_folder(sample_folder):
    """AC-INV-1: inventory=true, 1 folder bin + include_glob=*Mail* -> tra du ten DLL khop (khong omitted het)."""
    res = compare_things(
        kind="folder",
        folder_a=str(sample_folder),
        include_glob="*Mail*",
        inventory=True,
    )
    assert res["success"] is True
    assert res["mode"] == "inventory"
    assert res["kind"] == "folder"
    assert res["folder"] == str(sample_folder).replace("\\", "/")
    
    file_names = [f["relative"] for f in res["files"]]
    assert "fsdMail.dll" in file_names
    assert "callMailXS.dll" in file_names
    assert "other.dll" not in file_names
    # .f file must not be in files
    assert "hidden.f" not in file_names
    assert res["summary"]["file_count"] == 2
    assert res["summary"]["truncated"] is False


def test_ac_inv_2_inventory_missing_folder():
    """AC-INV-2: inventory=true thieu folder -> error_code=invalid_folder."""
    res = compare_things(
        kind="folder",
        folder_a="",
        folder_b="",
        inventory=True,
    )
    assert res["success"] is False
    assert res["error_code"] == "invalid_folder"


def test_ac_inv_3_self_compare_list_identical(sample_folder):
    """AC-INV-3: Self-compare A=B + list_identical=true -> co ten file trong summary.identical."""
    res = compare_things(
        kind="folder",
        folder_a=str(sample_folder),
        folder_b=str(sample_folder),
        list_identical=True,
    )
    assert res["success"] is True
    assert "identical" in res["summary"]
    identical_files = res["summary"]["identical"]
    assert "fsdMail.dll" in identical_files
    assert "other.dll" in identical_files
    assert res["summary"]["omitted_identical_count"] == 0


def test_ac_inv_4_no_regress_when_inventory_false(sample_folder):
    """AC-INV-4: Khong regress summary 2-folder khi inventory=false (van duoc omit identical de gon)."""
    res = compare_things(
        kind="folder",
        folder_a=str(sample_folder),
        folder_b=str(sample_folder),
        inventory=False,
        list_identical=False,
    )
    assert res["success"] is True
    assert res["summary"]["identical_meta_count"] == 3
    assert res["summary"]["omitted_identical_count"] == 3
    assert "identical" not in res["summary"]
