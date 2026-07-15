"""Tests for queryDatabase query_resolver."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from queryDatabase.query_resolver import (
    build_object_lookup_sql,
    is_user_table,
    normalize_query_type,
    parse_object_lookup_result,
    read_sql_file,
    resolve_object_sql,
    resolve_query,
    should_use_helptext,
)


class TestQueryResolver(unittest.TestCase):
    def test_normalize_query_type(self):
        self.assertEqual(normalize_query_type(0), 0)
        self.assertEqual(normalize_query_type(1), 1)
        self.assertEqual(normalize_query_type(2), 2)
        with self.assertRaises(ValueError):
            normalize_query_type(3)

    def test_read_sql_file(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".sql", delete=False, encoding="utf-8"
        ) as f:
            f.write("SELECT 1 AS x\n")
            path = f.name

        try:
            sql, label = read_sql_file(path)
            self.assertEqual(sql, "SELECT 1 AS x")
            self.assertTrue(label.startswith("sql_file:"))
            self.assertIn(Path(path).resolve().as_posix().split("/")[-1], label.replace("\\", "/"))
        finally:
            Path(path).unlink(missing_ok=True)

    def test_read_sql_file_errors(self):
        with self.assertRaises(FileNotFoundError):
            read_sql_file("E:\\nonexistent\\missing.sql")

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write("SELECT 1")
            path = f.name
        try:
            with self.assertRaises(ValueError):
                read_sql_file(path)
        finally:
            Path(path).unlink(missing_ok=True)

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".sql", delete=False, encoding="utf-8"
        ) as f:
            f.write("   \n  ")
            path = f.name
        try:
            with self.assertRaises(ValueError):
                read_sql_file(path)
        finally:
            Path(path).unlink(missing_ok=True)

    def test_resolve_query_type2(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".sql", delete=False, encoding="utf-8"
        ) as f:
            f.write("SELECT 2")
            path = f.name
        try:
            sql, label = resolve_query(2, path)
            self.assertEqual(sql, "SELECT 2")
            self.assertTrue(label.startswith("sql_file:"))
        finally:
            Path(path).unlink(missing_ok=True)

    def test_build_object_lookup_sql(self):
        sql = build_object_lookup_sql("dmkh")
        self.assertIn("sys.objects", sql)
        self.assertIn("N'dmkh'", sql)

    def test_parse_object_lookup(self):
        result = {
            "result_sets": [
                {"columns": ["type", "type_desc"], "rows": [["U", "USER_TABLE"]]}
            ]
        }
        self.assertEqual(parse_object_lookup_result(result), ("U", "USER_TABLE"))
        empty = {"result_sets": [{"columns": ["type"], "rows": []}]}
        self.assertIsNone(parse_object_lookup_result(empty))

    def test_resolve_object_sql(self):
        sql, label, resolved = resolve_object_sql("dmkh", "U", "USER_TABLE")
        self.assertEqual(resolved, "table_schema")
        self.assertIn("dmkh", sql)

        sql, label, resolved = resolve_object_sql("ff_x", "P", "SQL_STORED_PROCEDURE")
        self.assertEqual(resolved, "object_definition")
        self.assertIn("sp_helptext", sql)

        sql, label = resolve_query(1, "SELECT 1")
        self.assertEqual(sql, "SELECT 1")
        self.assertEqual(label, "free_query")

    def test_object_type_helpers(self):
        self.assertTrue(is_user_table("U", "USER_TABLE"))
        self.assertFalse(is_user_table("P", "SQL_STORED_PROCEDURE"))
        self.assertTrue(should_use_helptext("FN", "SQL_SCALAR_FUNCTION"))
        self.assertFalse(should_use_helptext("U", "USER_TABLE"))


if __name__ == "__main__":
    unittest.main()
