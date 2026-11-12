from __future__ import annotations


def format_brl(value) -> str:
    """Moeda no padrão brasileiro: R$ 1.234,56 e -R$ 1.234,56.

    Arredonda para centavos antes de decidir o sinal, então -0,004 vira R$ 0,00.
    """
    number = round(float(value or 0), 2)
    sign = "-" if number < 0 else ""
    text = f"{abs(number):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{sign}R$ {text}"
