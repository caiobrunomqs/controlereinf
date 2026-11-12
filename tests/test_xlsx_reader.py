from datetime import date
from pathlib import Path
import unittest

from services.xlsx_reader import list_sheets, read_sheet

SOURCE = Path(__file__).resolve().parent / "fixtures" / "carteira_ficticia.xlsx"


class XlsxReaderTests(unittest.TestCase):
    def test_expected_sheets_exist(self):
        sheets = list_sheets(SOURCE)
        self.assertIn("Dados das empresas", sheets)
        self.assertIn("ATAS de distribuição", sheets)

    def test_company_sheet_values_and_types(self):
        rows = read_sheet(SOURCE, "Dados das empresas")
        names = [row[1] for row in rows[1:] if len(row) > 1 and row[1]]
        self.assertEqual(len(names), 5)
        first = rows[1]
        self.assertEqual(first[0], 101)                 # número inteiro
        self.assertEqual(first[6], date(2019, 3, 1))    # data pelo estilo da célula
        self.assertEqual(rows[3][6], "desde 2018")      # texto livre preservado
        self.assertIs(rows[5][7], True)                 # booleano

    def test_ata_general_control_starts_at_row_10(self):
        rows = read_sheet(SOURCE, "ATAS de distribuição")
        self.assertEqual(rows[8][0], "Empresa")
        names = [row[0] for row in rows[9:] if row and row[0]]
        self.assertEqual(len(names), 3)


if __name__ == "__main__":
    unittest.main()
