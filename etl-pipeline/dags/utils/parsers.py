import re
from fractions import Fraction

# час 1:20 год в 80
def parse_time_str(text: str)-> int | None:
    """
    Парсить український час у форматах:
    - '1:50 год'
    - '45 хв'
    - '2 год 30 хв'
    - '1 год 5 хв'
    - '50 хв'
    
    Повертає: int (хвилини) або None.
    """
    if not text:
        return None

    text = text.strip().lower()

    # --- Випадок: формат "1:50" ---
    if ":" in text:
        try:
            h, m = text.split(":")
            return int(h) * 60 + int(re.sub(r"\D", "", m))
        except:
            pass  # впаде → спробуємо нижче інші варіанти

    # --- Випадок: X год Y хв ---
    hours = 0
    minutes = 0

    # Знайти години: "1 год", "2 година", "3 години"
    h_match = re.search(r"(\d+)\s*год", text)
    if h_match:
        hours = int(h_match.group(1))

    # Знайти хвилини: "30 хв", "5 хвилин"
    m_match = re.search(r"(\d+)\s*хв", text)
    if m_match:
        minutes = int(m_match.group(1))

    # Якщо знайшли щось по годинам/хвилинам
    if hours or minutes:
        return hours * 60 + minutes

    # --- Випадок: лише хвилини, наприклад '45' ---
    if text.isdigit():
        return int(text)

    return None

def parse_qty_unit(text: str):
    """
    Парсить рядок типу:
    '500 г', '150 мл', '1 шт.', '2 ст. л.', '1 ч. л.', '0.25 ч. л.', '1/4 ч. л.', 'за смаком'
    Повертає (qty: float|None, unit: str|None)
    """

    text = text.strip().lower()

    # --- випадок "за смаком" ---
    if "за смаком" in text:
        return None, "за смаком"

    # --- дроби типу 1/2, 1/4 ---
    fraction_match = re.match(r'^(\d+)\s*/\s*(\d+)\s*(.*)$', text)
    if fraction_match:
        numerator = int(fraction_match.group(1))
        denominator = int(fraction_match.group(2))
        qty = float(Fraction(numerator, denominator))
        unit = fraction_match.group(3).strip() or None
        return qty, unit

    # --- число + одиниця ---
    match = re.match(r'^([\d\.]+)\s*(.*)$', text)
    if match:
        qty_str = match.group(1)
        unit = match.group(2).strip() or None

        try:
            qty = float(qty_str)
        except ValueError:
            qty = None

        return qty, unit

    # Якщо не знайшли кількість — це просто текст
    return None, text
