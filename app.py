import streamlit as st

from database.db import DB_PATH, init_db
from ui.visuals import apply_app_style

APP_NAME = "Controle REINF & Atas"
APP_VERSION = "0.5"

st.set_page_config(
    page_title=APP_NAME,
    page_icon=":material/fact_check:",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Primeiro uso (ex.: logo após clonar o repositório): cria uma base de
# demonstração com dados fictícios para o app abrir já preenchido.
if not DB_PATH.exists():
    from scripts.seed_demo import build_demo_database

    build_demo_database(DB_PATH)

init_db()
apply_app_style()

pages = {
    "Operação": [
        st.Page("views/dashboard.py", title="Dashboard", icon=":material/dashboard:"),
        st.Page("views/kanban.py", title="Kanban", icon=":material/view_kanban:"),
        st.Page("views/reinf.py", title="REINF / 12001", icon=":material/receipt_long:"),
        st.Page("views/sem_documentacao.py", title="Sem documentação", icon=":material/folder_off:"),
    ],
    "Cadastros e saldos": [
        st.Page("views/empresas.py", title="Empresas", icon=":material/domain:"),
        st.Page("views/atas.py", title="Controle das atas", icon=":material/account_balance_wallet:"),
        st.Page("views/responsaveis.py", title="Responsáveis", icon=":material/group:"),
    ],
    "Administração": [
        st.Page("views/migracao.py", title="Base de dados", icon=":material/database:"),
    ],
}

pg = st.navigation(pages)

with st.sidebar:
    st.caption(f"{APP_NAME} · v{APP_VERSION}")
    st.caption("Banco local SQLite · uso individual")

pg.run()
