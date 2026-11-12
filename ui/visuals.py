from __future__ import annotations

from html import escape as _html_escape

import streamlit as st

# Cores com contraste alto sobre o fundo escuro (todas acima de 4.5:1).
TONES = {
    "danger": "#ff7b7b",
    "warn": "#ffc163",
    "ok": "#5fe0a0",
    "info": "#7cc4ff",
    "neutral": "rgba(255,255,255,0.80)",
}

LEVEL_TONE = {"erro": "danger", "atenção": "warn", "info": "info"}


def escape(text) -> str:
    """Escapa HTML e troca "$" por entidade: com dois "R$" no mesmo bloco,
    o markdown do Streamlit interpretaria o trecho como fórmula."""
    return _html_escape(str(text)).replace("$", "&#36;")


LEVEL_LABEL = {"erro": "Erro", "atenção": "Atenção", "info": "Info"}


def tone_style(tone: str, bold: bool = True) -> str:
    """CSS para células de tabela (pandas Styler): cor do texto pelo tom."""
    color = TONES.get(tone)
    if not color:
        return ""
    return f"color: {color};" + (" font-weight: 600;" if bold else "")


def badge(text: str, tone: str = "neutral") -> str:
    """Texto colorido em HTML. A cor sempre acompanha o texto, nunca o substitui."""
    color = TONES.get(tone, TONES["neutral"])
    return f'<span style="color:{color}; font-weight:600;">{escape(text)}</span>'


def apply_app_style():
    st.markdown(
        """
        <style>
        :root {
            --card-bg: rgba(255,255,255,0.045);
            --card-border: rgba(255,255,255,0.14);
            --muted: rgba(255,255,255,0.78);
            --tone-danger: #ff7b7b;
            --tone-warn: #ffc163;
            --tone-ok: #5fe0a0;
            --tone-info: #7cc4ff;
        }

        .block-container {
            padding-top: 1.4rem;
            padding-bottom: 2rem;
            max-width: 1500px;
        }

        [data-testid="stSidebar"] {
            border-right: 1px solid rgba(255,255,255,0.10);
        }

        div[data-testid="stMetric"] {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            padding: 14px 16px;
            border-radius: 14px;
        }

        div[data-testid="stMetric"] label,
        div[data-testid="stMetric"] label p {
            color: var(--muted);
            font-size: .95rem;
        }

        div[data-testid="stMetricValue"] {
            font-weight: 700;
        }

        div[data-testid="stExpander"] {
            border: 1px solid var(--card-border);
            border-radius: 12px;
            background: rgba(255,255,255,0.02);
        }

        /* Abas maiores e mais fáceis de clicar */
        button[data-baseweb="tab"] p {
            font-size: 1rem;
            font-weight: 600;
        }

        /* Legendas do Streamlit com mais contraste */
        [data-testid="stCaptionContainer"], .stCaption {
            color: var(--muted) !important;
        }

        .reinf-section {
            border: 1px solid var(--card-border);
            border-radius: 16px;
            padding: 1rem 1.1rem;
            background: rgba(255,255,255,0.03);
            margin: .4rem 0 1rem 0;
        }

        .reinf-kicker {
            color: var(--muted);
            font-size: .85rem;
            text-transform: uppercase;
            letter-spacing: .08em;
            margin-bottom: .2rem;
        }

        .reinf-title {
            font-size: 1.25rem;
            font-weight: 700;
            margin-bottom: .15rem;
        }

        .reinf-muted {
            color: var(--muted);
            font-size: .95rem;
        }

        .money-card {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-left: 5px solid var(--card-border);
            border-radius: 16px;
            padding: 15px 17px 14px 17px;
            min-height: 105px;
            display: flex;
            flex-direction: column;
            justify-content: center;
            overflow: hidden;
            margin-bottom: .6rem;
            container-type: inline-size;
        }

        .money-card.tone-danger { border-left-color: var(--tone-danger); }
        .money-card.tone-warn   { border-left-color: var(--tone-warn); }
        .money-card.tone-ok     { border-left-color: var(--tone-ok); }
        .money-card.tone-info   { border-left-color: var(--tone-info); }

        .money-card-label {
            color: var(--muted);
            font-size: .92rem;
            line-height: 1.25rem;
            margin-bottom: .35rem;
        }

        .money-card-value {
            /* A fonte acompanha a largura do card: o valor inteiro cabe em uma linha. */
            font-size: clamp(0.72rem, 8.6cqi, 1.7rem);
            line-height: 1.2;
            font-weight: 760;
            letter-spacing: -0.01em;
            white-space: nowrap;
        }

        .money-card-helper {
            color: var(--muted);
            font-size: .85rem;
            margin-top: .35rem;
        }

        .reinf-alert {
            border: 1px solid var(--card-border);
            border-left: 5px solid var(--card-border);
            border-radius: 12px;
            padding: .65rem .9rem;
            margin-bottom: .5rem;
            background: rgba(255,255,255,0.03);
            font-size: .98rem;
            line-height: 1.4;
        }
        .reinf-alert.tone-danger { border-left-color: var(--tone-danger); }
        .reinf-alert.tone-warn   { border-left-color: var(--tone-warn); }
        .reinf-alert.tone-info   { border-left-color: var(--tone-info); }
        .reinf-alert-head {
            font-weight: 700;
            margin-bottom: .1rem;
        }
        .reinf-alert-tag {
            display: inline-block;
            font-size: .78rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: .05em;
            margin-right: .5rem;
        }
        .reinf-alert.tone-danger .reinf-alert-tag { color: var(--tone-danger); }
        .reinf-alert.tone-warn .reinf-alert-tag   { color: var(--tone-warn); }
        .reinf-alert.tone-info .reinf-alert-tag   { color: var(--tone-info); }

        .reinf-meter {
            height: 12px;
            border-radius: 999px;
            background: rgba(255,255,255,0.10);
            overflow: hidden;
            margin: .5rem 0 .25rem 0;
        }
        .reinf-meter > span {
            display: block;
            height: 100%;
            border-radius: 999px;
        }

        hr {
            border-color: rgba(255,255,255,0.10) !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def section_header(kicker: str, title: str, subtitle: str = ""):
    subtitle_html = f'<div class="reinf-muted">{escape(subtitle)}</div>' if subtitle else ""
    st.markdown(
        f"""
        <div class="reinf-section">
            <div class="reinf-kicker">{escape(kicker)}</div>
            <div class="reinf-title">{escape(title)}</div>
            {subtitle_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def money_card(label: str, value: str, helper: str = "", tone: str = ""):
    helper_html = f'<div class="money-card-helper">{escape(helper)}</div>' if helper else ""
    tone_class = f" tone-{tone}" if tone in TONES else ""
    st.markdown(
        f"""
        <div class="money-card{tone_class}">
            <div class="money-card-label">{escape(label)}</div>
            <div class="money-card-value">{escape(value)}</div>
            {helper_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def usage_meter(pct_used: float | None, label: str = ""):
    """Barra de consumo: verde até 75%, amarela até 90%, vermelha acima."""
    if pct_used is None:
        return
    pct = max(0.0, min(pct_used, 100.0))
    tone = "ok" if pct_used < 75 else "warn" if pct_used < 90 else "danger"
    text = label or f"{pct_used:.1f}% do valor original utilizado".replace(".", ",")
    st.markdown(
        f"""
        <div class="reinf-meter" role="progressbar" aria-valuenow="{pct:.0f}"
             aria-valuemin="0" aria-valuemax="100" aria-label="{escape(text)}">
            <span style="width:{pct:.1f}%; background:{TONES[tone]};"></span>
        </div>
        <div class="reinf-muted">{escape(text)}</div>
        """,
        unsafe_allow_html=True,
    )


def alert_list(alerts: list[dict], empty_text: str = "Nenhuma pendência."):
    if not alerts:
        st.success(empty_text)
        return
    for a in alerts:
        tone = LEVEL_TONE[a["level"]]
        head = escape(a["company_name"] or "")
        if a.get("ata_reference"):
            head += f' <span class="reinf-muted">· {escape(a["ata_reference"])}</span>'
        st.markdown(
            f"""
            <div class="reinf-alert tone-{tone}">
                <div class="reinf-alert-head">
                    <span class="reinf-alert-tag">{LEVEL_LABEL[a["level"]]}</span>{head}
                </div>
                <div>{escape(a["message"])}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
