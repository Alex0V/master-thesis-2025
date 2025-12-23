from sqlalchemy.orm import Session, joinedload, load_only
from datetime import date
from typing import List, Optional, Tuple, Set
from app.models import Recipe
from app.models.recipe import RecipeIngredient
from app.services import search_service


# ДОПОМІЖНІ ФУНКЦІЇ (SCORING STRATEGIES)

def _calculate_seasonal_score(
    product_ids: Set[int], 
    current_month: int
) -> Tuple[float, str]:
    """
    Рахує бали за сезонність інгредієнтів.
    """
    if not product_ids:
        return 0.0, None

    seasonal_hits = 0
    for pid in product_ids:
        p_seasons = search_service.PRODUCT_SEASONALITY.get(pid)
        if p_seasons and current_month in p_seasons:
            seasonal_hits += 1
    
    total = len(product_ids)
    ratio = seasonal_hits / total
    
    # Поріг 20%
    if ratio >= 0.2:
        # Беремо бонус з конфігу (або 50.0 за замовчуванням)
        base_bonus = search_service.SYSTEM_CONFIG.get("seasonal_bonus", 50.0)
        score = base_bonus * ratio
        return score, "Сезонні продукти"
        
    return 0.0, None


def _calculate_event_score(
    recipe_tags: Set[int],
    today: date
) -> Tuple[float, List[str]]:
    """
    Рахує бали за свята.
    Вся логіка (Warm-up vs Sustain) реалізована тут всередині.
    """
    score = 0.0
    active_events = []

    # Отримуємо базовий бал з конфігурації (наприклад, 100.0)
    holiday_base = search_service.SYSTEM_CONFIG.get("holiday_base_score", 100.0)

    # Проходимо по кешу свят (3-5 актуальних подій)
    for event in search_service.HOLIDAYS_CACHE:
        if event['tag_id'] in recipe_tags:
            
            # --- 1. Підготовка змінних ---
            event_start = event['start']
            event_end = event['end']
            
            # Розрахунок максимального балу для ЦЬОГО свята
            # (База 100 * Коефіцієнт з БД 2.0 = 200)
            max_score = holiday_base * float(event.get('coeff', 1.0))
            
            # Визначаємо тривалість та тип події
            duration_days = (event_end - event_start).days
            # Якщо триває 10 днів і більше - це "Довга подія" (Піст)
            is_long_term = duration_days >= 10
            
            # Скільки днів до початку (якщо мінус - вже почалось)
            days_until = (event_start - today).days
            
            event_points = 0.0

            # --- 2. Логіка нарахування (МАТЕМАТИКА) ---
            
            # А) Подія ще не настала (UPCOMING)
            if days_until > 0:
                if is_long_term:
                    # Довгі події заздалегідь не гріємо
                    event_points = 0.0
                else:
                    # Короткі події гріємо за 5 днів
                    if days_until <= 5:
                        # Експоненційний ріст: чим ближче, тим більше
                        event_points = max_score / (days_until * 0.5 + 1)

            # Б) Подія триває зараз (ACTIVE)
            elif event_start <= today <= event_end:
                if is_long_term:
                    event_points = max_score * 0.4 
                else:
                    # Пік для коротких свят (буст x1.5)
                    event_points = max_score * 1.5

            # --- 3. Підсумок ---
            if event_points > 0:
                score += event_points
                active_events.append(event['name'])
    
    return score, active_events


def _calculate_personal_score(
    recipe_tags: Set[int],
    user_diet_ids: Set[int]
) -> Tuple[float, Optional[str]]:
    """
    Перевіряє, чи підходить рецепт під дієту користувача.
    """
    if not user_diet_ids:
        return 0.0, None

    # Варіант А: Сувора відповідність (Strict Subset)
    # Якщо я вибрав "Веган" і "Без глютену", рецепт МАЄ містити ОБИДВА теги.
    if user_diet_ids.issubset(recipe_tags):
        # Даємо великий бонус, щоб перебити сезонність
        bonus = search_service.SYSTEM_CONFIG.get("personal_match_bonus", 200.0)
        return bonus, "Ваша дієта"

    # Варіант Б: М'яка відповідність (Intersection)
    # Якщо рецепт містить ХОЧА Б ОДНУ з моїх дієт
    # if not user_diet_ids.isdisjoint(recipe_tags):
    #     return 100.0, "Підходить вам"

    # Якщо дієти обрані, але рецепт їм не відповідає -> 0 балів (або навіть мінус)
    return 0.0, None


# ГОЛОВНИЙ ОРКЕСТРАТОР РЕКОМЕНДАЦІЙ
def generate_recommendations(db: Session, limit: int = 50, user_diet_ids: List[int] = None ) -> List[Recipe]:
    # today = date.today()
    today = date(2025, 12, 23)
    current_month = today.month
    
    scored_candidates = []
    
    # Поріг відсіювання (з конфігу)
    min_score_show = search_service.SYSTEM_CONFIG.get("min_score_show", 10.0)

    # Перетворюємо список ID дієт у Set для швидкого пошуку O(1)
    user_diets_set = set(user_diet_ids) if user_diet_ids else set()

    # 1. Головний цикл (In-Memory)
    for r_id, data in search_service.RECIPE_INDEX.items():
        total_score = 0.0
        all_reasons = []

        # --- КРОК A: Персоналізація (Найважливіше) ---
        # Якщо у юзера є дієти, це пріоритет №1
        if user_diets_set:
            p_score, p_reason = _calculate_personal_score(data['tags'], user_diets_set)
            
            # ВАЖЛИВИЙ НЮАНС:
            # Якщо користувач обрав дієту, а рецепт їй НЕ відповідає (p_score == 0),
            # то ми взагалі пропускаємо цей рецепт (Hard Filter).
            if p_score == 0:
                continue 
            
            total_score += p_score
            all_reasons.append(p_reason)

        # --- КРОК B: Сезонність ---
        s_score, s_reason = _calculate_seasonal_score(data['products'], current_month)
        if s_score > 0:
            total_score += s_score
            all_reasons.append(s_reason)

        # --- КРОК C: Свята (з вбудованою логікою) ---
        h_score, h_reasons_list = _calculate_event_score(data['tags'], today)
        if h_score > 0:
            total_score += h_score
            all_reasons.extend(h_reasons_list)

        # Фінальна перевірка та додавання
        if total_score >= min_score_show:
            scored_candidates.append((total_score, r_id, all_reasons))

    # 2. Сортування
    scored_candidates.sort(key=lambda x: x[0], reverse=True)
    top_candidates = scored_candidates[:limit]
    
    if not top_candidates:
        return []

    # 3. Гідратація (Запит в БД)
    top_ids = [item[1] for item in top_candidates]
    score_map = {item[1]: (item[0], item[2]) for item in top_candidates}

    recipes = db.query(Recipe).filter(Recipe.id.in_(top_ids)).options(
        # Використовуємо load_only, щоб взяти тільки те, що треба для картки
        load_only(
            Recipe.id,
            Recipe.title,
            Recipe.image_s3_path,
            Recipe.difficulty,
            Recipe.prep_time_min, # Потрібно для Pydantic (total_time)
            Recipe.cook_time_min, # Потрібно для Pydantic (total_time)
        )
    ).all()
    
    # Відновлення порядку
    recipes.sort(key=lambda r: score_map[r.id][0], reverse=True)

    return recipes