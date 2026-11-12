"""Gera tests/fixtures/carteira_ficticia.xlsx: planilha pequena, 100% fictícia,
no mesmo layout de abas que services/migration.py espera.

Escrita "à mão" (zip + XML) para não exigir openpyxl só por causa dos testes.
Rode de novo se mudar os dados:  python tests/fixtures/build_fixture.py
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape
import zipfile

OUT = Path(__file__).with_name("carteira_ficticia.xlsx")

# CNPJs com dígito verificador propositalmente inválido: não podem pertencer
# a nenhuma empresa real.

COMPANY_HEADER = ["Código", "Empresa", "CNPJ", "IM/IE", "Regime", "UF", "Cliente desde",
                  "Situação", "Observação", "Nota"]
COMPANIES = [
    [101, "Aroeira Comércio de Alimentos Ltda", "12.345.678/0001-00", "123456", "Lucro Presumido", "SP",
     date(2019, 3, 1), "Ativa", "REINF até o mês 3", None],
    [102, "Bela Serra Engenharia Ltda", "23.456.789/0001-00", "998877", "Lucro Real", "MG",
     date(2021, 7, 1), "Ativa", None, None],
    [103, "Cedro Azul Transportes Ltda", "34.567.890/0001-00", None, "Lucro Presumido", "PR",
     "desde 2018", "Ativa", "Sem documentação", "Cliente não envia extratos"],
    [104, "Delta Campos Odontologia Ltda", "45.678.901/0001-00", "445566", "Simples Nacional", "SC",
     date(2023, 1, 1), "Inativa", None, None],
    [105, "Estrela do Cerrado Tecnologia Ltda", 67890123000100, "112233", "Lucro Presumido", "GO",
     date(2020, 11, 1), True, None, None],
]

# Aba de atas: linhas 2-6 = controle mensal legado; linha 9 = cabeçalho do
# controle geral; dados a partir da linha 10.
LEGACY_HEADER = ["Empresa", "Saldo inicial", "Jan", "Fev", "Mar", "Abr", "Mai", "Total", "Saldo"]
LEGACY = [
    ["BELA SERRA ENGENHARIA", "R$ 500.000,00", 10000, 12000.5, 9000, 11000, 10500, 52500.5, 447499.5],
    ["EMPRESA NÃO CADASTRADA", 80000, None, None, None, None, None, 0, 80000],
]
GENERAL_HEADER = ["Empresa", "CNPJ", "Valor da ata", "Já distribuído", "Saldo", "Classificação"]
GENERAL = [
    ["Aroeira Comércio de Alimentos Ltda", "12.345.678/0001-00", 300000, 50000, 250000,
     "Valor definitivo identificado"],
    ["Bela Serra Engenharia Ltda", "23.456.789/0001-00", "R$ 500.000,00", 0, 500000,
     "Valor definitivo identificado"],
    ["Fictícia Nova Consultoria Ltda", "78.901.234/0001-00", 120000, 0, 120000,
     "Valor provisório sujeito a ajuste"],
]


def _col(idx: int) -> str:
    name = ""
    idx += 1
    while idx:
        idx, rem = divmod(idx - 1, 26)
        name = chr(65 + rem) + name
    return name


def _cell(ref: str, value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return f'<c r="{ref}" t="b"><v>{int(value)}</v></c>'
    if isinstance(value, date):
        serial = (value - date(1899, 12, 30)).days
        return f'<c r="{ref}" s="1"><v>{serial}</v></c>'
    if isinstance(value, (int, float)):
        return f'<c r="{ref}"><v>{value}</v></c>'
    return f'<c r="{ref}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>'


def _sheet(rows: list[list]) -> str:
    body = []
    for r, row in enumerate(rows, start=1):
        cells = "".join(_cell(f"{_col(c)}{r}", v) for c, v in enumerate(row))
        body.append(f'<row r="{r}">{cells}</row>')
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(body)}</sheetData></worksheet>'
    )


def build(out: Path = OUT) -> Path:
    # Mantém o cabeçalho do controle geral na linha 9.
    ata_rows = [LEGACY_HEADER, *LEGACY] + [[]] * (8 - 1 - len(LEGACY)) + [GENERAL_HEADER, *GENERAL]
    sheets = {
        "Dados das empresas": [COMPANY_HEADER, *COMPANIES],
        "ATAS de distribuição": ata_rows,
    }
    ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    rel_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    pkg_ns = "http://schemas.openxmlformats.org/package/2006/relationships"

    workbook = (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook {ns} xmlns:r="{rel_ns}"><sheets>'
        + "".join(
            f'<sheet name="{escape(name)}" sheetId="{i}" r:id="rId{i}"/>'
            for i, name in enumerate(sheets, start=1)
        )
        + "</sheets></workbook>"
    )
    workbook_rels = (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="{pkg_ns}">'
        + "".join(
            f'<Relationship Id="rId{i}" Type="{rel_ns}/worksheet" Target="worksheets/sheet{i}.xml"/>'
            for i in range(1, len(sheets) + 1)
        )
        + f'<Relationship Id="rId{len(sheets) + 1}" Type="{rel_ns}/styles" Target="styles.xml"/>'
        "</Relationships>"
    )
    styles = (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet {ns}>'
        '<cellXfs count="2"><xf numFmtId="0"/><xf numFmtId="14" applyNumberFormat="1"/></cellXfs>'
        "</styleSheet>"
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/styles.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        + "".join(
            f'<Override PartName="/xl/worksheets/sheet{i}.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            for i in range(1, len(sheets) + 1)
        )
        + "</Types>"
    )
    root_rels = (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="{pkg_ns}">'
        f'<Relationship Id="rId1" Type="{rel_ns}/officeDocument" Target="xl/workbook.xml"/>'
        "</Relationships>"
    )

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", root_rels)
        zf.writestr("xl/workbook.xml", workbook)
        zf.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        zf.writestr("xl/styles.xml", styles)
        for i, rows in enumerate(sheets.values(), start=1):
            zf.writestr(f"xl/worksheets/sheet{i}.xml", _sheet(rows))
    return out


if __name__ == "__main__":
    print(f"Gerado: {build()}")
