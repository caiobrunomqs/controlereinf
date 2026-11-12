PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS responsibles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    legacy_code INTEGER,
    name TEXT NOT NULL,
    cnpj TEXT UNIQUE,
    registration TEXT,
    tax_regime TEXT,
    uf TEXT,
    start_date TEXT,
    start_raw TEXT,
    legacy_status TEXT,
    legacy_observation TEXT,
    legacy_extra_note TEXT,
    default_responsible_id INTEGER,
    active INTEGER NOT NULL DEFAULT 1,
    metrics_excluded INTEGER NOT NULL DEFAULT 0,
    exclusion_reason TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (default_responsible_id) REFERENCES responsibles(id)
);

CREATE TABLE IF NOT EXISTS reinf_competencies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL CHECK(month BETWEEN 1 AND 12),
    workflow_status TEXT NOT NULL DEFAULT 'Não iniciado',
    documentation_status TEXT NOT NULL DEFAULT 'Não informado',
    assessment_status TEXT NOT NULL DEFAULT 'Não iniciado',
    obligation_status TEXT NOT NULL DEFAULT 'Pendente',
    information_source TEXT,
    responsible_id INTEGER,
    notes TEXT,
    migrated_from_legacy INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(company_id, year, month),
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
    FOREIGN KEY (responsible_id) REFERENCES responsibles(id)
);

CREATE TABLE IF NOT EXISTS atas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    reference TEXT NOT NULL,
    original_value REAL,
    opening_distributed REAL NOT NULL DEFAULT 0,
    classification TEXT,
    status TEXT NOT NULL DEFAULT 'Vigente',
    notes TEXT,
    source_label TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS withdrawals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL CHECK(month BETWEEN 1 AND 12),
    partner_name TEXT NOT NULL,
    amount REAL NOT NULL CHECK(amount >= 0),
    source TEXT,
    ata_id INTEGER,
    reviewed INTEGER NOT NULL DEFAULT 0,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
    FOREIGN KEY (ata_id) REFERENCES atas(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS legacy_ata_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_name TEXT NOT NULL,
    linked_company_id INTEGER,
    initial_balance REAL,
    jan REAL,
    feb REAL,
    mar REAL,
    apr REAL,
    may REAL,
    total_used REAL,
    remaining_balance REAL,
    warning TEXT,
    source_row INTEGER,
    reconciled_ata_id INTEGER,
    reconciled_at TEXT,
    FOREIGN KEY (linked_company_id) REFERENCES companies(id) ON DELETE SET NULL,
    FOREIGN KEY (reconciled_ata_id) REFERENCES atas(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL,
    entity_id INTEGER,
    action TEXT NOT NULL,
    detail TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_reinf_competence
    ON reinf_competencies(year, month, workflow_status);

CREATE INDEX IF NOT EXISTS idx_withdrawals_competence
    ON withdrawals(company_id, year, month);

CREATE INDEX IF NOT EXISTS idx_atas_company
    ON atas(company_id);


CREATE TABLE IF NOT EXISTS ata_manual_movements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ata_id INTEGER NOT NULL,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL CHECK(month BETWEEN 1 AND 12),
    amount REAL NOT NULL CHECK(amount >= 0),
    movement_type TEXT NOT NULL DEFAULT 'Consumo',
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ata_id) REFERENCES atas(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_ata_manual_movements_competence
    ON ata_manual_movements(ata_id, year, month);

-- Saldo de cada ata: fonte única para todas as telas.
-- Recriada a cada inicialização para acompanhar mudanças de colunas.
DROP VIEW IF EXISTS ata_balances;
CREATE VIEW ata_balances AS
SELECT
    a.*,
    c.name AS company_name,
    c.cnpj AS cnpj,
    ROUND(COALESCE(w.linked_withdrawals, 0), 2) AS linked_withdrawals,
    ROUND(COALESCE(m.manual_net, 0), 2) AS manual_net,
    ROUND(
        COALESCE(a.opening_distributed, 0)
        + COALESCE(w.linked_withdrawals, 0)
        + COALESCE(m.manual_net, 0),
        2
    ) AS total_used,
    CASE
        WHEN a.original_value IS NULL THEN NULL
        ELSE ROUND(
            a.original_value
            - COALESCE(a.opening_distributed, 0)
            - COALESCE(w.linked_withdrawals, 0)
            - COALESCE(m.manual_net, 0),
            2
        )
    END AS calculated_balance,
    NULLIF(MAX(COALESCE(w.last_period, 0), COALESCE(m.last_period, 0)), 0) AS last_period
FROM atas a
JOIN companies c ON c.id = a.company_id
LEFT JOIN (
    SELECT ata_id,
           SUM(amount) AS linked_withdrawals,
           MAX(year * 100 + month) AS last_period
    FROM withdrawals
    WHERE ata_id IS NOT NULL
    GROUP BY ata_id
) w ON w.ata_id = a.id
LEFT JOIN (
    SELECT ata_id,
           SUM(CASE
                   WHEN movement_type = 'Estorno' THEN -amount
                   WHEN movement_type = 'Sem movimento' THEN 0
                   ELSE amount
               END) AS manual_net,
           MAX(year * 100 + month) AS last_period
    FROM ata_manual_movements
    GROUP BY ata_id
) m ON m.ata_id = a.id;
