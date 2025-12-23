from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.api import deps
from app.models.tag import Tag
from app.models.tag import recipe_tags # Таблиця зв'язку
from app.schemas.tag import DietTag # {id, name}

router = APIRouter()


@router.get("/diets", response_model=List[DietTag])
def get_diets(
    db: Session = Depends(deps.get_db),
    min_recipes: int = 50 # Можна поставити поріг, наприклад 50
):
    """
    Повертає список всіх доступних дієт.
    """
    # Будуємо запит: вибрати теги типу 'diet'
    query = db.query(Tag).filter(Tag.type == 'diet')
    
    # (Опціонально) Фільтруємо ті, де мало рецептів, як ми обговорювали
    if min_recipes > 0:
        query = (
            query.join(recipe_tags, Tag.id == recipe_tags.c.tag_id)
            .group_by(Tag.id)
            .having(func.count(recipe_tags.c.recipe_id) >= min_recipes)
            .order_by(func.count(recipe_tags.c.recipe_id).desc())
        )
    
    return query.all()