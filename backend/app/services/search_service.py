from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Dict, Set, List
from datetime import date, timedelta

# --- ГЛОБАЛЬНИЙ СТАН (IN-MEMORY CACHE) ---
# Структура: { recipe_id: {'tags': {1, 2}, 'products': {10, 20}} }
RECIPE_INDEX: Dict[int, Dict[str, Set[int]]] = {}

# Структура: { product_id: {1, 2, 12} } (номери місяців)
PRODUCT_SEASONALITY: Dict[int, Set[int]] = {}

# Кеш свят, щоб не смикати БД при кожному запиті
# Структура: [{'name': 'New Year', 'start': date, 'end': date, 'tag_id': 5}]
HOLIDAYS_CACHE: List[Dict] = []

# Глобальний кеш налаштувань. 
# Значення за замовчуванням (щоб код не впав, якщо база пуста)
SYSTEM_CONFIG: Dict[str, float] = {
    "holiday_base_score": 100.0,
    "seasonal_bonus": 50.0,
    "min_score_show": 10.0,
}

def build_index(db: Session):
    """
    Запускається Планувальником. Витягує всі дані raw-SQL запитами (для швидкості).
    """
    global RECIPE_INDEX, PRODUCT_SEASONALITY, HOLIDAYS_CACHE, SYSTEM_CONFIG
    
    print("[Indexer] Починаю індексацію...")

    # 0 ЗАВАНТАЖЕННЯ КОНФІГУРАЦІЇ
    raw_config = db.execute(text("SELECT key_name, value_num FROM system_config")).fetchall()
    # Оновлюємо дефолтний словник значеннями з БД
    for key, val in raw_config:
        # Конвертуємо Decimal в float для швидкості
        SYSTEM_CONFIG[key] = float(val)
        
    print(f"[Config] Налаштування завантажено: {SYSTEM_CONFIG}")

    # 1. Завантажуємо Сезонність Продуктів
    # Припускаємо, що в БД поле seasonality це масив int[]
    raw_products = db.execute(text("SELECT id, seasonality FROM products")).fetchall()
    PRODUCT_SEASONALITY = {
        row[0]: set(row[1]) if row[1] else set() 
        for row in raw_products
    }

    # 2. Ініціалізуємо рецепти
    recipe_ids = db.execute(text("SELECT id FROM recipes")).fetchall()
    temp_index = {row[0]: {'tags': set(), 'products': set()} for row in recipe_ids}

    # 3. Заповнюємо зв'язки (Інгредієнти)
    ing_data = db.execute(text("SELECT recipe_id, product_id FROM recipe_ingredients")).fetchall()
    for rid, pid in ing_data:
        if rid in temp_index:
            temp_index[rid]['products'].add(pid)

    # 4. Заповнюємо зв'язки (Теги)
    tags_data = db.execute(text("SELECT recipe_id, tag_id FROM recipe_tags")).fetchall()
    for rid, tid in tags_data:
        if rid in temp_index:
            temp_index[rid]['tags'].add(tid)
            
    # 5. Оновлюємо глобальну змінну (атомарно, наскільки це можливо в Python)
    RECIPE_INDEX = temp_index

    # 6. Кешуємо ТІЛЬКИ актуальні свята (Ковзне вікно)
   # 1. Витягуємо всі визначення свят
    # Нам не треба фільтрувати SQL-ом по датах, бо дати там умовні (місяць/день).
    # Таблиця маленька (20-30 рядків), читаємо всю.
    query = text("""
        SELECT name, start_month, start_day, end_month, end_day, tag_id, coeff 
        FROM holiday_definitions
    """)
    definitions = db.execute(query).fetchall()

    today = date.today()
    window_end = today + timedelta(days=14) # Дивимось на 14 днів вперед
    
    temp_cache = []

    # 2. Проходимо по кожному визначенню і генеруємо дати
    for row in definitions:
        name, sm, sd, em, ed, tid, base_coeff = row
        
        # Нам треба перевірити подію для ПОТОЧНОГО року і НАСТУПНОГО
        # (Бо якщо сьогодні грудень, то свято може початися в грудні, а закінчитися в січні наступного року)
        years_to_check = [today.year, today.year + 1]
        
        # Якщо сьогодні січень, а свято було в грудні минулого року і ще триває (перехід року)
        if today.month == 1:
            years_to_check.append(today.year - 1)

        for year in years_to_check:
            try:
                # Формуємо дату початку
                start_date = date(year, sm, sd)
                
                # Формуємо дату кінця
                # УВАГА: Обробка переходу через рік (Новий Рік: початок 12, кінець 01)
                target_end_year = year if em >= sm else year + 1
                end_date = date(target_end_year, em, ed)
                
                # --- ЛОГІКА КОВЗНОГО ВІКНА ---
                # Перевіряємо перетин (Intersection) двох відрізків часу:
                # [start_date, end_date]  VS  [today, window_end]
                
                # Формула перетину: max(start1, start2) < min(end1, end2)
                overlap_start = max(start_date, today)
                overlap_end = min(end_date, window_end)
                
                if overlap_start <= overlap_end:
                    # Подія актуальна! Додаємо в кеш
                    temp_cache.append({
                        "name": name,
                        "start": start_date,
                        "end": end_date,
                        "tag_id": tid,
                        "max_score": float(base_coeff) * 10 # Перетворюємо коефіцієнт (2.0 -> 20.0)
                    })
            except ValueError:
                # Це трапиться, якщо 29 лютого у невисокосний рік. Просто ігноруємо.
                continue
    for temp in temp_cache:
        print(temp['name'], temp["start"], temp["end"])
    HOLIDAYS_CACHE = temp_cache
    print(f"[Cache] Згенеровано {len(HOLIDAYS_CACHE)} подій з визначень.")