"""Tests for queryDatabase executor helpers."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from queryDatabase.executor import (
    collect_cursor_messages,
    format_pyodbc_error,
)


class TestExecutorHelpers(unittest.TestCase):
    def test_collect_cursor_messages(self):
        cursor = SimpleNamespace(
            messages=[
                (None, "[SQL Server]debug step 1"),
                (None, "[SQL Server]debug step 2"),
                (None, "[SQL Server]debug step 1"),
            ]
        )
        self.assertEqual(
            collect_cursor_messages(cursor),
            [
                "[SQL Server]debug step 1",
                "[SQL Server]debug step 2",
            ],
        )

    def test_collect_cursor_messages_empty(self):
        cursor = SimpleNamespace(messages=[])
        self.assertEqual(collect_cursor_messages(cursor), [])

    def test_format_pyodbc_error(self):
        exc = Exception(
            "('42000', '[42000] [Microsoft][ODBC Driver 17 for SQL Server]"
            "[SQL Server]Invalid column name \\'foo\\'. (207) (SQLExecDirectW)')",
        )
        text = format_pyodbc_error(exc)
        self.assertIn("Invalid column name", text)

    def test_format_pyodbc_error_with_message_list(self):
        class FakeError(Exception):
            args = (
                "main error",
                [
                    ("42000", "[SQL Server]Line 5: syntax error"),
                    ("01000", "[SQL Server]PRINT debug info"),
                ],
            )

        text = format_pyodbc_error(FakeError())
        self.assertIn("main error", text)
        self.assertIn("syntax error", text)
        self.assertIn("PRINT debug info", text)


if __name__ == "__main__":
    unittest.main()
