from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.models.recipe import Recipe
from app.schemas.recipe import RecipeResponse # Та сама схема, що і в стрічці

router = APIRouter()

# 1. Отримати список улюблених
@router.get("/", response_model=List[RecipeResponse])
def get_favorites(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # SQLAlchemy магія: завдяки relationship ми просто беремо поле favorites
    return current_user.favorite_recipes

# 2. Додати в улюблене
@router.post("/{recipe_id}")
def add_favorite(
    recipe_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    
    if recipe not in current_user.favorite_recipes:
        current_user.favorite_recipes.append(recipe)
        db.commit()
    
    return {"message": "Recipe added to favorites"}

# 3. Видалити з улюбленого
@router.delete("/{recipe_id}")
def remove_favorite(
    recipe_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
        
    if recipe in current_user.favorite_recipes:
        current_user.favorite_recipes.remove(recipe)
        db.commit()
        
    return {"message": "Recipe removed from favorites"}