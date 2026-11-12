"""Gera uma base de demonstração 100% fictícia.

Uso:
    python scripts/seed_demo.py            # cria data/reinf_control.db se não existir
    python scripts/seed_demo.py --reset    # apaga e recria
    python scripts/seed_demo.py --db outro.db

Nomes de empresas, sócios e responsáveis são inventados e os CNPJs são
gerados aleatoriamente (com dígito verificador válido). Qualquer semelhança
com empresas reais é coincidência.

A base foi montada para que cada tela tenha o que mostrar: competências de
2026 em todas as etapas do Kanban, atas com saldo confortável, baixo,
negativo e sem valor definido, meses sem lançamento, uma duplicidade
proposital (REINF + manual no mesmo mês), uma retirada sem ata vinculada e
uma linha do controle legado ainda não conciliada.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database.db import DB_PATH, init_db, transaction  # noqa: E402

SEED = 2026
YEAR = 2026
LAST_MONTH = 10  # competências preparadas: jan a out/2026

PREFIXES = [
    "Aroeira", "Bela Serra", "Cedro Azul", "Delta Campos", "Estrela do Cerrado",
    "Figueira Branca", "Horizonte Leste", "Ipê Roxo", "Jatobá", "Lagoa Funda",
    "Monte Verde Alto", "Nascente Clara", "Orvalho", "Pedra Lisa", "Quaresmeira",
    "Rio Sereno", "Serra do Vento", "Terra Firme", "Umbuzeiro", "Vereda Mansa",
    "Alvorada Norte", "Brisa do Lago", "Canto do Sabiá", "Duna Dourada", "Engenho Velho",
    "Flor do Campo", "Girassol", "Jardim das Pedras", "Lumiar", "Mirante do Sol",
    "Nova Aliança", "Oásis", "Pau-Brasil", "Ribeirão Fundo", "Sabiá-Laranjeira",
    "Taquaral", "Urupema", "Vale do Ipê", "Xingó", "Zênite",
]

ACTIVITIES = [
    "Comércio de Alimentos", "Serviços Médicos", "Engenharia", "Transportes",
    "Tecnologia da Informação", "Odontologia", "Representações Comerciais",
    "Consultoria Empresarial", "Arquitetura", "Distribuidora de Bebidas",
    "Materiais de Construção", "Clínica Veterinária", "Autopeças", "Educação",
    "Agropecuária", "Confecções", "Fisioterapia", "Laboratório de Análises",
]

FIRST_NAMES = [
    "Ana", "Bruno", "Carla", "Diego", "Elisa", "Fábio", "Gabriela", "Heitor",
    "Isabela", "João", "Larissa", "Marcelo", "Natália", "Otávio", "Paula",
    "Rafael", "Sílvia", "Tiago", "Vanessa", "Wagner",
]
LAST_NAMES = [
    "Almeida", "Barros", "Cardoso", "Duarte", "Esteves", "Fontes", "Guimarães",
    "Lacerda", "Macedo", "Nogueira", "Pacheco", "Queiroz", "Rezende", "Siqueira",
    "Teixeira", "Valadares",
]

RESPONSIBLES = ["Ana Lacerda", "Bruno Siqueira", "Carla Fontes"]
REGIMES = ["Lucro Presumido"] * 6 + ["Lucro Real"] * 3 + ["Simples Nacional"]
UFS = ["SP"] * 5 + ["MG"] * 3 + ["PR", "PR", "SC", "RJ", "GO", "BA"]
WITHDRAWAL_SOURCES = ["Extrato bancário", "Planilha do cliente", "Razão contábil"]

# Etapa do Kanban -> (documentação, apuração, obrigação)
WORKFLOW_DETAILS = {
    "Não iniciado": (["Não informado"], "Não iniciado", "Pendente"),
    "Aguardando documentos": (["Não recebido", "Parcial"], "Não iniciado", "Pendente"),
    "Em levantamento": (["Recebida", "Extratos disponíveis", "Informação do cliente"], "Em levantamento", "Pendente"),
    "Revisar": (["Recebida", "Parcial"], "Revisar", "Pendente"),
    "Pronto para envio": (["Recebida", "Extratos disponíveis"], "Concluído", "Pronto para envio"),
    "Enviado": (["Recebida", "Extratos disponíveis"], "Concluído", "Enviado"),
    "Validado": (["Recebida"], "Concluído", "Validado"),
    "Não se aplica": (["Informação do cliente"], "Não se aplica", "Não se aplica"),
}

CARD_NOTES = {
    "Aguardando documentos": ["Cobrar extratos de setembro e outubro.", "Cliente prometeu enviar até sexta."],
    "Revisar": ["Conferir retirada fora do padrão no extrato.", "Divergência entre razão e extrato."],
    "Em levantamento": ["Separar retiradas por sócio."],
}


# ---------------------------------------------------------------------------
# Geradores
# ---------------------------------------------------------------------------

def cnpj_check_digits(base12: str) -> str:
    """Dígitos verificadores do CNPJ (módulo 11)."""
    def digit(numbers: str) -> str:
        weights = list(range(len(numbers) - 7, 1, -1)) + list(range(9, 1, -1))
        total = sum(int(n) * w for n, w in zip(numbers, weights))
        rest = total % 11
        return "0" if rest < 2 else str(11 - rest)

    first = digit(base12)
    return first + digit(base12 + first)


def is_valid_cnpj(cnpj: str) -> bool:
    digits = "".join(ch for ch in cnpj if ch.isdigit())
    if len(digits) != 14 or len(set(digits)) == 1:
        return False
    return cnpj_check_digits(digits[:12]) == digits[12:]


def fake_cnpj(rng: random.Random, used: set[str]) -> str:
    while True:
        base = "".join(str(rng.randint(0, 9)) for _ in range(8)) + "0001"
        cnpj = base + cnpj_check_digits(base)
        if cnpj not in used and len(set(cnpj)) > 1:
            used.add(cnpj)
            return cnpj


def cents(rng: random.Random, base: float, spread: float = 0.2) -> float:
    """Valor em reais com centavos, variando em torno de `base`."""
    value = base * rng.uniform(1 - spread, 1 + spread)
    return round(int(value * 100) / 100, 2)


def partner_names(rng: random.Random, qty: int) -> list[str]:
    names = set()
    while len(names) < qty:
        names.add(f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}")
    return sorted(names)


# ---------------------------------------------------------------------------
# Carga
# ---------------------------------------------------------------------------

def _insert_companies(con, rng: random.Random) -> list[dict]:
    responsible_ids = [
        con.execute("INSERT INTO responsibles(name) VALUES (?)", (name,)).lastrowid
        for name in RESPONSIBLES
    ]

    used_cnpjs: set[str] = set()
    activities = ACTIVITIES[:]
    companies = []
    for i, prefix in enumerate(PREFIXES):
        activity = activities[i % len(activities)] if i < len(activities) else rng.choice(activities)
        suffix = "SLU" if i % 9 == 4 else "Ltda"
        name = f"{prefix} {activity} {suffix}"

        no_docs = i in (6, 13, 21, 29, 35)
        inactive = i in (17, 38)
        if inactive:
            status, observation = "Inativa", "Encerrou atividades em 2025."
        elif no_docs:
            status, observation = "Sem documentação", rng.choice([
                "Cliente não envia extratos desde 2025.",
                "Aguardando contrato de prestação de serviços.",
                "Sem documentos do exercício.",
            ])
        else:
            status, observation = "Ativa", ""

        start_year = rng.randint(2014, 2025)
        cur = con.execute(
            """
            INSERT INTO companies(
                legacy_code, name, cnpj, registration, tax_regime, uf,
                start_date, legacy_status, legacy_observation,
                default_responsible_id, active, metrics_excluded, exclusion_reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                1001 + i,
                name,
                fake_cnpj(rng, used_cnpjs),
                str(rng.randint(10_000_000, 99_999_999)),
                rng.choice(REGIMES),
                rng.choice(UFS),
                f"{start_year}-{rng.randint(1, 12):02d}-01",
                status,
                observation or None,
                rng.choice(responsible_ids),
                0 if inactive else 1,
                1 if no_docs else 0,
                "Sem documentação" if no_docs else None,
            ),
        )
        companies.append(
            {
                "id": cur.lastrowid,
                "name": name,
                "short": f"{prefix} {activity}",
                "active": not inactive,
                "operational": not inactive and not no_docs,
            }
        )
    return companies


def _insert_competencies(con, rng: random.Random, companies: list[dict]) -> None:
    current_mix = (
        ["Não iniciado"] * 4
        + ["Aguardando documentos"] * 6
        + ["Em levantamento"] * 5
        + ["Revisar"] * 3
        + ["Pronto para envio"] * 4
        + ["Enviado"] * 9
        + ["Validado"] * 5
        + ["Não se aplica"] * 2
    )
    for company in companies:
        if not company["active"]:
            continue
        resp = con.execute(
            "SELECT default_responsible_id FROM companies WHERE id = ?", (company["id"],)
        ).fetchone()[0]
        for month in range(1, LAST_MONTH + 1):
            if not company["operational"]:
                workflow = "Aguardando documentos"
            elif month <= LAST_MONTH - 2:
                workflow = rng.choices(["Validado", "Enviado", "Não se aplica"], [6, 3, 1])[0]
            elif month == LAST_MONTH - 1:
                workflow = rng.choices(["Enviado", "Validado", "Revisar", "Pronto para envio"], [6, 2, 1, 1])[0]
            else:
                workflow = rng.choice(current_mix)

            docs, assessment, obligation = WORKFLOW_DETAILS[workflow]
            note = None
            if month == LAST_MONTH and workflow in CARD_NOTES and rng.random() < 0.6:
                note = rng.choice(CARD_NOTES[workflow])
            con.execute(
                """
                INSERT INTO reinf_competencies(
                    company_id, year, month, workflow_status, documentation_status,
                    assessment_status, obligation_status, information_source,
                    responsible_id, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    company["id"], YEAR, month, workflow, rng.choice(docs),
                    assessment, obligation,
                    rng.choice(WITHDRAWAL_SOURCES) if workflow != "Não iniciado" else None,
                    resp, note,
                ),
            )


def _ata(con, company_id, reference, original, opening=0.0,
         classification="Valor definitivo identificado", status="Vigente", notes=None) -> int:
    return con.execute(
        """
        INSERT INTO atas(company_id, reference, original_value, opening_distributed,
                         classification, status, notes, source_label)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'Base de demonstração')
        """,
        (company_id, reference, original, opening, classification, status,
         notes or "Distribuição de lucros acumulados até 2025."),
    ).lastrowid


def _withdrawal(con, rng, company_id, month, partner, amount, ata_id, notes=None) -> None:
    con.execute(
        """
        INSERT INTO withdrawals(company_id, year, month, partner_name, amount,
                                source, ata_id, reviewed, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (company_id, YEAR, month, partner, amount, rng.choice(WITHDRAWAL_SOURCES),
         ata_id, 1 if rng.random() < 0.8 else 0, notes),
    )


def _manual(con, ata_id, month, amount, movement_type="Consumo", notes=None) -> None:
    con.execute(
        """
        INSERT INTO ata_manual_movements(ata_id, year, month, amount, movement_type, notes)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (ata_id, YEAR, month, amount, movement_type, notes),
    )


def _insert_atas(con, rng: random.Random, companies: list[dict]) -> dict:
    ops = [c for c in companies if c["operational"]]
    pick = rng.sample(ops, 9)
    months = range(1, LAST_MONTH + 1)
    ref_2025 = "Ata 19/12/2025"
    info = {}

    # 1. Saldo confortável, consumo por retiradas da REINF (dois sócios).
    c = pick[0]
    a1 = _ata(con, c["id"], ref_2025, 1_800_000.00,
              notes="Distribuição prevista em parcelas mensais até 2028.")
    for partner in partner_names(rng, 2):
        for m in months:
            _withdrawal(con, rng, c["id"], m, partner, cents(rng, 18_000), a1)
    # Ata anterior, já consumida e encerrada.
    _ata(con, c["id"], "Ata 28/04/2023", 400_000.00, 400_000.00,
         status="Encerrada", notes="Lucros de 2022, totalmente distribuídos em 2023 e 2024.")

    # 2. Lançamentos manuais (cliente informa por planilha) + uma retirada sem vínculo.
    c = pick[1]
    a2 = _ata(con, c["id"], ref_2025, 650_000.00)
    for m in months:
        _manual(con, a2, m, cents(rng, 21_000), notes="Planilha mensal do cliente")
    _withdrawal(con, rng, c["id"], LAST_MONTH, partner_names(rng, 1)[0], 7_350.00, None,
                notes="Identificada no extrato; confirmar se é distribuição.")

    # 3. Saldo baixo: grande parte já distribuída antes da implantação.
    c = pick[2]
    a3 = _ata(con, c["id"], ref_2025, 300_000.00, 180_000.00)
    partner = partner_names(rng, 1)[0]
    for m in months:
        _withdrawal(con, rng, c["id"], m, partner, cents(rng, 10_000, 0.05), a3)

    # 4. Saldo negativo: retiradas acima do aprovado.
    c = pick[3]
    a4 = _ata(con, c["id"], ref_2025, 240_000.00, 150_000.00,
              notes="Verificar se há ata complementar.")
    partner = partner_names(rng, 1)[0]
    for m in months:
        _withdrawal(con, rng, c["id"], m, partner, cents(rng, 9_800, 0.05), a4)

    # 5. Ata sem valor monetário definido.
    c = pick[4]
    a5 = _ata(con, c["id"], "Ata 30/12/2025", None,
              classification="Ata não define valor monetário definitivo",
              notes="Ata aprova a distribuição, mas não fixa o valor.")
    partner = partner_names(rng, 1)[0]
    for m in months:
        _withdrawal(con, rng, c["id"], m, partner, cents(rng, 6_500), a5)

    # 6. Valor provisório, com dois meses sem lançamento (lacuna).
    c = pick[5]
    a6 = _ata(con, c["id"], ref_2025, 900_000.00,
              classification="Valor provisório sujeito a ajuste",
              notes="Valor ajustável após o balanço de 2025.")
    for m in months:
        if m in (7, 8):
            continue
        _manual(con, a6, m, cents(rng, 30_000))

    # 7. Duplicidade proposital em junho: retirada da REINF + consumo manual.
    c = pick[6]
    a7 = _ata(con, c["id"], ref_2025, 500_000.00)
    partner = partner_names(rng, 1)[0]
    for m in months:
        _withdrawal(con, rng, c["id"], m, partner, cents(rng, 12_000), a7)
    _manual(con, a7, 6, 12_000.00, notes="Lançado a partir do e-mail do cliente")
    info["duplicate_ata_id"] = a7

    # 8. Implantada em junho: jan–mai ficaram no controle mensal legado.
    c = pick[7]
    a8 = _ata(con, c["id"], ref_2025, 420_000.00,
              notes="Jan a mai/2026 controlados na planilha antiga.")
    for m in range(6, LAST_MONTH + 1):
        _manual(con, a8, m, cents(rng, 15_000))
    legacy = [cents(rng, 15_000) for _ in range(5)]
    used = round(sum(legacy), 2)
    con.execute(
        """
        INSERT INTO legacy_ata_entries(raw_name, linked_company_id, initial_balance,
            jan, feb, mar, apr, may, total_used, remaining_balance, warning, source_row)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 2)
        """,
        (c["short"].upper(), c["id"], 420_000.00, *legacy, used, round(420_000.00 - used, 2),
         "Controle mensal legado preservado apenas para conferência. "
         "Não reduz automaticamente o saldo do controle geral."),
    )
    info["legacy_ata_id"] = a8

    # 9. Meses conferidos sem consumo + um estorno.
    c = pick[8]
    a9 = _ata(con, c["id"], ref_2025, 380_000.00)
    for m in months:
        if m in (3, 4):
            _manual(con, a9, m, 0.0, "Sem movimento", "Conferido no extrato, sem retiradas")
        else:
            _manual(con, a9, m, cents(rng, 14_000))
    _manual(con, a9, 9, 2_500.00, "Estorno", "Devolução de valor pago a maior")

    # Retiradas de uma empresa sem ata: aparecem na REINF, não afetam saldo.
    other = next(c for c in ops if c not in pick)
    for m in range(LAST_MONTH - 2, LAST_MONTH + 1):
        _withdrawal(con, rng, other["id"], m, partner_names(rng, 1)[0], cents(rng, 5_000), None)

    info["atas"] = 10
    return info


def build_demo_database(db_path: Path | str = DB_PATH, reset: bool = False) -> dict:
    """Cria a base demo em `db_path`. Recusa se já houver empresas cadastradas."""
    db_path = Path(db_path)
    if reset and db_path.exists():
        db_path.unlink()
    init_db(db_path)

    rng = random.Random(SEED)
    with transaction(db_path) as con:
        if con.execute("SELECT COUNT(*) FROM companies").fetchone()[0]:
            raise RuntimeError("O banco já possui empresas. Use --reset para recriar a base demo.")
        companies = _insert_companies(con, rng)
        _insert_competencies(con, rng, companies)
        info = _insert_atas(con, rng, companies)
        con.execute(
            "INSERT INTO history(entity_type, action, detail) VALUES ('demo', 'Base de demonstração', ?)",
            (f"{len(companies)} empresas fictícias | semente {SEED}",),
        )
    return {"companies": len(companies), **info}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", default=str(DB_PATH), help="Caminho do banco SQLite")
    parser.add_argument("--reset", action="store_true", help="Apaga o banco antes de gerar")
    args = parser.parse_args()
    result = build_demo_database(args.db, reset=args.reset)
    print(f"Base de demonstração criada em {args.db}: {result}")
