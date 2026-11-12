from __future__ import annotations

from collections import defaultdict
import sqlite3

from database.db import fetch_all, fetch_one, transaction
from services.formatting import format_brl


ATA_CLASSIFICATIONS = [
    "Valor definitivo identificado",
    "Valor provisório sujeito a ajuste",
    "Ata não define valor monetário definitivo",
    "A classificar",
]

ATA_STATUSES = ["Vigente", "Encerrada", "Revisar"]

# "Sem movimento" registra que o mês foi conferido e não houve consumo.
MANUAL_MOVEMENT_TYPES = ["Consumo", "Estorno", "Sem movimento"]

LOW_BALANCE_RATIO = 0.10

MONTHS_PT = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]

HEALTH_LABELS = {
    "negativo": "Saldo negativo",
    "baixo": "Saldo baixo",
    "sem_valor": "Sem valor definido",
    "encerrada": "Encerrada",
    "ok": "Com saldo",
}

# Tom visual de cada situação (ver ui/visuals.TONES). O rótulo em texto
# sempre acompanha a cor.
HEALTH_TONE = {
    "negativo": "danger",
    "baixo": "warn",
    "sem_valor": "info",
    "encerrada": "neutral",
    "ok": "ok",
}

LEVEL_ORDER = {"erro": 0, "atenção": 1, "info": 2}


def money(value) -> float:
    """Arredonda para centavos antes de gravar, evitando resíduos de float."""
    return round(float(value or 0), 2)


def period_label(period: int | None) -> str:
    if not period:
        return "—"
    return f"{period % 100:02d}/{period // 100}"


def _log(con: sqlite3.Connection, entity_type: str, entity_id, action: str, detail: str = "") -> None:
    # Grava o histórico na mesma transação da alteração.
    con.execute(
        "INSERT INTO history(entity_type, entity_id, action, detail) VALUES (?, ?, ?, ?)",
        (entity_type, entity_id, action, detail),
    )



# ---------------------------------------------------------------------------
# Consultas de saldo
# ---------------------------------------------------------------------------

def list_atas(company_id: int | None = None):
    if company_id is None:
        return fetch_all("SELECT * FROM ata_balances ORDER BY company_name, id DESC")
    return fetch_all(
        "SELECT * FROM ata_balances WHERE company_id = ? ORDER BY id DESC",
        (company_id,),
    )


def get_ata(ata_id: int):
    return fetch_one("SELECT * FROM ata_balances WHERE id = ?", (ata_id,))


def company_ata_summary():
    return fetch_all(
        """
        SELECT
            company_id,
            company_name,
            COUNT(id) AS ata_count,
            SUM(COALESCE(original_value, 0)) AS original_value,
            SUM(total_used) AS total_used,
            SUM(COALESCE(calculated_balance, 0)) AS available_balance
        FROM ata_balances
        GROUP BY company_id, company_name
        ORDER BY company_name
        """
    )


def ata_health(ata) -> str:
    if ata["status"] == "Encerrada":
        return "encerrada"
    original = ata["original_value"]
    if not original:
        return "sem_valor"
    balance = ata["calculated_balance"] or 0
    if balance < -0.005:
        return "negativo"
    if balance <= original * LOW_BALANCE_RATIO:
        return "baixo"
    return "ok"


def monthly_net(year: int | None = None):
    """Consumo líquido por ata e competência, com indicadores de origem."""
    where = "WHERE year = ?" if year is not None else ""
    params = (year,) if year is not None else ()
    return fetch_all(
        f"""
        SELECT ata_id, year, month,
               ROUND(SUM(net), 2) AS net,
               SUM(is_reinf) AS reinf_count,
               SUM(is_manual_consumption) AS manual_consumption_count,
               SUM(is_no_movement) AS no_movement_count,
               COUNT(*) AS entries
        FROM (
            SELECT ata_id, year, month, amount AS net,
                   1 AS is_reinf, 0 AS is_manual_consumption, 0 AS is_no_movement
            FROM withdrawals
            WHERE ata_id IS NOT NULL
            UNION ALL
            SELECT ata_id, year, month,
                   CASE
                       WHEN movement_type = 'Estorno' THEN -amount
                       WHEN movement_type = 'Sem movimento' THEN 0
                       ELSE amount
                   END,
                   0,
                   CASE WHEN movement_type = 'Consumo' THEN 1 ELSE 0 END,
                   CASE WHEN movement_type = 'Sem movimento' THEN 1 ELSE 0 END
            FROM ata_manual_movements
        )
        {where}
        GROUP BY ata_id, year, month
        ORDER BY ata_id, year, month
        """,
        params,
    )


def ata_overview():
    """Uma linha por ata com saldo, situação e ritmo de consumo."""
    atas = list_atas()
    by_ata = defaultdict(list)
    for row in monthly_net():
        by_ata[row["ata_id"]].append(row)

    result = []
    for a in atas:
        periods = by_ata.get(a["id"], [])
        consumed = sum(p["net"] for p in periods)
        avg_month = consumed / len(periods) if periods else 0.0
        balance = a["calculated_balance"]
        original = a["original_value"] or 0
        months_left = None
        if balance is not None and balance > 0 and avg_month > 0:
            months_left = balance / avg_month

        result.append(
            {
                "id": a["id"],
                "company_id": a["company_id"],
                "company_name": a["company_name"],
                "cnpj": a["cnpj"],
                "reference": a["reference"],
                "status": a["status"],
                "classification": a["classification"],
                "original_value": a["original_value"],
                "total_used": a["total_used"],
                "balance": balance,
                "pct_used": (a["total_used"] / original * 100) if original else None,
                "health": ata_health(a),
                "last_period": a["last_period"],
                "months_recorded": len(periods),
                "avg_month": avg_month,
                "months_left": months_left,
            }
        )
    return result


def ata_statement(ata_id: int) -> list[dict]:
    """Extrato da ata em ordem cronológica, com saldo após cada lançamento."""
    ata = get_ata(ata_id)
    if ata is None:
        return []

    entries = []
    for w in fetch_all(
        "SELECT * FROM withdrawals WHERE ata_id = ? ORDER BY year, month, id",
        (ata_id,),
    ):
        entries.append(
            {
                "kind": "reinf",
                "id": w["id"],
                "year": w["year"],
                "month": w["month"],
                "origin": "REINF / retirada",
                "movement_type": "Consumo",
                "description": w["partner_name"],
                "amount": float(w["amount"]),
                "signed": float(w["amount"]),
                "notes": w["notes"] or "",
                "created_at": w["created_at"],
            }
        )

    for m in fetch_all(
        "SELECT * FROM ata_manual_movements WHERE ata_id = ? ORDER BY year, month, id",
        (ata_id,),
    ):
        if m["movement_type"] == "Estorno":
            signed, description = -float(m["amount"]), "Estorno manual"
        elif m["movement_type"] == "Sem movimento":
            signed, description = 0.0, "Mês conferido sem consumo"
        else:
            signed, description = float(m["amount"]), "Consumo manual"
        entries.append(
            {
                "kind": "manual",
                "id": m["id"],
                "year": m["year"],
                "month": m["month"],
                "origin": "Manual",
                "movement_type": m["movement_type"],
                "description": description,
                "amount": float(m["amount"]),
                "signed": signed,
                "notes": m["notes"] or "",
                "created_at": m["created_at"],
            }
        )

    entries.sort(key=lambda e: (e["year"], e["month"], e["created_at"] or "", e["id"]))

    balance = float(ata["original_value"] or 0) - float(ata["opening_distributed"] or 0)
    for e in entries:
        balance -= e["signed"]
        e["balance_after"] = round(balance, 2)
    return entries


def monthly_movements(year: int, month: int, company_id: int | None = None):
    params = [year, month, year, month]
    company_filter_w = ""
    company_filter_m = ""

    if company_id is not None:
        company_filter_w = "AND w.company_id = ?"
        company_filter_m = "AND a.company_id = ?"
        params = [year, month, company_id, year, month, company_id]

    return fetch_all(
        f"""
        SELECT *
        FROM (
            SELECT
                w.id AS source_id,
                'REINF / retirada' AS origin,
                c.name AS company_name,
                c.id AS company_id,
                a.reference AS ata_reference,
                a.id AS ata_id,
                w.year AS year,
                w.month AS month,
                w.partner_name AS detail,
                w.amount AS amount,
                'Consumo' AS movement_type,
                w.source AS source,
                w.notes AS notes,
                w.created_at AS created_at
            FROM withdrawals w
            JOIN atas a ON a.id = w.ata_id
            JOIN companies c ON c.id = w.company_id
            WHERE w.year = ?
              AND w.month = ?
              {company_filter_w}

            UNION ALL

            SELECT
                m.id AS source_id,
                'Manual' AS origin,
                c.name AS company_name,
                c.id AS company_id,
                a.reference AS ata_reference,
                a.id AS ata_id,
                m.year AS year,
                m.month AS month,
                CASE
                    WHEN m.movement_type = 'Estorno' THEN 'Estorno manual'
                    WHEN m.movement_type = 'Sem movimento' THEN 'Mês conferido sem consumo'
                    ELSE 'Movimentação manual'
                END AS detail,
                m.amount AS amount,
                m.movement_type AS movement_type,
                'Ajuste/histórico' AS source,
                m.notes AS notes,
                m.created_at AS created_at
            FROM ata_manual_movements m
            JOIN atas a ON a.id = m.ata_id
            JOIN companies c ON c.id = a.company_id
            WHERE m.year = ?
              AND m.month = ?
              {company_filter_m}
        ) movimentos
        ORDER BY company_name, created_at
        """,
        tuple(params),
    )


# ---------------------------------------------------------------------------
# Pendências
# ---------------------------------------------------------------------------

def ata_alerts(year: int, upto_month: int) -> list[dict]:
    """Tudo o que precisa de atenção no controle das atas.

    upto_month: último mês do ano que já deveria estar lançado.
    """
    alerts = []

    def add(level, ata, message, kind):
        alerts.append(
            {
                "level": level,
                "kind": kind,
                "company_name": ata["company_name"] if ata else "",
                "ata_id": ata["id"] if ata else None,
                "ata_reference": ata["reference"] if ata else "",
                "message": message,
            }
        )

    net_rows = monthly_net(year)
    periods_by_ata = defaultdict(dict)
    for row in net_rows:
        periods_by_ata[row["ata_id"]][row["month"]] = row

    for a in list_atas():
        health = ata_health(a)
        if health == "encerrada":
            continue

        balance = a["calculated_balance"]
        if health == "negativo":
            add("erro", a, f"Saldo negativo: {format_brl(balance)}. Revise os lançamentos ou o valor original.", "saldo")
        elif health == "baixo":
            pct = balance / a["original_value"] * 100
            add("atenção", a, f"Saldo baixo: {format_brl(balance)} ({pct:.0f}% do valor original).", "saldo")
        elif health == "sem_valor":
            add("atenção", a, "Ata sem valor original. O saldo não pode ser calculado.", "cadastro")

        if a["classification"] in (
            "Valor provisório sujeito a ajuste",
            "Ata não define valor monetário definitivo",
            "A classificar",
        ):
            add("info", a, f"Classificação: {a['classification']}. Confirme o valor da ata.", "cadastro")

        months = periods_by_ata.get(a["id"], {})
        missing = [m for m in range(1, upto_month + 1) if m not in months]
        if missing:
            labels = ", ".join(MONTHS_PT[m - 1] for m in missing)
            add(
                "atenção",
                a,
                f"{len(missing)} mês(es) de {year} sem lançamento: {labels}. "
                "Lance o consumo ou marque \"Sem movimento\".",
                "lacuna",
            )

        for month, row in sorted(months.items()):
            if row["reinf_count"] and row["manual_consumption_count"]:
                add(
                    "erro",
                    a,
                    f"Possível duplicidade em {month:02d}/{year}: há retirada da REINF "
                    "e consumo manual no mesmo mês.",
                    "duplicidade",
                )
            if row["no_movement_count"] and row["entries"] > row["no_movement_count"]:
                add(
                    "atenção",
                    a,
                    f"{month:02d}/{year} está marcado como \"Sem movimento\", mas também tem lançamentos.",
                    "duplicidade",
                )

    unlinked = fetch_all(
        """
        SELECT w.company_id, c.name AS company_name, COUNT(*) AS qty,
               SUM(w.amount) AS total,
               GROUP_CONCAT(DISTINCT printf('%02d/%d', w.month, w.year)) AS periods
        FROM withdrawals w
        JOIN companies c ON c.id = w.company_id
        WHERE w.ata_id IS NULL
          AND EXISTS (SELECT 1 FROM atas a WHERE a.company_id = w.company_id AND a.status <> 'Encerrada')
        GROUP BY w.company_id, c.name
        """
    )
    for row in unlinked:
        alerts.append(
            {
                "level": "atenção",
                "kind": "sem_vinculo",
                "company_name": row["company_name"],
                "ata_id": None,
                "ata_reference": "",
                "message": (
                    f"{row['qty']} retirada(s) da REINF sem ata vinculada ({format_brl(row['total'])}) "
                    f"em {row['periods']}. Elas não reduzem nenhum saldo."
                ),
            }
        )

    for item in legacy_entries():
        if item["reconciled_at"]:
            continue
        months_total = sum(float(item[k] or 0) for k in ("jan", "feb", "mar", "apr", "may"))
        if months_total > 0:
            alerts.append(
                {
                    "level": "erro",
                    "kind": "legado",
                    "company_name": item["company_name"] or item["raw_name"],
                    "ata_id": None,
                    "ata_reference": "",
                    "message": (
                        f"Controle mensal legado com {format_brl(months_total)} consumidos (Jan–Mai) "
                        "que ainda não entraram no saldo de nenhuma ata. Concilie na aba Pendências."
                    ),
                }
            )

    alerts.sort(key=lambda x: (LEVEL_ORDER[x["level"]], x["company_name"]))
    return alerts


# ---------------------------------------------------------------------------
# Alterações
# ---------------------------------------------------------------------------

def _validate_movement(amount: float, movement_type: str) -> float:
    if movement_type not in MANUAL_MOVEMENT_TYPES:
        raise ValueError(f"Tipo inválido: {movement_type}")
    amount = money(amount)
    if movement_type == "Sem movimento":
        return 0.0
    if amount <= 0:
        raise ValueError("Informe um valor maior que zero.")
    return amount


def add_manual_movement(
    ata_id: int,
    year: int,
    month: int,
    amount: float,
    movement_type: str,
    notes: str,
):
    amount = _validate_movement(amount, movement_type)
    with transaction() as con:
        cur = con.execute(
            """
            INSERT INTO ata_manual_movements(
                ata_id, year, month, amount, movement_type, notes
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (ata_id, year, month, amount, movement_type, (notes or "").strip() or None),
        )
        movement_id = cur.lastrowid
        _log(
            con,
            "ata_manual_movement",
            movement_id,
            "Inclusão",
            f"Ata {ata_id} | {month:02d}/{year} | {movement_type} | {format_brl(amount)}",
        )
    return movement_id


def update_manual_movement(
    movement_id: int,
    year: int,
    month: int,
    amount: float,
    movement_type: str,
    notes: str,
):
    amount = _validate_movement(amount, movement_type)
    with transaction() as con:
        old = con.execute("SELECT * FROM ata_manual_movements WHERE id = ?", (movement_id,)).fetchone()
        if old is None:
            raise ValueError("Movimentação não encontrada.")
        con.execute(
            """
            UPDATE ata_manual_movements
            SET year = ?, month = ?, amount = ?, movement_type = ?, notes = ?
            WHERE id = ?
            """,
            (year, month, amount, movement_type, (notes or "").strip() or None, movement_id),
        )
        _log(
            con,
            "ata_manual_movement",
            movement_id,
            "Alteração",
            f"Ata {old['ata_id']} | de {old['month']:02d}/{old['year']} {old['movement_type']} {format_brl(old['amount'])} "
            f"para {month:02d}/{year} {movement_type} {format_brl(amount)}",
        )


def delete_manual_movement(movement_id: int):
    with transaction() as con:
        old = con.execute("SELECT * FROM ata_manual_movements WHERE id = ?", (movement_id,)).fetchone()
        if old is None:
            return
        con.execute("DELETE FROM ata_manual_movements WHERE id = ?", (movement_id,))
        _log(
            con,
            "ata_manual_movement",
            movement_id,
            "Exclusão",
            f"Ata {old['ata_id']} | {old['month']:02d}/{old['year']} | {old['movement_type']} | {format_brl(old['amount'])}",
        )


def add_ata(
    company_id: int,
    reference: str,
    original_value: float | None,
    opening_distributed: float,
    classification: str,
    status: str,
    notes: str,
):
    with transaction() as con:
        cur = con.execute(
            """
            INSERT INTO atas(
                company_id, reference, original_value, opening_distributed,
                classification, status, notes, source_label
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'Cadastro manual')
            """,
            (
                company_id,
                reference.strip(),
                None if original_value is None else money(original_value),
                money(opening_distributed),
                classification,
                status,
                (notes or "").strip() or None,
            ),
        )
        ata_id = cur.lastrowid
        _log(con, "ata", ata_id, "Inclusão", f"{reference.strip()} | {format_brl(original_value)}")
    return ata_id


def update_ata(
    ata_id: int,
    reference: str,
    original_value: float | None,
    opening_distributed: float,
    classification: str,
    status: str,
    notes: str,
):
    if not reference.strip():
        raise ValueError("Informe uma referência.")
    with transaction() as con:
        old = con.execute("SELECT * FROM atas WHERE id = ?", (ata_id,)).fetchone()
        if old is None:
            raise ValueError("Ata não encontrada.")
        new_values = {
            "reference": reference.strip(),
            "original_value": None if original_value is None else money(original_value),
            "opening_distributed": money(opening_distributed),
            "classification": classification,
            "status": status,
            "notes": (notes or "").strip() or None,
        }
        con.execute(
            """
            UPDATE atas
            SET reference = :reference,
                original_value = :original_value,
                opening_distributed = :opening_distributed,
                classification = :classification,
                status = :status,
                notes = :notes
            WHERE id = :id
            """,
            {**new_values, "id": ata_id},
        )
        changes = [
            f"{field}: {old[field]!r} → {value!r}"
            for field, value in new_values.items()
            if old[field] != value
        ]
        if changes:
            _log(con, "ata", ata_id, "Alteração", " | ".join(changes))


def delete_ata(ata_id: int):
    """Exclui somente atas sem nenhum lançamento; as demais devem ser encerradas."""
    with transaction() as con:
        used = con.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM withdrawals WHERE ata_id = ?)
              + (SELECT COUNT(*) FROM ata_manual_movements WHERE ata_id = ?)
            """,
            (ata_id, ata_id),
        ).fetchone()[0]
        if used:
            raise ValueError(
                "Esta ata possui lançamentos. Para preservar o histórico, altere o status para Encerrada."
            )
        old = con.execute("SELECT * FROM atas WHERE id = ?", (ata_id,)).fetchone()
        con.execute("DELETE FROM atas WHERE id = ?", (ata_id,))
        _log(con, "ata", ata_id, "Exclusão", old["reference"] if old else "")


# ---------------------------------------------------------------------------
# Controle mensal legado (planilha)
# ---------------------------------------------------------------------------

LEGACY_MONTH_FIELDS = [("jan", 1), ("feb", 2), ("mar", 3), ("apr", 4), ("may", 5)]


def legacy_entries():
    return fetch_all(
        """
        SELECT l.*, c.name AS company_name, a.reference AS reconciled_reference
        FROM legacy_ata_entries l
        LEFT JOIN companies c ON c.id = l.linked_company_id
        LEFT JOIN atas a ON a.id = l.reconciled_ata_id
        ORDER BY l.id
        """
    )


def import_legacy_entry(legacy_id: int, ata_id: int, year: int) -> int:
    """Transforma os meses do controle legado em movimentações manuais da ata.

    Recusa a importação se a ata já tiver lançamento em algum desses meses,
    para não contar o mesmo consumo duas vezes.
    """
    with transaction() as con:
        item = con.execute("SELECT * FROM legacy_ata_entries WHERE id = ?", (legacy_id,)).fetchone()
        if item is None:
            raise ValueError("Registro legado não encontrado.")
        if item["reconciled_at"]:
            raise ValueError("Este registro legado já foi conciliado.")

        to_import = [
            (month, money(item[field]))
            for field, month in LEGACY_MONTH_FIELDS
            if item[field] and float(item[field]) > 0
        ]

        months = [m for m, _ in to_import]
        if months:
            placeholders = ",".join("?" for _ in months)
            clash = con.execute(
                f"""
                SELECT DISTINCT month FROM (
                    SELECT month FROM ata_manual_movements
                    WHERE ata_id = ? AND year = ? AND month IN ({placeholders})
                    UNION ALL
                    SELECT month FROM withdrawals
                    WHERE ata_id = ? AND year = ? AND month IN ({placeholders})
                ) ORDER BY month
                """,
                (ata_id, year, *months, ata_id, year, *months),
            ).fetchall()
            if clash:
                labels = ", ".join(MONTHS_PT[r["month"] - 1] for r in clash)
                raise ValueError(
                    f"A ata já tem lançamentos em {labels}/{year}. "
                    "Revise o extrato antes de importar, para não duplicar consumo."
                )

        for month, amount in to_import:
            con.execute(
                """
                INSERT INTO ata_manual_movements(ata_id, year, month, amount, movement_type, notes)
                VALUES (?, ?, ?, ?, 'Consumo', ?)
                """,
                (ata_id, year, month, amount, f"Importado do controle mensal legado ({item['raw_name']})"),
            )

        con.execute(
            """
            UPDATE legacy_ata_entries
            SET reconciled_ata_id = ?, reconciled_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (ata_id, legacy_id),
        )
        _log(
            con,
            "legacy_ata_entry",
            legacy_id,
            "Conciliação",
            f"{item['raw_name']} → ata {ata_id}: {len(to_import)} mês(es) importado(s) em {year}",
        )
    return len(to_import)


def mark_legacy_reviewed(legacy_id: int):
    """Marca o registro legado como conferido sem importar valores."""
    with transaction() as con:
        con.execute(
            "UPDATE legacy_ata_entries SET reconciled_at = CURRENT_TIMESTAMP WHERE id = ?",
            (legacy_id,),
        )
        _log(con, "legacy_ata_entry", legacy_id, "Conferido", "Marcado como conferido sem importação")
