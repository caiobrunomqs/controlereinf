import streamlit as st

from services.company_service import set_metrics_exclusion
from services.reinf_service import excluded_rows, previous_competence
from ui.helpers import cnpj_br
from ui.visuals import section_header

st.title("Sem documentação")
st.caption("Empresas preservadas na base, mas fora das métricas operacionais enquanto não houver documentação suficiente.")

default_year, default_month = previous_competence()
c1, c2 = st.columns(2)
with c1:
    year = int(st.number_input("Ano", 2025, 2035, default_year))
with c2:
    month = st.selectbox("Mês", range(1, 13), index=default_month - 1, format_func=lambda x: f"{x:02d}")

rows = excluded_rows(year, month)

m1, m2 = st.columns([1, 3])
m1.metric("Empresas", len(rows))
m2.info("Este grupo fica salvo e visível, mas não reduz o percentual de conclusão da carteira operacional.")

search = st.text_input("Pesquisar empresa")
if search:
    needle = search.lower()
    rows = [r for r in rows if needle in r["name"].lower() or needle in (r["cnpj"] or "")]

section_header(
    "Carteira preservada",
    "Empresas sem documentação",
    "Quando a documentação chegar, basta reintegrar a empresa à operação.",
)

if not rows:
    st.success("Nenhuma empresa classificada como sem documentação.")
    st.stop()

for row in rows:
    with st.expander(f"{row['name']} — {cnpj_br(row['cnpj'])}"):
        c1, c2 = st.columns([2, 1])
        with c1:
            st.write(f"**Motivo:** {row['exclusion_reason'] or 'Sem documentação'}")
            if row["legacy_status"]:
                st.write(f"**Situação:** {row['legacy_status']}")
            if row["legacy_observation"]:
                st.write(f"**Observação:** {row['legacy_observation']}")
            if row["legacy_extra_note"]:
                st.write(f"**Nota:** {row['legacy_extra_note']}")
        with c2:
            st.write(f"**Status da competência:** {row['workflow_status'] or 'Sem registro'}")
            st.write(f"**Documentação:** {row['documentation_status'] or 'Não informado'}")

        if st.button(
            "Reintegrar à operação",
            key=f"reintegrate_{row['company_id']}",
            type="primary",
        ):
            set_metrics_exclusion(row["company_id"], False, "")
            st.success("Empresa reintegrada.")
            st.rerun()
