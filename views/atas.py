
import pandas as pd
import streamlit as st

from services.ata_service import (
    ATA_CLASSIFICATIONS,
    ATA_STATUSES,
    HEALTH_LABELS,
    HEALTH_TONE,
    MANUAL_MOVEMENT_TYPES,
    MONTHS_PT,
    add_ata,
    add_manual_movement,
    ata_alerts,
    ata_overview,
    ata_statement,
    company_ata_summary,
    delete_ata,
    get_ata,
    import_legacy_entry,
    legacy_entries,
    list_atas,
    mark_legacy_reviewed,
    monthly_movements,
    monthly_net,
    period_label,
    update_ata,
)
from services.company_service import list_companies
from services.reinf_service import previous_competence
from ui.helpers import cnpj_br, md, money_br, money_short, months_label
from ui.dialogs import delete_entry_dialog, edit_entry_dialog
from ui.visuals import alert_list, money_card, section_header, tone_style, usage_meter

VIEWS = ["Visão geral", "Mapa mensal", "Extrato da ata", "Pendências", "Cadastrar ata"]
VIEW_ICONS = {
    "Visão geral": ":material/dashboard:",
    "Mapa mensal": ":material/calendar_month:",
    "Extrato da ata": ":material/receipt_long:",
    "Pendências": ":material/report:",
    "Cadastrar ata": ":material/add_circle:",
}
HEALTH_BY_LABEL = {label: HEALTH_TONE[key] for key, label in HEALTH_LABELS.items()}


def health_cell(value):
    return tone_style(HEALTH_BY_LABEL.get(value, ""))

ref_year, ref_month = previous_competence()

# Link direto para uma área: /atas?area=Pendências
if "atas_view" not in st.session_state and st.query_params.get("area") in VIEWS:
    st.session_state["atas_view"] = st.query_params["area"]
st.session_state.setdefault("atas_view", VIEWS[0])

# Redirecionamento pedido na execução anterior (ex.: após cadastrar uma ata).
if "_goto_ata" in st.session_state:
    st.session_state["atas_view"] = "Extrato da ata"
    st.session_state["extrato_ata"] = st.session_state.pop("_goto_ata")


def open_statement(ata_id: int):
    """Callback: troca para o extrato já com a ata escolhida."""
    st.session_state["atas_view"] = "Extrato da ata"
    st.session_state["extrato_ata"] = ata_id


def expected_months(year: int) -> int:
    """Quantos meses do ano já deveriam estar lançados."""
    if year < ref_year:
        return 12
    if year == ref_year:
        return ref_month
    return 0


# ---------------------------------------------------------------------------
# Dados comuns
# ---------------------------------------------------------------------------

overview = ata_overview()
alerts = ata_alerts(ref_year, ref_month)
n_errors = sum(1 for a in alerts if a["level"] == "erro")
n_warn = sum(1 for a in alerts if a["level"] == "atenção")

st.title("Controle das atas")
st.caption(
    f"Empresa › Ata › Valor original › Total utilizado › Saldo disponível. "
    f"Pendências calculadas até {ref_month:02d}/{ref_year}."
)

view = st.segmented_control(
    "Área",
    VIEWS,
    key="atas_view",
    format_func=lambda v: f"{VIEW_ICONS[v]} {v}"
    + (f" ({n_errors + n_warn})" if v == "Pendências" and (n_errors + n_warn) else ""),
    label_visibility="collapsed",
) or VIEWS[0]


# ---------------------------------------------------------------------------
# Diálogos de edição
# ---------------------------------------------------------------------------

@st.dialog("Editar ata", width="large")
def edit_ata_dialog(ata_id: int):
    ata = get_ata(ata_id)
    st.caption(ata["company_name"])
    with st.form("edit_ata_form"):
        reference = st.text_input("Referência", value=ata["reference"])
        c1, c2 = st.columns(2)
        with c1:
            original_value = st.number_input(
                "Valor original (R$)",
                min_value=0.0,
                value=None if ata["original_value"] is None else float(ata["original_value"]),
                step=1000.0,
                format="%.2f",
                placeholder="Sem valor definido",
            )
        with c2:
            opening = st.number_input(
                "Utilizado antes da implantação (R$)",
                min_value=0.0,
                value=float(ata["opening_distributed"] or 0),
                step=1000.0,
                format="%.2f",
            )
        c3, c4 = st.columns(2)
        with c3:
            classification = st.selectbox(
                "Classificação",
                ATA_CLASSIFICATIONS,
                index=ATA_CLASSIFICATIONS.index(ata["classification"])
                if ata["classification"] in ATA_CLASSIFICATIONS
                else len(ATA_CLASSIFICATIONS) - 1,
            )
        with c4:
            status = st.selectbox(
                "Status",
                ATA_STATUSES,
                index=ATA_STATUSES.index(ata["status"]) if ata["status"] in ATA_STATUSES else 0,
            )
        notes = st.text_area("Observações", value=ata["notes"] or "")
        saved = st.form_submit_button("Salvar ata", type="primary")

    if saved:
        try:
            update_ata(ata_id, reference, original_value, opening, classification, status, notes)
        except ValueError as exc:
            st.error(str(exc))
        else:
            st.rerun()

    with st.expander("Excluir ata"):
        st.caption("Só é possível excluir uma ata sem lançamentos. Com lançamentos, use o status Encerrada.")
        if st.button("Excluir definitivamente", key="delete_ata_btn"):
            try:
                delete_ata(ata_id)
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.rerun()


# ---------------------------------------------------------------------------
# 1. Visão geral
# ---------------------------------------------------------------------------

if view == "Visão geral":
    active = [o for o in overview if o["status"] != "Encerrada"]
    total_original = sum(o["original_value"] or 0 for o in active)
    total_used = sum(o["total_used"] or 0 for o in active)
    total_balance = sum(o["balance"] or 0 for o in active)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        money_card("Valor original (atas ativas)", money_br(total_original), f"{len(active)} ata(s)")
    with c2:
        pct = total_used / total_original * 100 if total_original else 0
        money_card("Total utilizado", money_br(total_used), f"{pct:.1f}% do valor original".replace(".", ","))
    with c3:
        money_card("Saldo disponível", money_br(total_balance), tone="ok" if total_balance >= 0 else "danger")
    with c4:
        money_card(
            "Pendências",
            f"{n_errors} erro(s)",
            f"{n_warn} aviso(s) · veja a área Pendências",
            tone="danger" if n_errors else "warn" if n_warn else "ok",
        )

    f1, f2 = st.columns([2, 2])
    with f1:
        search = st.text_input("Buscar empresa ou ata", placeholder="Digite parte do nome")
    with f2:
        health_filter = st.multiselect(
            "Situação",
            list(HEALTH_LABELS),
            format_func=lambda h: HEALTH_LABELS[h],
            placeholder="Todas",
        )

    rows = overview
    if search:
        needle = search.lower()
        rows = [o for o in rows if needle in o["company_name"].lower() or needle in o["reference"].lower()]
    if health_filter:
        rows = [o for o in rows if o["health"] in health_filter]

    if not rows:
        st.info("Nenhuma ata encontrada com esses filtros.")
    else:
        df = pd.DataFrame(
            [
                {
                    "Situação": HEALTH_LABELS[o["health"]],
                    "Empresa": o["company_name"],
                    "Ata": o["reference"],
                    "Valor original": money_br(o["original_value"]),
                    "Utilizado": money_br(o["total_used"]),
                    "Saldo disponível": money_br(o["balance"]),
                    "% utilizado": o["pct_used"],
                    "Último lançamento": period_label(o["last_period"]),
                    "Média por mês": money_br(o["avg_month"]) if o["months_recorded"] else "—",
                    "Saldo dura": months_label(o["months_left"]),
                }
                for o in rows
            ]
        )
        st.caption("Clique em uma linha para abrir o extrato da ata.")
        event = st.dataframe(
            df.style.map(health_cell, subset=["Situação"]),
            hide_index=True,
            width="stretch",
            on_select="rerun",
            selection_mode="single-row",
            key="overview_table",
            column_config={
                "% utilizado": st.column_config.ProgressColumn(
                    "% utilizado", min_value=0, max_value=100, format="%.0f%%"
                ),
                "Saldo dura": st.column_config.TextColumn(
                    "Saldo dura", help="Estimativa no ritmo médio dos meses lançados."
                ),
            },
        )
        selected = event.selection.rows if event and event.selection else []
        if selected:
            chosen = rows[selected[0]]
            st.button(
                f"Abrir extrato: {chosen['company_name']} · {chosen['reference']}",
                icon=":material/receipt_long:",
                type="primary",
                on_click=open_statement,
                args=(chosen["id"],),
            )

    with st.expander("Consolidado por empresa (soma de todas as atas)"):
        summary = company_ata_summary()
        st.dataframe(
            [
                {
                    "Empresa": r["company_name"],
                    "Atas": r["ata_count"],
                    "Valor original": money_br(r["original_value"]),
                    "Total utilizado": money_br(r["total_used"]),
                    "Saldo disponível": money_br(r["available_balance"]),
                }
                for r in summary
            ],
            hide_index=True,
            width="stretch",
        )


# ---------------------------------------------------------------------------
# 2. Mapa mensal
# ---------------------------------------------------------------------------

elif view == "Mapa mensal":
    c1, c2 = st.columns([1, 3])
    with c1:
        year = int(st.number_input("Ano", 2020, 2035, ref_year, key="map_year"))
    with c2:
        show_closed = st.checkbox("Incluir atas encerradas", value=False)

    due = expected_months(year)
    net_by_ata = {}
    for r in monthly_net(year):
        net_by_ata.setdefault(r["ata_id"], {})[r["month"]] = r

    MISSING, NO_MOVE = "falta", "sem consumo"
    grid = []
    for o in overview:
        if o["status"] == "Encerrada" and not show_closed:
            continue
        months = net_by_ata.get(o["id"], {})
        line = {"Empresa": o["company_name"], "Ata": o["reference"]}
        year_total = 0.0
        for m in range(1, 13):
            r = months.get(m)
            if r is None:
                line[MONTHS_PT[m - 1]] = MISSING if m <= due else ""
            elif r["entries"] == r["no_movement_count"]:
                line[MONTHS_PT[m - 1]] = NO_MOVE
            else:
                line[MONTHS_PT[m - 1]] = money_short(r["net"])
                year_total += r["net"]
        line[f"Total {year}"] = money_short(year_total)
        line["Saldo"] = money_short(o["balance"])
        grid.append(line)

    if not grid:
        st.info("Nenhuma ata para exibir.")
    else:
        df = pd.DataFrame(grid)
        missing_total = int((df[MONTHS_PT] == MISSING).sum().sum())

        k1, k2, k3 = st.columns(3)
        k1.metric("Atas no mapa", len(grid))
        k2.metric("Meses esperados por ata", due)
        k3.metric("Meses faltando", missing_total)

        def cell_style(value):
            if value == MISSING:
                return f"background-color: rgba(255,123,123,0.16); {tone_style('danger')}"
            if value == NO_MOVE:
                return tone_style("ok", bold=False)
            if value:
                return "color: #ffffff;"
            return ""

        styled = df.style.map(cell_style, subset=MONTHS_PT)
        st.dataframe(
            styled,
            hide_index=True,
            width="stretch",
            height=min(42 + 35 * len(grid), 640),
            column_config={
                "Empresa": st.column_config.TextColumn("Empresa", width=330, pinned=True),
                "Ata": st.column_config.TextColumn("Ata", width=125, pinned=True),
                **{m: st.column_config.TextColumn(m, width=92) for m in MONTHS_PT},
            },
        )
        st.caption(
            "**falta** = mês que já deveria estar lançado e não tem nenhum registro · "
            "**sem consumo** = mês conferido, sem retirada · valores em R$ (mil / mi)."
        )

        with st.expander("Marcar meses conferidos sem consumo", expanded=missing_total > 0):
            st.caption(
                "Use quando o mês foi verificado e não houve distribuição. "
                "Assim o mês deixa de aparecer como pendente."
            )
            open_atas = [o for o in overview if o["status"] != "Encerrada"]
            ata_label = {o["id"]: f"{o['company_name']} · {o['reference']}" for o in open_atas}
            with st.form("bulk_no_movement"):
                ata_id = st.selectbox("Ata", list(ata_label), format_func=lambda x: ata_label[x])
                months_sel = st.multiselect(
                    f"Meses de {year}",
                    list(range(1, 13)),
                    format_func=lambda m: MONTHS_PT[m - 1],
                )
                note = st.text_input("Observação (opcional)", placeholder="Ex.: conferido no extrato, sem retiradas")
                go = st.form_submit_button("Marcar como sem consumo", type="primary")
            if go:
                existing = net_by_ata.get(ata_id, {})
                clash = [MONTHS_PT[m - 1] for m in months_sel if m in existing]
                if not months_sel:
                    st.error("Selecione pelo menos um mês.")
                elif clash:
                    st.error(f"Estes meses já têm lançamento nesta ata: {', '.join(clash)}. Remova-os da seleção.")
                else:
                    for m in months_sel:
                        add_manual_movement(ata_id, year, m, 0, "Sem movimento", note)
                    st.success(f"{len(months_sel)} mês(es) marcado(s).")
                    st.rerun()

    section_header("Detalhe", "Lançamentos de um mês", "Todos os lançamentos de todas as atas na competência escolhida.")
    d1, d2 = st.columns([1, 3])
    with d1:
        detail_month = st.selectbox(
            "Mês",
            range(1, 13),
            index=(ref_month - 1) if year == ref_year else 0,
            format_func=lambda m: MONTHS_PT[m - 1],
            key="map_detail_month",
        )
    movs = monthly_movements(year, detail_month)
    if movs:
        total = 0.0
        table = []
        for m in movs:
            if m["movement_type"] == "Estorno":
                signed = -float(m["amount"])
            elif m["movement_type"] == "Sem movimento":
                signed = 0.0
            else:
                signed = float(m["amount"])
            total += signed
            table.append(
                {
                    "Empresa": m["company_name"],
                    "Ata": m["ata_reference"],
                    "Origem": m["origin"],
                    "Detalhe": m["detail"],
                    "Valor": money_br(signed),
                    "Observação": m["notes"] or "",
                }
            )
        with d2:
            money_card(f"Consumo líquido em {detail_month:02d}/{year}", money_br(total))
        st.dataframe(table, hide_index=True, width="stretch")
    else:
        st.info(f"Nenhum lançamento em {detail_month:02d}/{year}.")


# ---------------------------------------------------------------------------
# 3. Extrato da ata
# ---------------------------------------------------------------------------

elif view == "Extrato da ata":
    if not overview:
        st.info("Nenhuma ata cadastrada.")
        st.stop()

    ata_label = {
        o["id"]: f"{o['company_name']} · {o['reference']}"
        + (" (encerrada)" if o["status"] == "Encerrada" else "")
        for o in overview
    }
    if st.session_state.get("extrato_ata") not in ata_label:
        st.session_state["extrato_ata"] = next(iter(ata_label))
    ata_id = st.selectbox("Ata", list(ata_label), format_func=lambda x: ata_label[x], key="extrato_ata")
    o = next(x for x in overview if x["id"] == ata_id)
    ata = get_ata(ata_id)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        money_card("Valor original", money_br(o["original_value"]), ata["classification"] or "")
    with c2:
        money_card(
            "Total utilizado",
            money_br(o["total_used"]),
            f"Antes da implantação: {money_br(ata['opening_distributed'])}",
        )
    with c3:
        money_card("Saldo disponível", money_br(o["balance"]), HEALTH_LABELS[o["health"]], tone=HEALTH_TONE[o["health"]])
    with c4:
        money_card(
            "Ritmo médio por mês",
            money_br(o["avg_month"]) if o["months_recorded"] else "—",
            f"Saldo dura: {months_label(o['months_left'])}",
        )
    usage_meter(o["pct_used"])

    m1, m2 = st.columns([4, 1])
    with m1:
        st.markdown(
            f"**Status:** {ata['status']} · **Último lançamento:** {period_label(o['last_period'])} · "
            f"**Origem:** {ata['source_label'] or '—'}"
        )
        if ata["notes"]:
            st.caption(ata["notes"])
    with m2:
        if st.button("Editar ata", icon=":material/edit:", width="stretch"):
            edit_ata_dialog(ata_id)

    entries = ata_statement(ata_id)

    section_header("Lançar", "Novo lançamento manual", "Para retiradas de sócio, prefira registrar na tela REINF / 12001 vinculando a esta ata.")
    months_with_entries = {(e["year"], e["month"]) for e in entries}
    with st.form("new_manual_movement", clear_on_submit=True):
        f1, f2, f3, f4 = st.columns([1, 1, 1.2, 1.5])
        with f1:
            year = int(st.number_input("Ano", 2020, 2035, ref_year))
        with f2:
            month = st.selectbox("Mês", range(1, 13), index=ref_month - 1, format_func=lambda m: MONTHS_PT[m - 1])
        with f3:
            movement_type = st.selectbox(
                "Tipo",
                MANUAL_MOVEMENT_TYPES,
                help="Consumo reduz o saldo · Estorno devolve ao saldo · Sem movimento marca o mês como conferido.",
            )
        with f4:
            amount = st.number_input("Valor (R$)", min_value=0.0, step=100.0, format="%.2f")
        notes = st.text_input("Observação")
        confirm_dup = st.checkbox("Confirmo que é um lançamento adicional, mesmo que o mês já tenha outro")
        submitted = st.form_submit_button("Registrar lançamento", type="primary")

    if submitted:
        if (year, month) in months_with_entries and not confirm_dup:
            st.error(
                f"{MONTHS_PT[month - 1]}/{year} já tem lançamento nesta ata. Confira o extrato abaixo; "
                "se for mesmo um valor adicional, marque a confirmação e registre de novo."
            )
        else:
            try:
                add_manual_movement(ata_id, year, month, amount, movement_type, notes)
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.toast("Lançamento registrado.", icon=":material/check_circle:")
                st.rerun()

    section_header("Extrato", "Lançamentos da ata", "Do mais antigo para o mais recente, com o saldo após cada lançamento.")
    if not entries:
        st.info("Esta ata ainda não tem lançamentos.")
    else:
        df = pd.DataFrame(
            [
                {
                    "Competência": f"{e['month']:02d}/{e['year']}",
                    "Origem": e["origin"],
                    "Descrição": e["description"],
                    "Valor": money_br(e["signed"]),
                    "Saldo após": money_br(e["balance_after"]),
                    "Observação": e["notes"],
                }
                for e in entries
            ]
        )
        st.caption("Selecione uma linha para editar ou excluir.")
        event = st.dataframe(
            df,
            hide_index=True,
            width="stretch",
            on_select="rerun",
            selection_mode="single-row",
            key=f"statement_{ata_id}",
        )
        selected = event.selection.rows if event and event.selection else []
        if selected:
            entry = entries[selected[0]]
            b1, b2, _ = st.columns([1, 1, 3])
            if b1.button("Editar lançamento", icon=":material/edit:", width="stretch"):
                edit_entry_dialog(entry, ata["company_id"])
            if b2.button("Excluir lançamento", icon=":material/delete:", width="stretch"):
                delete_entry_dialog(entry)


# ---------------------------------------------------------------------------
# 4. Pendências
# ---------------------------------------------------------------------------

elif view == "Pendências":
    k1, k2, k3 = st.columns(3)
    with k1:
        money_card("Erros", str(n_errors), "Afetam o saldo: resolva primeiro", tone="danger" if n_errors else "ok")
    with k2:
        money_card("Avisos", str(n_warn), "Meses sem lançamento, saldo baixo, sem vínculo", tone="warn" if n_warn else "ok")
    with k3:
        n_info = len(alerts) - n_errors - n_warn
        money_card("Informativos", str(n_info), "Classificação do valor da ata", tone="info")

    levels = st.multiselect(
        "Mostrar",
        ["erro", "atenção", "info"],
        default=["erro", "atenção"],
        format_func=lambda x: {"erro": "Erros", "atenção": "Avisos", "info": "Informativos"}[x],
    )
    alert_list([a for a in alerts if a["level"] in levels], "Nenhuma pendência nos níveis selecionados.")

    if any(a["kind"] == "sem_vinculo" for a in alerts):
        st.page_link("views/reinf.py", label="Vincular retiradas na tela REINF / 12001", icon=":material/link:")

    section_header(
        "Conciliação",
        "Controle mensal legado (planilha)",
        "Valores mensais que estavam na planilha antiga. Importe para a ata correta para que reduzam o saldo, "
        "ou marque como conferido se já estiverem lançados.",
    )

    all_atas = list_atas()
    for item in legacy_entries():
        months_total = sum(float(item[k] or 0) for k in ("jan", "feb", "mar", "apr", "may"))
        title = item["company_name"] or item["raw_name"]
        done = bool(item["reconciled_at"])
        if done:
            badge, icon = ":green[Conciliado]", ":material/check_circle:"
        elif months_total > 0:
            badge, icon = ":red[Pendente]", ":material/error:"
        else:
            badge, icon = "Sem valores mensais", ":material/remove:"
        with st.expander(f"{title} — {badge}", icon=icon, expanded=not done and months_total > 0):
            st.dataframe(
                [
                    {
                        "Saldo inicial (planilha)": money_br(item["initial_balance"]),
                        **{
                            MONTHS_PT[i]: money_br(item[k])
                            for i, k in enumerate(("jan", "feb", "mar", "apr", "may"))
                        },
                        "Total utilizado": money_br(item["total_used"]),
                        "Saldo remanescente": money_br(item["remaining_balance"]),
                    }
                ],
                hide_index=True,
                width="stretch",
            )
            if done:
                target = item["reconciled_reference"] or "sem importação"
                st.success(f"Conciliado em {item['reconciled_at'][:10]} · {target}")
                continue

            candidates = [a for a in all_atas if a["company_id"] == item["linked_company_id"]] or all_atas
            cand_label = {a["id"]: f"{a['company_name']} · {a['reference']}" for a in candidates}
            for a in candidates:
                if item["initial_balance"] and a["original_value"] and abs(a["original_value"] - item["initial_balance"]) > 0.01:
                    st.warning(md(
                        f"O saldo inicial da planilha mensal ({money_br(item['initial_balance'])}) é diferente do "
                        f"valor original da ata \"{a['reference']}\" ({money_br(a['original_value'])}). "
                        "Confira se é a mesma ata antes de importar."
                    ))
            with st.form(f"legacy_{item['id']}"):
                c1, c2 = st.columns([3, 1])
                with c1:
                    target_ata = st.selectbox("Importar para a ata", list(cand_label), format_func=lambda x, labels=cand_label: labels[x])
                with c2:
                    legacy_year = int(st.number_input("Ano dos meses", 2020, 2035, 2026))
                go = st.form_submit_button(
                    md(f"Importar Jan–Mai como consumo ({money_br(months_total)})"),
                    type="primary",
                    disabled=months_total <= 0,
                )
            if go:
                try:
                    n = import_legacy_entry(item["id"], target_ata, legacy_year)
                except ValueError as exc:
                    st.error(str(exc))
                else:
                    st.toast(f"{n} mês(es) importado(s).", icon=":material/check_circle:")
                    st.rerun()
            if st.button("Marcar como conferido sem importar", key=f"legacy_ok_{item['id']}"):
                mark_legacy_reviewed(item["id"])
                st.rerun()


# ---------------------------------------------------------------------------
# 5. Cadastrar ata
# ---------------------------------------------------------------------------

elif view == "Cadastrar ata":
    st.caption("Cada empresa pode ter uma ou mais atas. O saldo é calculado por ata e consolidado por empresa.")
    all_companies = list_companies(active_only=False)
    company_names = {c["id"]: f"{c['name']} — {cnpj_br(c['cnpj'])}" for c in all_companies}

    with st.form("new_ata", clear_on_submit=True):
        company_id = st.selectbox("Empresa", list(company_names), format_func=lambda x: company_names[x])
        reference = st.text_input("Referência", placeholder="Ata 2025 / distribuição até 2028")
        c1, c2 = st.columns(2)
        with c1:
            original_value = st.number_input(
                "Valor original (R$)", min_value=0.0, value=None, step=1000.0, format="%.2f",
                placeholder="Deixe vazio se a ata não define valor",
            )
        with c2:
            opening_distributed = st.number_input(
                "Já utilizado antes da implantação (R$)",
                min_value=0.0,
                step=1000.0,
                format="%.2f",
                help="Valor consumido antes de começar a lançar neste sistema.",
            )
        c3, c4 = st.columns(2)
        with c3:
            classification = st.selectbox("Classificação", ATA_CLASSIFICATIONS)
        with c4:
            status = st.selectbox("Status", ATA_STATUSES)
        notes = st.text_area("Observações")
        save = st.form_submit_button("Cadastrar ata", type="primary")

    if save:
        if not reference.strip():
            st.error("Informe uma referência.")
        else:
            new_id = add_ata(company_id, reference, original_value, opening_distributed, classification, status, notes)
            st.toast("Ata cadastrada.", icon=":material/check_circle:")
            st.session_state["_goto_ata"] = new_id
            st.rerun()
