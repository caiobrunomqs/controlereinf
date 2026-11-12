from pathlib import Path
import sqlite3
import tempfile
import unittest

from database.db import init_db


class MetricsExclusionTests(unittest.TestCase):
    def test_upgrade_adds_metrics_columns(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "db.sqlite"
            init_db(db)
            con = sqlite3.connect(db)
            try:
                cols = {row[1] for row in con.execute("PRAGMA table_info(companies)")}
            finally:
                con.close()

            self.assertIn("metrics_excluded", cols)
            self.assertIn("exclusion_reason", cols)


if __name__ == "__main__":
    unittest.main()
