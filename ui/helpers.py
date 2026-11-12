from __future__ import annotations

from services.formatting import format_brl


def money_br(value) -> str:
    if value is None:
        return "—"
    return format_brl(value)


def cnpj_br(value: str | None) -> str:
    if not value:
        return "—"
    digits = "".join(ch for ch in value if ch.isdigit())
    digits = digits.zfill(14)[-14:]
    return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}"


def competence_label(year: int, month: int) -> str:
    return f"{month:02d}/{year}"


def _br_number(value: float, decimals: int) -> str:
    text = f"{value:,.{decimals}f}"
    return text.replace(",", "X").replace(".", ",").replace("X", ".")


def money_short(value) -> str:
    """Valor compacto para tabelas largas: 1,74 mi / 302,4 mil / 980,00."""
    if value is None:
        return "—"
    v = float(value)
    sign = "−" if v < 0 else ""
    v = abs(v)
    if v >= 1_000_000:
        return f"{sign}{_br_number(v / 1_000_000, 2)} mi"
    if v >= 1_000:
        return f"{sign}{_br_number(v / 1_000, 1)} mil"
    return f"{sign}{_br_number(v, 2)}"


def months_label(value: float | None) -> str:
    if value is None:
        return "—"
    if value >= 24:
        return f"{value / 12:.1f} anos".replace(".", ",")
    return f"{value:.1f} meses".replace(".", ",")


def md(text: str) -> str:
    """Texto seguro para st.markdown/st.warning: "$" literal, sem fórmula."""
    return str(text).replace("$", r"\$")
