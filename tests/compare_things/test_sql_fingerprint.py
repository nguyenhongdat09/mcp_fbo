"""Unit tests for SQL fingerprinting and signals."""

import pytest
from compare_things.sql_fingerprint import (
    compute_sql_fingerprint,
    extract_hunk_signals,
    extract_sql_signals,
    normalize_sql_definition,
)


def test_sql_fingerprint_identical():
    def1 = "CREATE PROCEDURE dbo.ProcA\nAS\nBEGIN\n    SELECT 1\nEND"
    def2 = "CREATE PROCEDURE dbo.ProcA\r\nAS\r\nBEGIN\r\n    SELECT 1\r\nEND"

    c1, _ = normalize_sql_definition(def1, ignore_line_endings=True)
    c2, _ = normalize_sql_definition(def2, ignore_line_endings=True)
    fp1 = compute_sql_fingerprint(c1)
    fp2 = compute_sql_fingerprint(c2)
    assert fp1 == fp2


def test_sql_signals_extraction():
    src = "SELECT * FROM vdmduyetuq WHERE status = '1'"
    tgt = "SELECT * FROM dmduyet WHERE status = '1'"

    signals = extract_sql_signals(src, tgt, seed_keywords=["vdmduyetuq", "dmduyet"])
    assert "source_refs_vdmduyetuq" in signals
    assert "target_refs_dmduyet" in signals


def test_hunk_signals():
    preview = [
        "- SELECT * FROM dmduyet",
        "+ SELECT * FROM vdmduyetuq",
    ]
    signals = extract_hunk_signals(preview)
    assert "dmduyet_vs_vdmduyetuq" in signals
