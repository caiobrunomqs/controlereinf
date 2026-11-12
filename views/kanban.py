import streamlit as st

from services.reinf_service import kanban_rows, prepare_competence, previous_competence
from ui.helpers import cnpj_br, competence_label
from ui.visuals import badge

st.title("Kanban")
st.caption("Fila operacional da competência. Empresas sem documentação ficam fora deste quadro.")

default_year, default_month = previous_competence()
c1, c2 = st.columns(2)
with c1:
    year = int(st.number_input("Ano", min_value=2025, max_value=2035, value=default_year, step=1))
with c2:
    month = st.selectbox("Mês", range(1, 13), index=default_month - 1, format_func=lambda x: f"{x:02d}")

rows = kanban_rows(year, month)
if not rows:
    st.warning(f"Competência {competence_label(year, month)} ainda não possui base operacional preparada.")
    if st.button("Preparar agora", type="primary"):
        prepare_competence(year, month)
        st.rerun()
    st.stop()

search = st.text_input("Filtrar empresa")
if search:
    needle = search.lower()
    rows = [r for r in rows if needle in r["name"].lower() or needle in (r["cnpj"] or "")]

visible_statuses = [
    "Não iniciado",
    "Aguardando documentos",
    "Em levantamento",
    "Revisar",
    "Pronto para envio",
    "Enviado",
    "Validado",
    "Não se aplica",
]

# Texto + cor: a situação nunca depende só da cor.
DOC_TONE = {
    "Não informado": "neutral",
    "Não recebido": "danger",
    "Parcial": "warn",
    "Recebida": "ok",
    "Extratos disponíveis": "ok",
    "Informação do cliente": "info",
}

counts = {s: sum(1 for r in rows if r["workflow_status"] == s) for s in visible_statuses}
tabs = st.tabs([f"{s} ({counts[s]})" for s in visible_statuses])
for tab, status in zip(tabs, visible_statuses):
    with tab:
        subset = [r for r in rows if r["workflow_status"] == status]
        if not subset:
            st.info("Nenhuma empresa nesta etapa.")

        for row in subset:
            with st.container(border=True):
                top_left, top_right = st.columns([3, 1])
                top_left.markdown(f"#### {row['name']}")
                top_left.caption(cnpj_br(row["cnpj"]))
                top_right.markdown(f"**Responsável**  \n{row['responsible'] or '— não atribuído'}")
                a, b, c = st.columns(3)
                doc = row["documentation_status"]
                a.markdown(
                    f"**Documentos**  \n{badge(doc, DOC_TONE.get(doc, 'neutral'))}",
                    unsafe_allow_html=True,
                )
                b.markdown(f"**Apuração**  \n{row['assessment_status']}")
                c.markdown(f"**Obrigação**  \n{row['obligation_status']}")
                if row["notes"]:
                    st.caption(f"Obs.: {row['notes']}")
