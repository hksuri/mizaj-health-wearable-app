from __future__ import annotations

from pathlib import Path

import duckdb

from mizaj.config import settings


def connect_gold(path: Path | None = None) -> duckdb.DuckDBPyConnection:
    db_path = path or settings.duckdb_path
    if not db_path.exists():
        raise FileNotFoundError(f"Gold DuckDB not found at {db_path}. Run make synth.")
    return duckdb.connect(str(db_path), read_only=True)
