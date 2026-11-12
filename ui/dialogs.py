"""Diálogos compartilhados para editar e excluir lançamentos de atas."""
import streamlit as st

from services.ata_service import (
    MANUAL_MOVEMENT_TYPES,
    MONTHS_PT,
    delete_manual_movement,
    list_atas,
    update_manual_movement,
)
from services.reinf_service import delete_withdrawal, get_withdrawal, update_withdrawal
from ui.helpers import md, money_br


@st.dialog("Editar lançamento")
def edit_entry_dialog(entry: dict, company_id: int):
    if entry["kind"] == "manual":
        with st.form("edit_manual_form"):
            c1, c2 = st.columns(2)
            with c1:
                year = int(st.number_input("Ano", 2020, 2035, entry["year"]))
            with c2:
                month = st.selectbox(
                    "Mês", range(1, 13), index=entry["month"] - 1, format_func=lambda m: MONTHS_PT[m - 1]
                )
            movement_type = st.selectbox(
                "Tipo", MANUAL_MOVEMENT_TYPES, index=MANUAL_MOVEMENT_TYPES.index(entry["movement_type"])
            )
            amount = st.number_input("Valor (R$)", min_value=0.0, value=entry["amount"], step=100.0, format="%.2f")
            notes = st.text_area("Observação", value=entry["notes"])
            saved = st.form_submit_button("Salvar", type="primary")
        if saved:
            try:
                update_manual_movement(entry["id"], year, month, amount, movement_type, notes)
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.rerun()
    else:
        w = get_withdrawal(entry["id"])
        company_atas = list_atas(company_id)
        ata_options = [None] + [a["id"] for a in company_atas]
        ata_names = {None: "Não vincular (não afeta saldo)", **{a["id"]: a["reference"] for a in company_atas}}
        st.caption(f"Retirada registrada na REINF em {w['month']:02d}/{w['year']}.")
        with st.form("edit_withdrawal_form"):
            partner = st.text_input("Sócio / favorecido", value=w["partner_name"])
            amount = st.number_input("Valor (R$)", min_value=0.0, value=float(w["amount"]), step=100.0, format="%.2f")
            source = st.text_input("Fonte", value=w["source"] or "")
            ata_id = st.selectbox(
                "Ata vinculada",
                ata_options,
                index=ata_options.index(w["ata_id"]) if w["ata_id"] in ata_options else 0,
                format_func=lambda x: ata_names[x],
            )
            reviewed = st.checkbox("Valor revisado", value=bool(w["reviewed"]))
            notes = st.text_area("Observações", value=w["notes"] or "")
            saved = st.form_submit_button("Salvar", type="primary")
        if saved:
            try:
                update_withdrawal(entry["id"], partner, amount, source, ata_id, reviewed, notes)
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.rerun()


@st.dialog("Excluir lançamento")
def delete_entry_dialog(entry: dict):
    st.write(md(
        f"**{entry['month']:02d}/{entry['year']}** · {entry['origin']} · {entry['description']} · "
        f"**{money_br(entry['signed'])}**"
    ))
    if entry["kind"] == "reinf":
        st.warning("Esta retirada também será removida da tela REINF / 12001.")
    st.caption("A exclusão fica registrada no histórico.")
    c1, c2 = st.columns(2)
    if c1.button("Confirmar exclusão", type="primary", width="stretch"):
        if entry["kind"] == "manual":
            delete_manual_movement(entry["id"])
        else:
            delete_withdrawal(entry["id"])
        st.rerun()
    if c2.button("Cancelar", width="stretch"):
        st.rerun()
