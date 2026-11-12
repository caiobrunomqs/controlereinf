from contextlib import ExitStack
from functools import partial
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from database import db
from services import ata_service as atas
from services import reinf_service as reinf
from services.migration import migrate_workbook

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "carteira_ficticia.xlsx"


class AtaControlTests(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.db_path = Path(self._td.name) / "test.db"
        migrate_workbook(FIXTURE, self.db_path, reset=True)

        # Aponta os serviços para a base temporária.
        self._stack = ExitStack()
        for module in (atas, reinf):
            for name, fn in (("fetch_all", db.fetch_all), ("fetch_one", db.fetch_one), ("transaction", db.transaction)):
                self._stack.enter_context(mock.patch.object(module, name, partial(fn, db_path=self.db_path)))
        self._stack.enter_context(mock.patch.object(reinf, "log_history", lambda *a, **k: None))

        ata = atas.list_atas()[0]
        self.ata_id = ata["id"]
        self.company_id = ata["company_id"]
        # Saldo de partida: valor da ata menos o que já fora distribuído antes do sistema.
        self.original = ata["original_value"] - ata["opening_distributed"]

    def tearDown(self):
        self._stack.close()
        self._td.cleanup()

    def _balance(self):
        return atas.get_ata(self.ata_id)["calculated_balance"]

    def test_statement_running_balance_matches_view(self):
        atas.add_manual_movement(self.ata_id, 2026, 1, 1000.10, "Consumo", "")
        atas.add_manual_movement(self.ata_id, 2026, 2, 200.20, "Consumo", "")
        atas.add_manual_movement(self.ata_id, 2026, 2, 100.05, "Estorno", "")
        reinf.add_withdrawal(self.company_id, 2026, 3, "Sócio A", 50.30, "", self.ata_id, True, "")

        statement = atas.ata_statement(self.ata_id)
        self.assertEqual(len(statement), 4)
        self.assertAlmostEqual(statement[-1]["balance_after"], self._balance(), places=2)
        self.assertAlmostEqual(self._balance(), round(self.original - 1000.10 - 200.20 + 100.05 - 50.30, 2), places=2)

    def test_no_movement_closes_gap_without_changing_balance(self):
        before = self._balance()
        gaps = [a for a in atas.ata_alerts(2026, 2) if a["ata_id"] == self.ata_id and a["kind"] == "lacuna"]
        self.assertTrue(gaps)

        atas.add_manual_movement(self.ata_id, 2026, 1, 0, "Sem movimento", "")
        atas.add_manual_movement(self.ata_id, 2026, 2, 0, "Sem movimento", "")

        gaps = [a for a in atas.ata_alerts(2026, 2) if a["ata_id"] == self.ata_id and a["kind"] == "lacuna"]
        self.assertEqual(gaps, [])
        self.assertEqual(self._balance(), before)

    def test_reinf_plus_manual_same_month_is_flagged(self):
        atas.add_manual_movement(self.ata_id, 2026, 4, 500, "Consumo", "")
        reinf.add_withdrawal(self.company_id, 2026, 4, "Sócio A", 500, "", self.ata_id, False, "")
        dup = [a for a in atas.ata_alerts(2026, 4) if a["ata_id"] == self.ata_id and a["kind"] == "duplicidade"]
        self.assertEqual(len(dup), 1)

    def test_withdrawal_cannot_use_other_company_ata(self):
        other = next(a for a in atas.list_atas() if a["company_id"] != self.company_id)
        with self.assertRaises(ValueError):
            reinf.add_withdrawal(self.company_id, 2026, 1, "Sócio", 10, "", other["id"], False, "")

    def test_edit_and_delete_movements(self):
        mid = atas.add_manual_movement(self.ata_id, 2026, 5, 300, "Consumo", "")
        atas.update_manual_movement(mid, 2026, 5, 450, "Consumo", "corrigido")
        self.assertAlmostEqual(self._balance(), self.original - 450, places=2)
        atas.delete_manual_movement(mid)
        self.assertAlmostEqual(self._balance(), self.original, places=2)

        wid = reinf.add_withdrawal(self.company_id, 2026, 5, "Sócio", 100, "", self.ata_id, False, "")
        reinf.update_withdrawal(wid, "Sócio", 100, "", None, False, "")  # desvincula
        self.assertAlmostEqual(self._balance(), self.original, places=2)
        reinf.delete_withdrawal(wid)
        self.assertIsNone(reinf.get_withdrawal(wid))

    def test_ata_with_entries_cannot_be_deleted(self):
        atas.add_manual_movement(self.ata_id, 2026, 1, 10, "Consumo", "")
        with self.assertRaises(ValueError):
            atas.delete_ata(self.ata_id)

    def test_legacy_import_creates_movements_and_blocks_duplicates(self):
        item = next(i for i in atas.legacy_entries() if (i["jan"] or 0) > 0)
        target = next(a for a in atas.list_atas() if a["company_id"] == item["linked_company_id"])
        before = target["calculated_balance"]
        months_total = sum(item[k] or 0 for k in ("jan", "feb", "mar", "apr", "may"))

        legacy_alerts = [a for a in atas.ata_alerts(2026, 5) if a["kind"] == "legado"]
        self.assertTrue(legacy_alerts)

        n = atas.import_legacy_entry(item["id"], target["id"], 2026)
        self.assertEqual(n, 5)
        after = atas.get_ata(target["id"])["calculated_balance"]
        self.assertAlmostEqual(before - after, months_total, places=2)
        self.assertFalse([a for a in atas.ata_alerts(2026, 5) if a["kind"] == "legado"])

        with self.assertRaises(ValueError):
            atas.import_legacy_entry(item["id"], target["id"], 2026)

    def test_legacy_import_refuses_when_month_already_recorded(self):
        item = next(i for i in atas.legacy_entries() if (i["jan"] or 0) > 0)
        target = next(a for a in atas.list_atas() if a["company_id"] == item["linked_company_id"])
        atas.add_manual_movement(target["id"], 2026, 1, 1, "Consumo", "")
        with self.assertRaises(ValueError):
            atas.import_legacy_entry(item["id"], target["id"], 2026)


if __name__ == "__main__":
    unittest.main()
