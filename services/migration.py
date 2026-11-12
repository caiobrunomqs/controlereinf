from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
import re
import unicodedata

from database.db import classify_missing_documentation, init_db, transaction
from services.xlsx_reader import read_sheet

BASE_DIR = Path(__file__).resolve().parents[1]
# Planilha opcional para importar uma carteira existente (não versionada).
DEFAULT_SOURCE = BASE_DIR / "data" / "input" / "clientes.xlsx"


def normalize_text(value) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    text = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in text if not unicodedata.combining(ch)).lower()


def normalize_cnpj(value) -> str | None:
    if value in (None, ""):
        return None
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    digits = re.sub(r"\D", "", str(value))
    if not digits:
        return None
    return digits.zfill(14)[-14:]


def display_cnpj(cnpj: str | None) -> str:
    if not cnpj or len(cnpj) != 14:
        return cnpj or ""
    return f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"


def parse_currency_br(value) -> float:
    if value in (None, ""):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).replace("R$", "").replace(" ", "").strip()
    text = text.replace(".", "").replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return 0.0


def _cell(row: list, idx: int):
    return row[idx] if idx < len(row) else None


def _date_parts(value):
    if isinstance(value, datetime):
        return value.date().isoformat(), None
    if isinstance(value, date):
        return value.isoformat(), None
    if value in (None, ""):
        return None, None
    return None, str(value)


def _status_text(value) -> str:
    if value is True:
        return "OK"
    if value is False:
        return "Não"
    return "" if value is None else str(value).strip()


def _extract_reinf_through_month(*texts) -> int | None:
    joined = " ".join(str(t or "") for t in texts)
    normalized = normalize_text(joined)
    patterns = [
        r"reinf\s+ate\s+(?:o\s+)?mes\s*(\d{1,2})",
        r"reinf\s+ate\s+(\d{1,2})",
    ]
    for pattern in patterns:
        match = re.search(pattern, normalized)
        if match:
            month = int(match.group(1))
            if 1 <= month <= 12:
                return month
    return None


def _best_name_match(con, raw_name: str):
    target = normalize_text(raw_name)
    if len(target) < 4:
        return None

    rows = con.execute("SELECT id, name FROM companies").fetchall()
    candidates = []
    for row in rows:
        name_norm = normalize_text(row["name"])
        if target in name_norm or name_norm in target:
            candidates.append(row["id"])
    return candidates[0] if len(candidates) == 1 else None


def migrate_workbook(source_path: Path | str = DEFAULT_SOURCE, db_path=None, reset: bool = False) -> dict:
    """Importa uma carteira a partir de planilha .xlsx.

    Layout esperado (exemplo em tests/fixtures/carteira_ficticia.xlsx):
    - aba "Dados das empresas": cabeçalho na linha 1; colunas código, empresa,
      CNPJ, IM/IE, regime, UF, cliente desde, situação, observação, nota;
    - aba "ATAS de distribuição": linhas 2 a 6 com o controle mensal legado
      (empresa, saldo inicial, jan a mai, total, saldo) e, a partir da linha
      10, o controle geral (empresa, CNPJ, valor da ata, já distribuído, saldo,
      classificação).

    Regra conservadora: só marca competências como enviadas quando o texto
    legado diz explicitamente "REINF até o mês X" (e apenas de janeiro a X).
    """
    source_path = Path(source_path)
    if not source_path.exists():
        raise FileNotFoundError(source_path)

    from database.db import DB_PATH
    db_path = Path(db_path or DB_PATH)

    if reset and db_path.exists():
        db_path.unlink()

    init_db(db_path)

    stats = {
        "companies": 0,
        "historical_reinf_rows": 0,
        "atas": 0,
        "legacy_ata_rows": 0,
    }

    with transaction(db_path) as con:
        if con.execute("SELECT COUNT(*) FROM companies").fetchone()[0] > 0:
            raise RuntimeError("O banco já possui empresas. Use reset=True para reconstruir a base.")

        company_rows = read_sheet(source_path, "Dados das empresas")
        for row in company_rows[1:]:
            name = _cell(row, 1)
            if not name or not str(name).strip():
                continue

            legacy_code = _cell(row, 0)
            cnpj = normalize_cnpj(_cell(row, 2))
            start_date, start_raw = _date_parts(_cell(row, 6))
            status = _status_text(_cell(row, 7))
            observation = _status_text(_cell(row, 8))
            extra_note = _status_text(_cell(row, 9))

            cur = con.execute(
                """
                INSERT INTO companies(
                    legacy_code, name, cnpj, registration, tax_regime, uf,
                    start_date, start_raw, legacy_status,
                    legacy_observation, legacy_extra_note, active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(legacy_code) if isinstance(legacy_code, (int, float)) else None,
                    str(name).strip(),
                    cnpj,
                    _status_text(_cell(row, 3)),
                    _status_text(_cell(row, 4)),
                    _status_text(_cell(row, 5)),
                    start_date,
                    start_raw,
                    status,
                    observation,
                    extra_note,
                    0 if "inativa" in normalize_text(status) else 1,
                ),
            )
            company_id = cur.lastrowid
            stats["companies"] += 1

            through_month = _extract_reinf_through_month(status, observation, extra_note)
            if through_month:
                for month in range(1, through_month + 1):
                    con.execute(
                        """
                        INSERT OR IGNORE INTO reinf_competencies(
                            company_id, year, month, workflow_status,
                            documentation_status, assessment_status, obligation_status,
                            information_source, notes, migrated_from_legacy
                        ) VALUES (?, 2026, ?, 'Enviado', 'Recebida', 'Concluído',
                                  'Enviado', 'Controle legado',
                                  ?, 1)
                        """,
                        (
                            company_id,
                            month,
                            f"Migrado automaticamente a partir do texto legado: {observation or status}. Conferir se necessário.",
                        ),
                    )
                    stats["historical_reinf_rows"] += 1

        ata_rows = read_sheet(source_path, "ATAS de distribuição")

        # Controle mensal legado no topo. Mantido separado para não misturar
        # automaticamente com o controle geral de atas.
        for excel_row_num, row in enumerate(ata_rows[1:6], start=2):
            raw_name = _cell(row, 0)
            if not raw_name:
                continue
            linked_company_id = _best_name_match(con, str(raw_name))
            con.execute(
                """
                INSERT INTO legacy_ata_entries(
                    raw_name, linked_company_id, initial_balance, jan, feb, mar,
                    apr, may, total_used, remaining_balance, warning, source_row
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(raw_name).strip(),
                    linked_company_id,
                    parse_currency_br(_cell(row, 1)),
                    parse_currency_br(_cell(row, 2)),
                    parse_currency_br(_cell(row, 3)),
                    parse_currency_br(_cell(row, 4)),
                    parse_currency_br(_cell(row, 5)),
                    parse_currency_br(_cell(row, 6)),
                    parse_currency_br(_cell(row, 7)),
                    parse_currency_br(_cell(row, 8)),
                    "Controle mensal legado preservado apenas para conferência. Não reduz automaticamente o saldo do controle geral.",
                    excel_row_num,
                ),
            )
            stats["legacy_ata_rows"] += 1

        # Controle geral: cabeçalho na linha 9 do arquivo original.
        for row in ata_rows[9:]:
            name = _cell(row, 0)
            cnpj_raw = _cell(row, 1)
            if not name or not cnpj_raw:
                continue

            cnpj = normalize_cnpj(cnpj_raw)
            company = con.execute(
                "SELECT id FROM companies WHERE cnpj = ?",
                (cnpj,),
            ).fetchone()

            if company is None:
                # Preserva a informação mesmo se a empresa não estiver na aba principal.
                cur = con.execute(
                    "INSERT INTO companies(name, cnpj, legacy_status, active) VALUES (?, ?, ?, 1)",
                    (str(name).strip(), cnpj, "Criada pela migração da aba de atas"),
                )
                company_id = cur.lastrowid
                stats["companies"] += 1
            else:
                company_id = company["id"]

            con.execute(
                """
                INSERT INTO atas(
                    company_id, reference, original_value, opening_distributed,
                    classification, status, source_label, notes
                ) VALUES (?, ?, ?, ?, ?, 'Vigente', 'Controle Geral — planilha original',
                          'Importado da segunda aba. Valores do controle mensal legado não foram abatidos automaticamente.')
                """,
                (
                    company_id,
                    "Ata / saldo migrado 2025-2028",
                    parse_currency_br(_cell(row, 2)),
                    parse_currency_br(_cell(row, 3)),
                    _status_text(_cell(row, 5)),
                ),
            )
            stats["atas"] += 1

        # Classificação automática "sem documentação": roda só na carga inicial.
        stats["no_docs"] = classify_missing_documentation(con)

        con.execute(
            "INSERT INTO history(entity_type, action, detail) VALUES ('migration', 'Carga inicial', ?)",
            (f"Fonte: {source_path.name} | {stats}",),
        )

    return stats
