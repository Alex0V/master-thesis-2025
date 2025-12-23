from sqlalchemy import Column, Integer, String, Text, DECIMAL, ForeignKey, Boolean, SmallInteger
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import expression
from app.models.base import Base

class Recipe(Base):
    __tablename__ = "recipes"

    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, nullable=False)
    
    original_url = Column(Text, unique=True, nullable=True)
    image_s3_path = Column(String(255), nullable=True)
    
    portions_num = Column(DECIMAL(10, 2))
    prep_time_min = Column(Integer)
    cook_time_min = Column(Integer)
    difficulty = Column(
        SmallInteger, 
        nullable=True,               # можна залишати NULL
        server_default=expression.text("1")  # дефолт на стороні БД
    )

    # Інструкції JSON
    instructions = Column(JSONB)

    # --- ЗВ'ЯЗКИ ---
    
    # 1. Один до Одного з нутрієнтами (uselist=False)
    nutrition = relationship(
        "NutritionInfo", 
        back_populates="recipe", 
        uselist=False, 
        cascade="all, delete-orphan"
    )

    # 2. Список інгредієнтів (через Association Object)
    ingredients = relationship(
        "RecipeIngredient", 
        back_populates="recipe", 
        cascade="all, delete-orphan"
    )

    # 3. Теги (через many-to-many таблицю)
    tags = relationship(
        "Tag", 
        secondary="recipe_tags", 
        back_populates="recipes"
    )

    # 4. Хто лайкнув
    favorited_by = relationship(
        "User",
        secondary="favorites",
        back_populates="favorite_recipes"
    )


class NutritionInfo(Base):
    __tablename__ = "nutrition_info"

    # PK є одночасно і FK
    recipe_id = Column(
        Integer, 
        ForeignKey("recipes.id", ondelete="CASCADE"), 
        primary_key=True
    )
    
    calories = Column(DECIMAL(10, 2))
    proteins = Column(DECIMAL(10, 2))
    fats = Column(DECIMAL(10, 2))
    carbs = Column(DECIMAL(10, 2))

    recipe = relationship("Recipe", back_populates="nutrition")
    def __str__(self):
        return f"{self.calories} ккал (Б:{self.proteins}/Ж:{self.fats}/В:{self.carbs})"

# Проміжна таблиця з додатковими даними (Кількість, Міра)
class RecipeIngredient(Base):
    __tablename__ = "recipe_ingredients"

    id = Column(Integer, primary_key=True)
    
    recipe_id = Column(Integer, ForeignKey("recipes.id", ondelete="CASCADE"))
    product_id = Column(Integer, ForeignKey("products.id"))
    
    section_name = Column(String(100), default="Основне")
    amount = Column(DECIMAL(10, 2))
    unit = Column(String(20))
    is_optional = Column(Boolean, default=False)

    # Зв'язки
    recipe = relationship("Recipe", back_populates="ingredients")
    product = relationship("Product", back_populates="recipe_links")

