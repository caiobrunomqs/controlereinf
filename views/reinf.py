import pandas as pd
import streamlit as st

from services.ata_service import HEALTH_LABELS, HEALTH_TONE, ata_health, list_atas, monthly_net
from services.company_service import list_companies, list_responsibles
from services.reinf_service import (
    ASSESSMENT_STATUSES,
    DOCUMENT_STATUSES,
    OBLIGATION_STATUSES,
    WORKFLOW_STATUSES,
    add_withdrawal,
    get_company_competence,
    list_withdrawals,
    previous_competence,
    update_company_competence,
)
from ui.dialogs import delete_entry_dialog, edit_entry_dialog
from ui.helpers import cnpj_br, md, money_br
from ui.visuals import money_card, tone_style, usage_meter

st.title("REINF / 12001")
st.caption("Controle por empresa + competência. Retiradas vinculadas a uma ata reduzem automaticamente o saldo dela no Controle das atas.")

companies = list_companies(active_only=True)
if not companies:
    st.warning("Nenhuma empresa ativa.")
    st.stop()

labels = {c["id"]: f"{c['name']} — {cnpj_br(c['cnpj'])}" for c in companies}
company_id = st.selectbox("Empresa", list(labels), format_func=lambda x: labels[x])

default_year, default_month = previous_competence()
c1, c2 = st.columns(2)
with c1:
    year = int(st.number_input("Ano", 2025, 2035, default_year))
with c2:
    month = st.selectbox("Mês", range(1, 13), index=default_month - 1, format_func=lambda x: f"{x:02d}")

# Apenas lê. O registro só é criado ao salvar (update_company_competence),
# para que abrir a tela não "prepare" a competência por acidente.
record = get_company_competence(company_id, year, month)
if record is None:
    st.info("Esta empresa ainda não tem registro nesta competência. Ele será criado ao salvar.")
    record = {
        "workflow_status": "Não iniciado",
        "documentation_status": "Não informado",
        "assessment_status": "Não iniciado",
        "obligation_status": "Pendente",
        "information_source": None,
        "responsible_id": None,
        "notes": None,
    }

responsibles = list_responsibles()
resp_ids = [None] + [r["id"] for r in responsibles]
resp_names = {None: "Não atribuído", **{r["id"]: r["name"] for r in responsibles}}
current_resp = record["responsible_id"] if record["responsible_id"] in resp_ids else None

def idx(options, value):
    return options.index(value) if value in options else 0

with st.form("reinf_status_form"):
    a, b = st.columns(2)
    with a:
        workflow = st.selectbox("Status do Kanban", WORKFLOW_STATUSES, idx(WORKFLOW_STATUSES, record["workflow_status"]))
        docs = st.selectbox("Documentação", DOCUMENT_STATUSES, idx(DOCUMENT_STATUSES, record["documentation_status"]))
        assessment = st.selectbox("Levantamento / apuração", ASSESSMENT_STATUSES, idx(ASSESSMENT_STATUSES, record["assessment_status"]))
    with b:
        obligation = st.selectbox("Obrigação", OBLIGATION_STATUSES, idx(OBLIGATION_STATUSES, record["obligation_status"]))
        source = st.text_input("Fonte da informação", value=record["information_source"] or "")
        responsible_id = st.selectbox(
            "Responsável",
            resp_ids,
            index=resp_ids.index(current_resp),
            format_func=lambda x: resp_names[x],
        )
    notes = st.text_area("Observações da competência", value=record["notes"] or "")
    save = st.form_submit_button("Salvar competência", type="primary")

if save:
    update_company_competence(
        company_id, year, month, workflow, docs, assessment,
        obligation, source, responsible_id, notes
    )
    st.success("Competência atualizada.")
    st.rerun()

st.divider()
st.subheader("Retiradas / distribuições identificadas")

atas = list_atas(company_id)
manual_this_month = {
    r["ata_id"]
    for r in monthly_net(year)
    if r["month"] == month and r["manual_consumption_count"]
}

if atas:
    st.caption("Saldo das atas desta empresa")
    cols = st.columns(min(len(atas), 3))
    for col, a in zip(cols * ((len(atas) // 3) + 1), atas):
        with col:
            health = ata_health(a)
            money_card(a["reference"], money_br(a["calculated_balance"]), HEALTH_LABELS[health], tone=HEALTH_TONE[health])
            if a["original_value"]:
                usage_meter(a["total_used"] / a["original_value"] * 100)
            if a["id"] in manual_this_month:
                st.warning(
                    f"Esta ata já tem consumo manual em {month:02d}/{year}. "
                    "Vincular retiradas aqui pode contar o mesmo valor duas vezes."
                )
else:
    st.caption("Esta empresa não tem ata cadastrada. As retiradas ficam registradas, mas não consomem saldo.")

UNLINKED = "Não vinculada"
withdrawals = list_withdrawals(company_id, year, month)
if withdrawals:
    df = pd.DataFrame(
        [
            {
                "Sócio / favorecido": w["partner_name"],
                "Valor": money_br(w["amount"]),
                "Fonte": w["source"] or "—",
                "Ata": w["ata_reference"] or UNLINKED,
                "Revisado": "Sim" if w["reviewed"] else "Não",
                "Observações": w["notes"] or "",
            }
            for w in withdrawals
        ]
    )
    st.caption("Selecione uma linha para editar ou excluir.")
    event = st.dataframe(
        df.style.map(lambda v: tone_style("warn") if v == UNLINKED else "", subset=["Ata"]),
        width="stretch",
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        key=f"withdrawals_{company_id}_{year}_{month}",
    )
    st.metric("Total da competência", money_br(sum(w["amount"] for w in withdrawals)))
    selected = event.selection.rows if event and event.selection else []
    if selected:
        w = withdrawals[selected[0]]
        entry = {
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
        }
        b1, b2, _ = st.columns([1, 1, 3])
        if b1.button("Editar retirada", icon=":material/edit:", width="stretch"):
            edit_entry_dialog(entry, company_id)
        if b2.button("Excluir retirada", icon=":material/delete:", width="stretch"):
            delete_entry_dialog(entry)
else:
    st.info("Nenhuma retirada registrada para esta competência.")

ata_options = [None] + [a["id"] for a in atas]
ata_names = {None: "Não vincular à ata (não afetará saldo)"}
for a in atas:
    ata_names[a["id"]] = f"{a['reference']} | saldo: {money_br(a['calculated_balance'])}"
balances = {a["id"]: a["calculated_balance"] for a in atas}

with st.expander("Adicionar retirada", expanded=not withdrawals):
    with st.form("withdrawal_form", clear_on_submit=True):
        partner = st.text_input("Sócio / favorecido")
        amount = st.number_input("Valor (R$)", min_value=0.0, step=100.0, format="%.2f")
        source_w = st.text_input("Fonte", placeholder="Extrato, planilha do cliente, contabilidade...")
        ata_id = st.selectbox(
            "Ata vinculada",
            ata_options,
            index=1 if len(atas) == 1 else 0,
            format_func=lambda x: ata_names[x],
        )
        reviewed = st.checkbox("Valor revisado")
        notes_w = st.text_area("Observações")
        allow_over = st.checkbox("Permitir mesmo que a retirada ultrapasse o saldo da ata")
        add = st.form_submit_button("Registrar retirada", type="primary")

    if add:
        balance = balances.get(ata_id)
        if not partner.strip() or amount <= 0:
            st.error("Informe o favorecido e um valor maior que zero.")
        elif ata_id is not None and balance is not None and amount > balance + 0.005 and not allow_over:
            st.error(md(
                f"A retirada de {money_br(amount)} é maior que o saldo disponível da ata ({money_br(balance)}). "
                "Confira o valor; se estiver correto, marque a permissão e registre de novo."
            ))
        else:
            try:
                add_withdrawal(
                    company_id, year, month, partner, amount,
                    source_w, ata_id, reviewed, notes_w
                )
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.toast("Retirada registrada.", icon=":material/check_circle:")
                st.rerun()
