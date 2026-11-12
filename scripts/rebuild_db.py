"""Reconstrói o banco a partir de uma planilha de carteira (.xlsx).

Uso:
    python scripts/rebuild_db.py caminho/para/planilha.xlsx

Sem argumento, procura data/input/clientes.xlsx. ATENÇÃO: apaga o banco atual.
O layout esperado das abas está descrito em services/migration.py e há um
exemplo fictício em tests/fixtures/carteira_ficticia.xlsx.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database.db import DB_PATH
from services.migration import DEFAULT_SOURCE, migrate_workbook

if __name__ == "__main__":
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SOURCE
    if not source.exists():
        sys.exit(f"Planilha não encontrada: {source}")
    print(f"Reconstruindo: {DB_PATH}")
    print(f"Fonte: {source}")
    stats = migrate_workbook(source, DB_PATH, reset=True)
    print("Concluído.")
    for key, value in stats.items():
        print(f"  {key}: {value}")
