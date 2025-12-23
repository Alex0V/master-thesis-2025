# Експортуємо Base, щоб його бачили інші файли
from .base import Base

# Експортуємо моделі, щоб їх було легко діставати
from .user import User, favorites
from .product import Product
from .recipe import Recipe, NutritionInfo, RecipeIngredient
from .tag import Tag, HolidayDefinition, recipe_tags
from .system import SystemConfig