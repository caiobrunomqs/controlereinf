import streamlit as st

from database.db import DB_PATH, fetch_all, fetch_one
from services.migration import DEFAULT_SOURCE

st.title("Base de dados")
st.caption("Diagnóstico do banco local e origem dos dados.")

st.write(f"**Banco:** `{DB_PATH}`")
demo = fetch_one("SELECT COUNT(*) qty FROM history WHERE entity_type = 'demo'")["qty"]
st.write(f"**Origem:** {'base de demonstração (dados fictícios)' if demo else 'carga própria'}")
st.write(
    f"**Planilha para importação:** `{DEFAULT_SOURCE}` "
    f"({'encontrada' if DEFAULT_SOURCE.exists() else 'não encontrada — opcional'})"
)

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Empresas", fetch_one("SELECT COUNT(*) qty FROM companies")["qty"])
m2.metric("Sem documentação", fetch_one(
    "SELECT COUNT(*) qty FROM companies WHERE active=1 AND COALESCE(metrics_excluded,0)=1"
)["qty"])
m3.metric("Atas", fetch_one("SELECT COUNT(*) qty FROM atas")["qty"])
m4.metric("Competências", fetch_one("SELECT COUNT(*) qty FROM reinf_competencies")["qty"])
m5.metric("Retiradas", fetch_one("SELECT COUNT(*) qty FROM withdrawals")["qty"])

st.subheader("Últimos eventos")
history = fetch_all("SELECT * FROM history ORDER BY id DESC LIMIT 30")
st.dataframe(
    [
        {
            "Data": h["created_at"],
            "Tipo": h["entity_type"],
            "Ação": h["action"],
            "Detalhe": h["detail"] or "",
        }
        for h in history
    ],
    width="stretch",
    hide_index=True,
)

st.warning(
    "Recriar o banco apaga as alterações feitas dentro do sistema. "
    "`python scripts/seed_demo.py --reset` recria a base de demonstração; "
    "`python scripts/rebuild_db.py <planilha.xlsx>` importa uma carteira a partir de planilha."
)
