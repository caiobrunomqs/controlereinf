from pathlib import Path
import sqlite3
import tempfile
import unittest

from database.db import init_db


class AtaMonthlyMovementTests(unittest.TestCase):
    def test_manual_movement_table_exists(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "test.db"
            init_db(db)
            con = sqlite3.connect(db)
            try:
                tables = {
                    row[0]
                    for row in con.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).fetchall()
                }
            finally:
                con.close()

            self.assertIn("ata_manual_movements", tables)


if __name__ == "__main__":
    unittest.main()
