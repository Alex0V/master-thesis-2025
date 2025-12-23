from datetime import date
from sqlalchemy.orm import Session
from app.models import HolidayDefinition

def get_current_context(db: Session):
    """
    Повертає поточний місяць і словник активних свят.
    """
    today = date.today()
    #today = date(2025, 12, 20) #  тест Різдва
    
    current_year = today.year
    
    # Отримуємо всі визначення свят
    all_holidays = db.query(HolidayDefinition).all()

    # Словник активних свят: {tag_id: {info}}
    active_holiday_map = {}

    for h in all_holidays:
        try:
            # Формуємо дати початку і кінця для поточного року
            start_date = date(current_year, h.start_month, h.start_day)
            end_date = date(current_year, h.end_month, h.end_day)
            
            # Логіка переходу через Новий Рік (напр. грудень -> січень)
            is_cross_year = start_date > end_date
            if is_cross_year:
                # Якщо сьогодні січень, а свято почалося в грудні минулого року
                if today.month <= h.end_month:
                    start_date = date(current_year - 1, h.start_month, h.start_day)
                # Якщо сьогодні грудень, а свято закінчиться в січні наступного
                else:
                    end_date = date(current_year + 1, h.end_month, h.end_day)

            # Перевірка 1: Свято йде зараз?
            is_active = start_date <= today <= end_date
            
            # Перевірка 2: Свято скоро? (14 днів до)
            days_diff = (start_date - today).days
            is_upcoming = 0 <= days_diff <= 14
            
            if is_active or is_upcoming:
                status_text = h.name if is_active else f"Скоро: {h.name}"
                
                # Додаємо у словник по ID тегу
                active_holiday_map[h.tag_id] = {
                    "name": status_text,
                    "coeff": float(h.coeff) if h.coeff else 1.0,
                    "is_upcoming": is_upcoming
                }
        except ValueError:
            continue # Пропускаємо помилкові дати (напр. 30 лютого)
    
    print({
        "month": today.month,
        "active_holidays": active_holiday_map
    })
    return {
        "month": today.month,
        "active_holidays": active_holiday_map
    }