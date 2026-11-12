from contextlib import ExitStack
from functools import partial
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest import mock

from database import db
from scripts.seed_demo import build_demo_database, cnpj_check_digits, is_valid_cnpj
from services import ata_service as atas


class SeedDemoTests(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.db_path = Path(self._td.name) / "demo.db"
        self.info = build_demo_database(self.db_path)
        self._stack = ExitStack()
        for name, fn in (("fetch_all", db.fetch_all), ("fetch_one", db.fetch_one), ("transaction", db.transaction)):
            self._stack.enter_context(mock.patch.object(atas, name, partial(fn, db_path=self.db_path)))

    def tearDown(self):
        self._stack.close()
        self._td.cleanup()

    def _query(self, sql):
        con = sqlite3.connect(self.db_path)
        try:
            return con.execute(sql).fetchall()
        finally:
            con.close()

    def test_cnpj_check_digits(self):
        self.assertEqual(cnpj_check_digits("112223330001"), "81")  # exemplo clássico da documentação
        self.assertFalse(is_valid_cnpj("11222333000182"))
        self.assertFalse(is_valid_cnpj("11111111111111"))

    def test_companies_have_valid_unique_cnpjs(self):
        cnpjs = [r[0] for r in self._query("SELECT cnpj FROM companies")]
        self.assertEqual(len(cnpjs), 40)
        self.assertEqual(len(set(cnpjs)), 40)
        self.assertTrue(all(is_valid_cnpj(c) for c in cnpjs))

    def test_seed_is_deterministic(self):
        other = Path(self._td.name) / "again.db"
        build_demo_database(other)
        sql = "SELECT name, cnpj FROM companies ORDER BY id"
        con = sqlite3.connect(other)
        try:
            again = con.execute(sql).fetchall()
        finally:
            con.close()
        self.assertEqual(again, self._query(sql))

    def test_demo_covers_every_screen(self):
        statuses = {r[0] for r in self._query("SELECT DISTINCT workflow_status FROM reinf_competencies")}
        self.assertGreaterEqual(len(statuses), 6)
        self.assertGreater(self._query("SELECT COUNT(*) FROM companies WHERE metrics_excluded = 1")[0][0], 0)

        health = {o["health"] for o in atas.ata_overview()}
        self.assertTrue({"ok", "baixo", "negativo", "sem_valor", "encerrada"} <= health)

        kinds = {a["kind"] for a in atas.ata_alerts(2026, 10)}
        self.assertTrue({"lacuna", "duplicidade", "sem_vinculo", "legado", "saldo"} <= kinds)

    def test_legacy_line_can_be_reconciled(self):
        item = atas.legacy_entries()[0]
        self.assertIsNone(item["reconciled_at"])
        self.assertEqual(atas.import_legacy_entry(item["id"], self.info["legacy_ata_id"], 2026), 5)

    def test_refuses_to_seed_over_existing_data(self):
        with self.assertRaises(RuntimeError):
            build_demo_database(self.db_path)


if __name__ == "__main__":
    unittest.main()
