import sqlite3
import streamlit as st

from services.company_service import add_responsible, list_responsibles, toggle_responsible

st.title("Responsáveis")
st.caption("Hoje o sistema pode ser usado por uma pessoa, mas a estrutura já permite atribuir demandas.")

with st.form("new_resp", clear_on_submit=True):
    name = st.text_input("Nome")
    add = st.form_submit_button("Adicionar responsável", type="primary")

if add:
    if not name.strip():
        st.error("Informe um nome.")
    else:
        try:
            add_responsible(name)
            st.success("Responsável adicionado.")
            st.rerun()
        except sqlite3.IntegrityError:
            st.error("Já existe um responsável com esse nome.")

rows = list_responsibles(active_only=False)
for row in rows:
    c1, c2, c3 = st.columns([4, 2, 2])
    c1.write(row["name"])
    c2.write("Ativo" if row["active"] else "Inativo")
    if c3.button("Desativar" if row["active"] else "Ativar", key=f"resp_{row['id']}"):
        toggle_responsible(row["id"], not bool(row["active"]))
        st.rerun()
