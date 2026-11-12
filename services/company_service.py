from __future__ import annotations

from database.db import fetch_all, fetch_one, transaction, log_history


def list_companies(
    search: str = "",
    active_only: bool = False,
    operational_only: bool = False,
    excluded_only: bool = False,
):
    where = []
    params = []

    if search.strip():
        conditions = ["LOWER(c.name) LIKE ?", "CAST(c.legacy_code AS TEXT) LIKE ?"]
        params.extend([f"%{search.strip().lower()}%", f"%{search.strip()}%"])

        # Só compara CNPJ quando o termo tem dígitos; senão "%%" casaria com tudo.
        digits = "".join(ch for ch in search if ch.isdigit())
        if digits:
            conditions.append("c.cnpj LIKE ?")
            params.append(f"%{digits}%")

        where.append("(" + " OR ".join(conditions) + ")")

    if active_only:
        where.append("c.active = 1")

    if operational_only:
        where.append("COALESCE(c.metrics_excluded, 0) = 0")

    if excluded_only:
        where.append("COALESCE(c.metrics_excluded, 0) = 1")

    clause = "WHERE " + " AND ".join(where) if where else ""

    return fetch_all(
        f"""
        SELECT c.*, r.name AS default_responsible
        FROM companies c
        LEFT JOIN responsibles r ON r.id = c.default_responsible_id
        {clause}
        ORDER BY c.name
        """,
        tuple(params),
    )


def get_company(company_id: int):
    return fetch_one(
        """
        SELECT c.*, r.name AS default_responsible
        FROM companies c
        LEFT JOIN responsibles r ON r.id = c.default_responsible_id
        WHERE c.id = ?
        """,
        (company_id,),
    )


def update_company(
    company_id: int,
    active: bool,
    default_responsible_id: int | None,
    legacy_status: str,
    legacy_observation: str,
    legacy_extra_note: str,
    metrics_excluded: bool,
    exclusion_reason: str,
):
    with transaction() as con:
        con.execute(
            """
            UPDATE companies
            SET active = ?,
                default_responsible_id = ?,
                legacy_status = ?,
                legacy_observation = ?,
                legacy_extra_note = ?,
                metrics_excluded = ?,
                exclusion_reason = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                int(bool(active)),
                default_responsible_id,
                legacy_status.strip() or None,
                legacy_observation.strip() or None,
                legacy_extra_note.strip() or None,
                int(bool(metrics_excluded)),
                exclusion_reason.strip() or None,
                company_id,
            ),
        )

    log_history(
        "company",
        company_id,
        "Atualização cadastral",
        f"Fora das métricas: {'sim' if metrics_excluded else 'não'}"
    )


def set_metrics_exclusion(company_id: int, excluded: bool, reason: str = ""):
    with transaction() as con:
        con.execute(
            """
            UPDATE companies
            SET metrics_excluded = ?,
                exclusion_reason = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (int(bool(excluded)), reason.strip() or None, company_id),
        )
    log_history(
        "company",
        company_id,
        "Classificação operacional",
        reason if excluded else "Reintegrada às métricas operacionais",
    )


def list_responsibles(active_only: bool = True):
    if active_only:
        return fetch_all("SELECT * FROM responsibles WHERE active = 1 ORDER BY name")
    return fetch_all("SELECT * FROM responsibles ORDER BY active DESC, name")


def add_responsible(name: str):
    with transaction() as con:
        cur = con.execute(
            "INSERT INTO responsibles(name) VALUES (?)",
            (name.strip(),),
        )
        rid = cur.lastrowid
    log_history("responsible", rid, "Inclusão", name.strip())
    return rid


def toggle_responsible(responsible_id: int, active: bool):
    with transaction() as con:
        con.execute(
            "UPDATE responsibles SET active = ? WHERE id = ?",
            (int(bool(active)), responsible_id),
        )
