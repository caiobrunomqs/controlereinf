from __future__ import annotations

from datetime import date

from database.db import fetch_all, fetch_one, transaction, log_history
from services.formatting import format_brl


WORKFLOW_STATUSES = [
    "Não iniciado",
    "Aguardando documentos",
    "Em levantamento",
    "Revisar",
    "Pronto para envio",
    "Enviado",
    "Validado",
    "Não se aplica",
]

DOCUMENT_STATUSES = [
    "Não informado",
    "Não recebido",
    "Parcial",
    "Recebida",
    "Extratos disponíveis",
    "Informação do cliente",
]

ASSESSMENT_STATUSES = [
    "Não iniciado",
    "Em levantamento",
    "Revisar",
    "Concluído",
    "Não se aplica",
]

OBLIGATION_STATUSES = [
    "Pendente",
    "Pronto para envio",
    "Enviado",
    "Validado",
    "Não se aplica",
]


def previous_competence(today: date | None = None):
    today = today or date.today()
    if today.month == 1:
        return today.year - 1, 12
    return today.year, today.month - 1


def prepare_competence(year: int, month: int) -> int:
    # Todos os ativos recebem registro de competência, inclusive os excluídos
    # das métricas. Assim, a empresa continua preservada e pode ser reintegrada
    # sem perda de histórico.
    with transaction() as con:
        before = con.total_changes
        con.execute(
            """
            INSERT OR IGNORE INTO reinf_competencies(company_id, year, month)
            SELECT id, ?, ?
            FROM companies
            WHERE active = 1
            """,
            (year, month),
        )
        created = con.total_changes - before

    log_history(
        "reinf_competence",
        None,
        "Preparar competência",
        f"{month:02d}/{year}: {created} registros criados",
    )
    return created


def competence_counts(year: int, month: int):
    rows = fetch_all(
        """
        SELECT rc.workflow_status, COUNT(*) AS qty
        FROM reinf_competencies rc
        JOIN companies c ON c.id = rc.company_id
        WHERE rc.year = ?
          AND rc.month = ?
          AND c.active = 1
          AND COALESCE(c.metrics_excluded, 0) = 0
        GROUP BY rc.workflow_status
        """,
        (year, month),
    )
    return {row["workflow_status"]: row["qty"] for row in rows}


def competence_total(year: int, month: int) -> int:
    row = fetch_one(
        """
        SELECT COUNT(*) AS qty
        FROM reinf_competencies rc
        JOIN companies c ON c.id = rc.company_id
        WHERE rc.year = ?
          AND rc.month = ?
          AND c.active = 1
          AND COALESCE(c.metrics_excluded, 0) = 0
        """,
        (year, month),
    )
    return int(row["qty"]) if row else 0


def excluded_total() -> int:
    row = fetch_one(
        """
        SELECT COUNT(*) AS qty
        FROM companies
        WHERE active = 1
          AND COALESCE(metrics_excluded, 0) = 1
        """
    )
    return int(row["qty"]) if row else 0


def active_operational_total() -> int:
    row = fetch_one(
        """
        SELECT COUNT(*) AS qty
        FROM companies
        WHERE active = 1
          AND COALESCE(metrics_excluded, 0) = 0
        """
    )
    return int(row["qty"]) if row else 0


def kanban_rows(year: int, month: int):
    return fetch_all(
        """
        SELECT
            rc.id, rc.workflow_status, rc.documentation_status,
            rc.assessment_status, rc.obligation_status, rc.notes,
            c.id AS company_id, c.name, c.cnpj,
            r.name AS responsible
        FROM reinf_competencies rc
        JOIN companies c ON c.id = rc.company_id
        LEFT JOIN responsibles r ON r.id = rc.responsible_id
        WHERE rc.year = ?
          AND rc.month = ?
          AND c.active = 1
          AND COALESCE(c.metrics_excluded, 0) = 0
        ORDER BY c.name
        """,
        (year, month),
    )


def excluded_rows(year: int | None = None, month: int | None = None):
    if year is not None and month is not None:
        return fetch_all(
            """
            SELECT
                c.id AS company_id, c.name, c.cnpj, c.exclusion_reason,
                c.legacy_status, c.legacy_observation, c.legacy_extra_note,
                rc.workflow_status, rc.documentation_status, rc.notes
            FROM companies c
            LEFT JOIN reinf_competencies rc
              ON rc.company_id = c.id AND rc.year = ? AND rc.month = ?
            WHERE c.active = 1
              AND COALESCE(c.metrics_excluded, 0) = 1
            ORDER BY c.name
            """,
            (year, month),
        )

    return fetch_all(
        """
        SELECT
            c.id AS company_id, c.name, c.cnpj, c.exclusion_reason,
            c.legacy_status, c.legacy_observation, c.legacy_extra_note
        FROM companies c
        WHERE c.active = 1
          AND COALESCE(c.metrics_excluded, 0) = 1
        ORDER BY c.name
        """
    )


def monthly_progress(year: int):
    return fetch_all(
        """
        SELECT
            rc.month,
            COUNT(*) AS total,
            SUM(CASE WHEN rc.workflow_status IN ('Enviado','Validado','Não se aplica')
                     THEN 1 ELSE 0 END) AS treated
        FROM reinf_competencies rc
        JOIN companies c ON c.id = rc.company_id
        WHERE rc.year = ?
          AND c.active = 1
          AND COALESCE(c.metrics_excluded, 0) = 0
        GROUP BY rc.month
        ORDER BY rc.month
        """,
        (year,),
    )


def get_company_competence(company_id: int, year: int, month: int):
    return fetch_one(
        """
        SELECT rc.*, r.name AS responsible_name
        FROM reinf_competencies rc
        LEFT JOIN responsibles r ON r.id = rc.responsible_id
        WHERE company_id = ? AND year = ? AND month = ?
        """,
        (company_id, year, month),
    )


def ensure_company_competence(company_id: int, year: int, month: int) -> None:
    with transaction() as con:
        con.execute(
            "INSERT OR IGNORE INTO reinf_competencies(company_id, year, month) VALUES (?, ?, ?)",
            (company_id, year, month),
        )


def update_company_competence(
    company_id: int,
    year: int,
    month: int,
    workflow_status: str,
    documentation_status: str,
    assessment_status: str,
    obligation_status: str,
    information_source: str,
    responsible_id: int | None,
    notes: str,
):
    ensure_company_competence(company_id, year, month)
    with transaction() as con:
        con.execute(
            """
            UPDATE reinf_competencies
            SET workflow_status = ?,
                documentation_status = ?,
                assessment_status = ?,
                obligation_status = ?,
                information_source = ?,
                responsible_id = ?,
                notes = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE company_id = ? AND year = ? AND month = ?
            """,
            (
                workflow_status,
                documentation_status,
                assessment_status,
                obligation_status,
                information_source.strip() or None,
                responsible_id,
                notes.strip() or None,
                company_id,
                year,
                month,
            ),
        )

    log_history(
        "reinf_competence",
        company_id,
        "Atualização",
        f"Competência {month:02d}/{year} → {workflow_status} / {obligation_status}",
    )


def list_withdrawals(company_id: int, year: int, month: int):
    return fetch_all(
        """
        SELECT w.*, a.reference AS ata_reference
        FROM withdrawals w
        LEFT JOIN atas a ON a.id = w.ata_id
        WHERE w.company_id = ? AND w.year = ? AND w.month = ?
        ORDER BY w.id DESC
        """,
        (company_id, year, month),
    )


def _check_ata_company(con, ata_id: int | None, company_id: int) -> None:
    if ata_id is None:
        return
    row = con.execute("SELECT company_id FROM atas WHERE id = ?", (ata_id,)).fetchone()
    if row is None or row["company_id"] != company_id:
        raise ValueError("A ata selecionada não pertence a esta empresa.")



def add_withdrawal(
    company_id: int,
    year: int,
    month: int,
    partner_name: str,
    amount: float,
    source: str,
    ata_id: int | None,
    reviewed: bool,
    notes: str,
):
    amount = round(float(amount), 2)
    if not partner_name.strip() or amount <= 0:
        raise ValueError("Informe o favorecido e um valor maior que zero.")
    with transaction() as con:
        _check_ata_company(con, ata_id, company_id)
        cur = con.execute(
            """
            INSERT INTO withdrawals(
                company_id, year, month, partner_name, amount,
                source, ata_id, reviewed, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                company_id,
                year,
                month,
                partner_name.strip(),
                amount,
                (source or "").strip() or None,
                ata_id,
                int(bool(reviewed)),
                (notes or "").strip() or None,
            ),
        )
        withdrawal_id = cur.lastrowid
        con.execute(
            "INSERT INTO history(entity_type, entity_id, action, detail) VALUES (?, ?, ?, ?)",
            (
                "withdrawal",
                withdrawal_id,
                "Inclusão",
                f"{month:02d}/{year} | {partner_name.strip()} | {format_brl(amount)} | ata {ata_id or '—'}",
            ),
        )
    return withdrawal_id


def get_withdrawal(withdrawal_id: int):
    return fetch_one("SELECT * FROM withdrawals WHERE id = ?", (withdrawal_id,))


def update_withdrawal(
    withdrawal_id: int,
    partner_name: str,
    amount: float,
    source: str,
    ata_id: int | None,
    reviewed: bool,
    notes: str,
):
    amount = round(float(amount), 2)
    if not partner_name.strip() or amount <= 0:
        raise ValueError("Informe o favorecido e um valor maior que zero.")
    with transaction() as con:
        old = con.execute("SELECT * FROM withdrawals WHERE id = ?", (withdrawal_id,)).fetchone()
        if old is None:
            raise ValueError("Retirada não encontrada.")
        _check_ata_company(con, ata_id, old["company_id"])
        con.execute(
            """
            UPDATE withdrawals
            SET partner_name = ?, amount = ?, source = ?, ata_id = ?, reviewed = ?, notes = ?
            WHERE id = ?
            """,
            (
                partner_name.strip(),
                amount,
                (source or "").strip() or None,
                ata_id,
                int(bool(reviewed)),
                (notes or "").strip() or None,
                withdrawal_id,
            ),
        )
        con.execute(
            "INSERT INTO history(entity_type, entity_id, action, detail) VALUES (?, ?, ?, ?)",
            (
                "withdrawal",
                withdrawal_id,
                "Alteração",
                f"{old['month']:02d}/{old['year']} | de {old['partner_name']} {format_brl(old['amount'])} ata {old['ata_id'] or '—'} "
                f"para {partner_name.strip()} {format_brl(amount)} ata {ata_id or '—'}",
            ),
        )


def delete_withdrawal(withdrawal_id: int):
    with transaction() as con:
        old = con.execute("SELECT * FROM withdrawals WHERE id = ?", (withdrawal_id,)).fetchone()
        if old is None:
            return
        con.execute("DELETE FROM withdrawals WHERE id = ?", (withdrawal_id,))
        con.execute(
            "INSERT INTO history(entity_type, entity_id, action, detail) VALUES (?, ?, ?, ?)",
            (
                "withdrawal",
                withdrawal_id,
                "Exclusão",
                f"{old['month']:02d}/{old['year']} | {old['partner_name']} | {format_brl(old['amount'])} | ata {old['ata_id'] or '—'}",
            ),
        )
