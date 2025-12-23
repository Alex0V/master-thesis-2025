from sqlalchemy import Column, DateTime, Integer, String, Boolean, TIMESTAMP, ForeignKey, func, Table
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import text
from app.models.base import Base
from datetime import datetime

# Таблиця улюблених (M2M)
favorites = Table(
    "favorites",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("recipe_id", Integer, ForeignKey("recipes.id", ondelete="CASCADE"), primary_key=True),
    Column("added_at", TIMESTAMP, server_default=func.now())
)

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=True)
    full_name = Column(String(100))
    
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    is_verified = Column(Boolean, default=False)

    created_at = Column(TIMESTAMP, server_default=func.now())

    # Демографія
    family_size = Column(Integer, default=1)
    cooking_skill_level = Column(Integer, default=1)

    diets = Column(JSONB, server_default=text("'[]'::jsonb"))

    # Вподобання (JSON)
    # text("'[]'::jsonb") гарантує, що дефолт буде порожнім JSON-масивом у базі
    positive_tags = Column(JSONB, server_default=text("'[]'::jsonb"))
    negative_tags = Column(JSONB, server_default=text("'[]'::jsonb"))

    # Зв'язок з улюбленими рецептами
    favorite_recipes = relationship(
        "Recipe",
        secondary=favorites,
        back_populates="favorited_by"
    )

    # Зв'язок з токенами
    tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String, unique=True, index=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user_id = Column(Integer, ForeignKey("users.id"))
    user = relationship("User", back_populates="tokens")