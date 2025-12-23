from dataclasses import Field
from pydantic import BaseModel, HttpUrl, field_validator, model_validator, ConfigDict
from typing import Any, List, Optional
from app.schemas.product import ProductSimple
from app.core.config import settings


# 1. Схема Нутрієнтів (БЖВ)
class NutritionSchema(BaseModel):
    calories: float
    proteins: float
    fats: float
    carbs: float

    model_config = ConfigDict(from_attributes=True)

# 2. Схема Інгредієнта
class IngredientItem(BaseModel):
    name: str           # Назва продукту
    amount: float       # Число (напр. 200.0)
    unit: str           # Одиниця (напр. "г")
    is_optional: bool

    model_config = ConfigDict(from_attributes=True)

# Секція інгредієнтів (напр. "Для тіста")
class IngredientSection(BaseModel):
    name: str
    ingredients: List[IngredientItem]

    model_config = ConfigDict(from_attributes=True)

# 3. Схема Кроку приготування
class InstructionSchema(BaseModel):
    step_number: int
    title: Optional[str] = None
    description: str

    model_config = ConfigDict(from_attributes=True)


# Головна схема видачі рецепта
class RecipeResponse(BaseModel):
    id: int
    title: str
    # Optional поля (можуть бути null)
    image_s3_path: Optional[str] = None
    difficulty: str
    prep_time_min: Optional[int]
    cook_time_min: Optional[int]

    total_time: Optional[int] = None


    @field_validator('image_s3_path')
    def make_full_url(cls, v):
        if v and not v.startswith("http"):
            # Додаємо до шляху повну адресу сервера
            return f"{settings.MINIO_BASE_URL}{v}"
        return v
    
    @field_validator('difficulty', mode='before')
    def map_difficulty(cls, v):
        # Якщо прийшло число (з бази) - перетворюємо на текст
        if isinstance(v, int):
            mapping = {
                1: "Легко",
                2: "Середньо",
                3: "Складно"
            }
            return mapping.get(v, "Невідомо") # Поверне "Невідомо", якщо прийде цифра 4 або 0
        return v

    @model_validator(mode='after')
    def calculate_total_time(self):
        # Якщо є обидва часи - сумуємо. Якщо чогось немає - беремо 0.
        p = self.prep_time_min or 0
        c = self.cook_time_min or 0
        self.total_time = p + c
        return self

    model_config = ConfigDict(from_attributes=True)


# Схема для Деталей (тут нічого міняти не треба, бо RecipeResponse вже має prep_time і cook_time)
class RecipeDetailResponse(RecipeResponse):
    is_favorite: bool = False
    
    portions_num: float = 1.0

    # Вкладені структури
    nutrition: Optional[NutritionSchema] = None
    ingredients: List[IngredientSection] = []
    instructions: List[InstructionSchema] = []

    # --- ВАЛІДАТОРИ ---

    @field_validator('ingredients', mode='before')
    def group_ingredients_by_section(cls, v: List[Any]):
        """
        Приймає список об'єктів ORM (RecipeIngredient).
        Групує їх за полем section_name.
        """
        if not v:
            return []

        # Словник для групування: { "Назва секції": [список інгредієнтів] }
        sections_map = {}

        for ri in v:
            # Отримуємо назву секції (або дефолтну, якщо NULL)
            # В Python моделі DB поле має називатися section_name
            sec_name = getattr(ri, "section_name", None) or "Основне"

            # Формуємо об'єкт інгредієнта
            ingredient_data = {
                "name": ri.product.name if ri.product else "Невідомий продукт",
                "amount": ri.amount or 0.0,
                "unit": ri.unit or "",
                "is_optional": ri.is_optional
            }

            if sec_name not in sections_map:
                sections_map[sec_name] = []
            
            sections_map[sec_name].append(ingredient_data)

        # Перетворюємо словник у список об'єктів IngredientSection
        # Порядок збережеться таким, яким він був у БД (якщо ви сортували при запиті)
        result = [
            {"name": name, "ingredients": items}
            for name, items in sections_map.items()
        ]
        
        return result

    @field_validator('instructions', mode='before')
    def parse_instructions(cls, v):
        if not v:
            return []
            
        if isinstance(v, list):
            parsed_steps = []
            for idx, item in enumerate(v):
                if isinstance(item, dict):
                    parsed_steps.append({
                        "step_number": item.get("step_number", idx + 1),
                        "title": item.get("title"),
                        "description": item.get("description", "")
                    })
                elif isinstance(item, str):
                    parsed_steps.append({
                        "step_number": idx + 1,
                        "title": None,
                        "description": item
                    })
            return parsed_steps
        return []


# Вкладена схема: Скільки + Чого
class IngredientShow(BaseModel):
    amount: Optional[float] = None  
    unit: Optional[str] = None      
    
    product: ProductSimple

    model_config = ConfigDict(from_attributes=True)