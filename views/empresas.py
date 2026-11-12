import streamlit as st

from services.company_service import (
    get_company,
    list_companies,
    list_responsibles,
    update_company,
)
from ui.helpers import cnpj_br

st.title("Empresas")

search = st.text_input("Pesquisar por nome, CNPJ ou código legado")
active_only = st.checkbox("Somente ativas", value=True)
companies = list_companies(search=search, active_only=active_only)

st.caption(f"{len(companies)} empresa(s) encontrada(s).")
if not companies:
    st.stop()

labels = {c["id"]: f"{c['name']} — {cnpj_br(c['cnpj'])}" for c in companies}
company_id = st.selectbox("Selecione", list(labels), format_func=lambda x: labels[x])
company = get_company(company_id)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Código legado", company["legacy_code"] or "—")
c2.metric("Regime", company["tax_regime"] or "—")
c3.metric("UF", company["uf"] or "—")
c4.metric(
    "Grupo",
    "Sem documentação" if company["metrics_excluded"] else "Operacional"
)

st.write(f"**CNPJ:** {cnpj_br(company['cnpj'])}")
st.write(f"**IM/IE:** {company['registration'] or '—'}")
st.write(f"**Cliente desde:** {company['start_date'] or company['start_raw'] or '—'}")

responsibles = list_responsibles()
responsible_options = [None] + [r["id"] for r in responsibles]
responsible_names = {None: "Não atribuído", **{r["id"]: r["name"] for r in responsibles}}
current_resp = company["default_responsible_id"] if company["default_responsible_id"] in responsible_options else None

with st.form("company_form"):
    active = st.checkbox("Empresa ativa", value=bool(company["active"]))
    responsible_id = st.selectbox(
        "Responsável padrão",
        responsible_options,
        index=responsible_options.index(current_resp),
        format_func=lambda x: responsible_names[x],
    )

    st.markdown("#### Classificação operacional")
    metrics_excluded = st.checkbox(
        "Sem documentação — excluir das métricas principais",
        value=bool(company["metrics_excluded"]),
    )
    exclusion_reason = st.text_input(
        "Motivo da exclusão",
        value=company["exclusion_reason"] or ("Sem documentação" if metrics_excluded else ""),
    )

    st.markdown("#### Informações legadas")
    legacy_status = st.text_input("Situação / informação legada", value=company["legacy_status"] or "")
    legacy_observation = st.text_area("Observação legada", value=company["legacy_observation"] or "")
    legacy_extra = st.text_area("Nota adicional da planilha", value=company["legacy_extra_note"] or "")

    submitted = st.form_submit_button("Salvar alterações", type="primary")

if submitted:
    update_company(
        company_id,
        active,
        responsible_id,
        legacy_status,
        legacy_observation,
        legacy_extra,
        metrics_excluded,
        exclusion_reason,
    )
    st.success("Empresa atualizada.")
    st.rerun()
