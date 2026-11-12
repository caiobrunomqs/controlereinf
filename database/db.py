from __future__ import annotations

from contextlib import closing, contextmanager
import os
from pathlib import Path
import sqlite3
import unicodedata

BASE_DIR = Path(__file__).resolve().parents[1]
# REINF_DB_PATH permite apontar para outra base (cópia de teste, backup).
DB_PATH = Path(os.environ.get("REINF_DB_PATH") or BASE_DIR / "data" / "reinf_control.db")
SCHEMA_PATH = Path(__file__).with_name("schema.sql")

# Versão do schema gravada em PRAGMA user_version.
# 1 = classificação automática "sem documentação" já executada uma vez.
SCHEMA_VERSION = 1


def connect(db_path: Path | str = DB_PATH) -> sqlite3.Connection:
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


@contextmanager
def transaction(db_path: Path | str = DB_PATH):
    con = connect(db_path)
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def _columns(con: sqlite3.Connection, table: str) -> set[str]:
    return {row["name"] for row in con.execute(f"PRAGMA table_info({table})").fetchall()}


def _normalize(value: str | None) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(ch for ch in text if not unicodedata.combining(ch)).lower().strip()


def classify_missing_documentation(con: sqlite3.Connection) -> int:
    """Marca como fora das métricas as empresas cujo texto legado indica
    ausência de documentação. Deve rodar uma única vez (carga inicial ou
    atualização de versão), para não desfazer reintegrações manuais."""
    rows = con.execute(
        """
        SELECT id, legacy_status, legacy_observation, legacy_extra_note,
               metrics_excluded
        FROM companies
        """
    ).fetchall()

    changed = 0
    for row in rows:
        legacy_text = " ".join(
            str(row[key] or "")
            for key in ("legacy_status", "legacy_observation", "legacy_extra_note")
        )
        normalized = _normalize(legacy_text)

        sem_documentacao = (
            "sem documentacao" in normalized
            or "sem documentos" in normalized
        )

        if sem_documentacao and not row["metrics_excluded"]:
            con.execute(
                """
                UPDATE companies
                SET metrics_excluded = 1,
                    exclusion_reason = COALESCE(exclusion_reason, 'Sem documentação')
                WHERE id = ?
                """,
                (row["id"],),
            )
            changed += 1
    return changed


def _upgrade_database(con: sqlite3.Connection) -> None:
    company_columns = _columns(con, "companies")

    if "metrics_excluded" not in company_columns:
        con.execute(
            "ALTER TABLE companies ADD COLUMN metrics_excluded INTEGER NOT NULL DEFAULT 0"
        )

    company_columns = _columns(con, "companies")
    if "exclusion_reason" not in company_columns:
        con.execute(
            "ALTER TABLE companies ADD COLUMN exclusion_reason TEXT"
        )

    legacy_columns = _columns(con, "legacy_ata_entries")
    if "reconciled_ata_id" not in legacy_columns:
        con.execute("ALTER TABLE legacy_ata_entries ADD COLUMN reconciled_ata_id INTEGER REFERENCES atas(id)")
    if "reconciled_at" not in legacy_columns:
        con.execute("ALTER TABLE legacy_ata_entries ADD COLUMN reconciled_at TEXT")

    version = con.execute("PRAGMA user_version").fetchone()[0]
    if version < 1:
        # Bases anteriores à v0.4.1: aplica a classificação automática uma
        # única vez. Depois disso, a classificação é sempre manual.
        classify_missing_documentation(con)

    if version < SCHEMA_VERSION:
        con.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")


def init_db(db_path: Path | str = DB_PATH) -> None:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with closing(connect(db_path)) as con:
        con.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        _upgrade_database(con)
        con.commit()


def fetch_all(sql: str, params=(), db_path: Path | str = DB_PATH):
    with closing(connect(db_path)) as con:
        return con.execute(sql, params).fetchall()


def fetch_one(sql: str, params=(), db_path: Path | str = DB_PATH):
    with closing(connect(db_path)) as con:
        return con.execute(sql, params).fetchone()


def execute(sql: str, params=(), db_path: Path | str = DB_PATH) -> int:
    with transaction(db_path) as con:
        cur = con.execute(sql, params)
        return int(cur.lastrowid or 0)


def log_history(entity_type: str, entity_id: int | None, action: str, detail: str = "") -> None:
    execute(
        "INSERT INTO history(entity_type, entity_id, action, detail) VALUES (?, ?, ?, ?)",
        (entity_type, entity_id, action, detail),
    )
