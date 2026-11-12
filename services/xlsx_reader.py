from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import zipfile

MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"

DATE_BUILTIN_IDS = set(range(14, 23)) | set(range(27, 37)) | set(range(45, 48)) | set(range(50, 59))


def _column_index(cell_ref: str) -> int:
    letters = re.match(r"([A-Z]+)", cell_ref.upper()).group(1)
    value = 0
    for char in letters:
        value = value * 26 + (ord(char) - 64)
    return value - 1


def _shared_strings(zf: zipfile.ZipFile) -> list[str]:
    path = "xl/sharedStrings.xml"
    if path not in zf.namelist():
        return []
    root = ET.fromstring(zf.read(path))
    values = []
    for si in root.findall(f"{{{MAIN_NS}}}si"):
        parts = [node.text or "" for node in si.iter(f"{{{MAIN_NS}}}t")]
        values.append("".join(parts))
    return values


def _date_style_indexes(zf: zipfile.ZipFile) -> set[int]:
    path = "xl/styles.xml"
    if path not in zf.namelist():
        return set()

    root = ET.fromstring(zf.read(path))
    custom = {}
    numfmts = root.find(f"{{{MAIN_NS}}}numFmts")
    if numfmts is not None:
        for fmt in numfmts.findall(f"{{{MAIN_NS}}}numFmt"):
            custom[int(fmt.attrib["numFmtId"])] = fmt.attrib.get("formatCode", "")

    xfs = root.find(f"{{{MAIN_NS}}}cellXfs")
    result = set()
    if xfs is None:
        return result

    for idx, xf in enumerate(xfs.findall(f"{{{MAIN_NS}}}xf")):
        num_fmt_id = int(xf.attrib.get("numFmtId", "0"))
        if num_fmt_id in DATE_BUILTIN_IDS:
            result.add(idx)
            continue
        fmt = custom.get(num_fmt_id, "")
        cleaned = re.sub(r'"[^"]*"|\[[^\]]*\]|\\.', "", fmt.lower())
        if re.search(r"[ymdhis]", cleaned):
            result.add(idx)
    return result


def _sheet_map(zf: zipfile.ZipFile) -> dict[str, str]:
    workbook = ET.fromstring(zf.read("xl/workbook.xml"))
    rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))

    rel_map = {}
    for rel in rels.findall(f"{{{PKG_REL_NS}}}Relationship"):
        rel_map[rel.attrib["Id"]] = rel.attrib["Target"]

    result = {}
    sheets = workbook.find(f"{{{MAIN_NS}}}sheets")
    for sheet in sheets.findall(f"{{{MAIN_NS}}}sheet"):
        name = sheet.attrib["name"]
        rid = sheet.attrib[f"{{{REL_NS}}}id"]
        target = rel_map[rid].lstrip("/")
        if not target.startswith("xl/"):
            target = "xl/" + target
        result[name] = target
    return result


def _excel_date(value: float):
    # Compatível com o sistema de datas 1900 do Excel, incluindo o ajuste histórico.
    dt = datetime(1899, 12, 30) + timedelta(days=value)
    if dt.time().hour == 0 and dt.time().minute == 0 and dt.time().second == 0:
        return dt.date()
    return dt


def read_sheet(path: Path | str, sheet_name: str) -> list[list]:
    path = Path(path)
    with zipfile.ZipFile(path) as zf:
        shared = _shared_strings(zf)
        date_styles = _date_style_indexes(zf)
        sheet_map = _sheet_map(zf)
        if sheet_name not in sheet_map:
            raise KeyError(f"Aba não encontrada: {sheet_name}")

        root = ET.fromstring(zf.read(sheet_map[sheet_name]))
        sheet_data = root.find(f"{{{MAIN_NS}}}sheetData")
        rows = []

        for row in sheet_data.findall(f"{{{MAIN_NS}}}row"):
            values = {}
            max_col = -1

            for cell in row.findall(f"{{{MAIN_NS}}}c"):
                ref = cell.attrib.get("r", "A1")
                col = _column_index(ref)
                max_col = max(max_col, col)

                cell_type = cell.attrib.get("t")
                style_idx = int(cell.attrib.get("s", "0"))
                v = cell.find(f"{{{MAIN_NS}}}v")

                if cell_type == "inlineStr":
                    is_node = cell.find(f"{{{MAIN_NS}}}is")
                    parts = [] if is_node is None else [n.text or "" for n in is_node.iter(f"{{{MAIN_NS}}}t")]
                    value = "".join(parts)
                elif v is None:
                    value = None
                else:
                    raw = v.text or ""
                    if cell_type == "s":
                        value = shared[int(raw)]
                    elif cell_type == "b":
                        value = raw == "1"
                    elif cell_type in {"str", "e"}:
                        value = raw
                    else:
                        try:
                            number = float(raw)
                            if style_idx in date_styles:
                                value = _excel_date(number)
                            elif number.is_integer():
                                value = int(number)
                            else:
                                value = number
                        except ValueError:
                            value = raw

                values[col] = value

            if max_col >= 0:
                row_values = [None] * (max_col + 1)
                for col, value in values.items():
                    row_values[col] = value
                rows.append(row_values)
            else:
                rows.append([])

        return rows


def list_sheets(path: Path | str) -> list[str]:
    with zipfile.ZipFile(path) as zf:
        return list(_sheet_map(zf).keys())
