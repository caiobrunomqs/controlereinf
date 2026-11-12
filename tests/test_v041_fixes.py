from functools import partial
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest import mock

from database import db
from database.db import init_db
from services import company_service
from services.migration import migrate_workbook

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "carteira_ficticia.xlsx"


class V041FixesTests(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.db_path = Path(self._td.name) / "test.db"
        self.stats = migrate_workbook(FIXTURE, self.db_path, reset=True)

    def tearDown(self):
        # Falharia no Windows se alguma conexão ficasse aberta.
        self._td.cleanup()

    def _query(self, sql, params=()):
        con = sqlite3.connect(self.db_path)
        try:
            return con.execute(sql, params).fetchall()
        finally:
            con.close()

    def test_migration_classifies_missing_documentation(self):
        self.assertGreater(self.stats["no_docs"], 0)
        excluded = self._query("SELECT COUNT(*) FROM companies WHERE metrics_excluded = 1")[0][0]
        self.assertEqual(excluded, self.stats["no_docs"])

    def test_reintegration_survives_app_restart(self):
        company_id = self._query(
            "SELECT id FROM companies WHERE metrics_excluded = 1 LIMIT 1"
        )[0][0]
        con = sqlite3.connect(self.db_path)
        try:
            con.execute("UPDATE companies SET metrics_excluded = 0 WHERE id = ?", (company_id,))
            con.commit()
        finally:
            con.close()

        init_db(self.db_path)  # o app chama isto a cada interação
        init_db(self.db_path)

        value = self._query(
            "SELECT metrics_excluded FROM companies WHERE id = ?", (company_id,)
        )[0][0]
        self.assertEqual(value, 0)

    def test_legacy_database_is_classified_once_on_upgrade(self):
        con = sqlite3.connect(self.db_path)
        try:
            con.execute("UPDATE companies SET metrics_excluded = 0")
            con.execute("PRAGMA user_version = 0")
            con.commit()
        finally:
            con.close()

        init_db(self.db_path)
        excluded = self._query("SELECT COUNT(*) FROM companies WHERE metrics_excluded = 1")[0][0]
        self.assertEqual(excluded, self.stats["no_docs"])

    def test_search_without_digits_does_not_match_every_cnpj(self):
        fetch = partial(db.fetch_all, db_path=self.db_path)
        with mock.patch.object(company_service, "fetch_all", fetch):
            self.assertEqual(len(company_service.list_companies(search="zzqq")), 0)

            some = self._query("SELECT name, cnpj FROM companies WHERE cnpj IS NOT NULL LIMIT 1")[0]
            by_name = company_service.list_companies(search=some[0][:6])
            self.assertTrue(any(r["name"] == some[0] for r in by_name))
            by_cnpj = company_service.list_companies(search=some[1][:8])
            self.assertTrue(any(r["cnpj"] == some[1] for r in by_cnpj))


if __name__ == "__main__":
    unittest.main()
