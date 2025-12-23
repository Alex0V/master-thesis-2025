from sqlalchemy import Column, Integer, String, Text, ForeignKey, Table, DECIMAL
from sqlalchemy.orm import relationship
from app.models.base import Base

# Таблиця зв'язку M2M (Recipe <-> Tag)
# Оскільки тут немає додаткових полів, можна використати об'єкт Table
recipe_tags = Table(
    "recipe_tags",
    Base.metadata,
    Column("recipe_id", Integer, ForeignKey("recipes.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True)
)

class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True)
    name = Column(Text, unique=True, nullable=False)
    type = Column(String(50)) # dish_type, cuisine, diet...

    recipes = relationship(
        "Recipe", 
        secondary=recipe_tags, 
        back_populates="tags"
    )

class HolidayDefinition(Base):
    __tablename__ = "holiday_definitions"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    
    start_month = Column(Integer, nullable=False)
    start_day = Column(Integer, nullable=False)
    end_month = Column(Integer, nullable=False)
    end_day = Column(Integer, nullable=False)
    
    tag_id = Column(Integer, ForeignKey("tags.id", ondelete="SET NULL"))
    coeff = Column(DECIMAL(3, 1), default=2.0)

    # Якщо треба отримати об'єкт тегу
    tag = relationship("Tag")