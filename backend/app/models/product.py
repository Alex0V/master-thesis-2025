from sqlalchemy import Column, Integer, String, Text, DECIMAL
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import relationship
from app.models.base import Base

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), unique=True, nullable=False)
    slug = Column(String(255), unique=True, nullable=False)
    
    image_s3_path = Column(String(255), nullable=True)
    original_url = Column(Text, unique=True, nullable=True)
    
    # Нутрієнти на 100г
    calories_per_100g = Column(DECIMAL(10, 2))
    proteins_per_100g = Column(DECIMAL(10, 2))
    fats_per_100g = Column(DECIMAL(10, 2))
    carbs_per_100g = Column(DECIMAL(10, 2))

    # Масив чисел: [1, 2, 12] - січень, лютий, грудень
    seasonality = Column(ARRAY(Integer))

    # Зв'язок з рецептами через проміжну таблицю RecipeIngredient
    recipe_links = relationship("RecipeIngredient", back_populates="product")