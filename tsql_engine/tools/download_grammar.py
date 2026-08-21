#!/usr/bin/env python3
"""Download official T-SQL ANTLR4 grammar into tsql_engine/grammar/."""

from __future__ import annotations

import urllib.request
from pathlib import Path

BASE_URL = "https://raw.githubusercontent.com/antlr/grammars-v4/master/sql/tsql"
FILES = ("TSqlLexer.g4", "TSqlParser.g4")
README_URL = "https://raw.githubusercontent.com/antlr/grammars-v4/master/sql/tsql/README.md"


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    grammar_dir = root / "grammar"
    grammar_dir.mkdir(parents=True, exist_ok=True)

    for name in FILES:
        url = f"{BASE_URL}/{name}"
        dest = grammar_dir / name
        print(f"Downloading {url} -> {dest}")
        urllib.request.urlretrieve(url, dest)
        print(f"  OK ({dest.stat().st_size} bytes)")

    readme_dest = grammar_dir / "UPSTREAM_README.md"
    print(f"Downloading {README_URL} -> {readme_dest}")
    urllib.request.urlretrieve(README_URL, readme_dest)
    print("Done.")


if __name__ == "__main__":
    main()
