import altair as alt
import pandas as pd
import streamlit as st

from services.reinf_service import (
    WORKFLOW_STATUSES,
    active_operational_total,
    competence_counts,
    competence_total,
    excluded_total,
    monthly_progress,
    prepare_competence,
    previous_competence,
)
from services.ata_service import ata_alerts, ata_overview
from ui.helpers import competence_label, money_br
from ui.visuals import money_card, section_header

st.title("Dashboard")
st.caption("Visão executiva da carteira REINF / 12001.")

default_year, default_month = previous_competence()

c1, c2 = st.columns(2)
with c1:
    year = int(st.number_input("Ano", min_value=2025, max_value=2035, value=default_year, step=1))
with c2:
    month = st.selectbox(
        "Mês",
        list(range(1, 13)),
        index=default_month - 1,
        format_func=lambda x: f"{x:02d}",
    )

total = competence_total(year, month)
counts = competence_counts(year, month)
operational_companies = active_operational_total()
no_docs = excluded_total()

treated = (
    counts.get("Enviado", 0)
    + counts.get("Validado", 0)
    + counts.get("Não se aplica", 0)
)
progress = treated / total if total else 0

section_header(
    "Competência selecionada",
    competence_label(year, month),
    "Métricas operacionais desconsideram empresas classificadas como sem documentação.",
)

if total == 0:
    st.warning("Esta competência ainda não foi preparada.")
    if st.button("Preparar competência", type="primary"):
        created = prepare_competence(year, month)
        st.success(f"{created} registros criados.")
        st.rerun()

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Carteira operacional", operational_companies)
m2.metric("Na competência", total)
m3.metric("Tratadas", treated)
m4.metric("Conclusão", f"{progress:.0%}")
m5.metric("Sem documentação", no_docs)

st.progress(progress, text=f"{treated} de {total} empresas tratadas")

ref_year, ref_month = previous_competence()
ata_rows = [o for o in ata_overview() if o["status"] != "Encerrada"]
if ata_rows:
    ata_pending = ata_alerts(ref_year, ref_month)
    errors = sum(1 for a in ata_pending if a["level"] == "erro")
    warnings = sum(1 for a in ata_pending if a["level"] == "atenção")
    low = sum(1 for o in ata_rows if o["health"] in ("baixo", "negativo"))

    section_header("Atas de distribuição", "Situação dos saldos", f"Pendências calculadas até {ref_month:02d}/{ref_year}.")
    a1, a2, a3 = st.columns(3)
    with a1:
        money_card("Saldo disponível (atas ativas)", money_br(sum(o["balance"] or 0 for o in ata_rows)), f"{len(ata_rows)} ata(s)")
    with a2:
        money_card(
            "Pendências das atas",
            f"{errors} erro(s)",
            f"{warnings} aviso(s): meses sem lançamento, duplicidades, legado",
            tone="danger" if errors else "warn" if warnings else "ok",
        )
    with a3:
        money_card("Atas com saldo baixo ou negativo", str(low), "Abaixo de 10% do valor original", tone="warn" if low else "ok")
    st.page_link("views/atas.py", label="Abrir o controle das atas", icon=":material/account_balance_wallet:")

status_df = pd.DataFrame(
    [
        {"Status": status, "Empresas": counts.get(status, 0)}
        for status in WORKFLOW_STATUSES
    ]
)
status_df = status_df[status_df["Empresas"] > 0]

left, right = st.columns([1.55, 1])

with left:
    section_header(
        "Operação",
        "Distribuição da fila",
        "Quantidade de empresas em cada etapa da competência.",
    )
    if not status_df.empty:
        chart = (
            alt.Chart(status_df)
            .mark_bar(cornerRadiusEnd=6)
            .encode(
                x=alt.X("Empresas:Q", title=None),
                y=alt.Y("Status:N", sort="-x", title=None, axis=alt.Axis(labelLimit=220)),
                tooltip=["Status:N", "Empresas:Q"],
            )
            .properties(height=max(230, len(status_df) * 38))
        )
        st.altair_chart(chart, width="stretch")
    else:
        st.info("Ainda não há movimentação de status nesta competência.")

with right:
    section_header(
        "Carteira",
        "Base disponível",
        "Separação entre empresas operacionais e empresas sem documentação.",
    )
    composition = pd.DataFrame(
        {
            "Grupo": ["Operacional", "Sem documentação"],
            "Empresas": [operational_companies, no_docs],
        }
    )
    donut = (
        alt.Chart(composition)
        .mark_arc(innerRadius=58, outerRadius=92)
        .encode(
            theta=alt.Theta("Empresas:Q"),
            color=alt.Color("Grupo:N", legend=alt.Legend(title=None)),
            tooltip=["Grupo:N", "Empresas:Q"],
        )
        .properties(height=260)
    )
    st.altair_chart(donut, width="stretch")

section_header(
    "Histórico",
    "Evolução anual",
    "Comparação entre a carteira operacional de cada competência e a quantidade tratada.",
)

history = monthly_progress(year)
if history:
    history_df = pd.DataFrame(
        [
            {
                "Competência": f"{row['month']:02d}/{year}",
                "Total operacional": row["total"],
                "Tratadas": row["treated"] or 0,
            }
            for row in history
        ]
    )
    long_df = history_df.melt(
        id_vars="Competência",
        var_name="Série",
        value_name="Empresas",
    )
    line = (
        alt.Chart(long_df)
        .mark_line(point=True)
        .encode(
            x=alt.X("Competência:N", title=None),
            y=alt.Y("Empresas:Q", title="Empresas"),
            color=alt.Color("Série:N", legend=alt.Legend(title=None)),
            tooltip=["Competência:N", "Série:N", "Empresas:Q"],
        )
        .properties(height=290)
    )
    st.altair_chart(line, width="stretch")
else:
    st.info("Ainda não há histórico suficiente para o gráfico anual.")

c1, c2, c3 = st.columns(3)
c1.metric("Aguardando documentos", counts.get("Aguardando documentos", 0))
c2.metric("Em levantamento / revisão", counts.get("Em levantamento", 0) + counts.get("Revisar", 0))
c3.metric("Prontas para envio", counts.get("Pronto para envio", 0))

st.caption(
    "Empresas sem documentação permanecem salvas em área própria e podem ser reintegradas à operação a qualquer momento."
)
