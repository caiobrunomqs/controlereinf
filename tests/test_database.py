from pathlib import Path
import sqlite3
import tempfile
import unittest

from services.migration import migrate_workbook

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "carteira_ficticia.xlsx"


class DatabaseMigrationTests(unittest.TestCase):
    def test_migration_builds_database(self):
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "test.db"
            stats = migrate_workbook(FIXTURE, db_path, reset=True)
            # 5 da aba principal + 1 que só aparece na aba de atas.
            self.assertEqual(stats["companies"], 6)
            self.assertEqual(stats["atas"], 3)
            self.assertEqual(stats["legacy_ata_rows"], 2)
            self.assertEqual(stats["no_docs"], 1)

            con = sqlite3.connect(db_path)
            try:
                inactive = con.execute("SELECT COUNT(*) FROM companies WHERE active = 0").fetchone()[0]
                start = con.execute(
                    "SELECT start_date, start_raw FROM companies WHERE legacy_code = 103"
                ).fetchone()
                linked = con.execute(
                    "SELECT COUNT(*) FROM legacy_ata_entries WHERE linked_company_id IS NOT NULL"
                ).fetchone()[0]
            finally:
                con.close()

            self.assertEqual(inactive, 1)
            self.assertEqual(start, (None, "desde 2018"))
            self.assertEqual(linked, 1)

    def test_reinf_until_month_text_creates_sent_competencies(self):
        # Regra conservadora: "REINF até o mês 3" vira jan–mar como Enviado, nada além.
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "test.db"
            stats = migrate_workbook(FIXTURE, db_path, reset=True)
            self.assertEqual(stats["historical_reinf_rows"], 3)
            con = sqlite3.connect(db_path)
            try:
                rows = con.execute(
                    "SELECT month, workflow_status FROM reinf_competencies ORDER BY month"
                ).fetchall()
            finally:
                con.close()
            self.assertEqual(rows, [(1, "Enviado"), (2, "Enviado"), (3, "Enviado")])


if __name__ == "__main__":
    unittest.main()
