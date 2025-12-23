from app.api import deps
from app.models.recipe import Recipe, RecipeIngredient
from app.models.tag import Tag, recipe_tags
from app.models.user import User, favorites
from app.schemas.tag import TagGroupResponse
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session, selectinload, joinedload
from typing import List, Any, Optional
from sqlalchemy.sql import exists
from app.db.session import get_db
from app.schemas.recipe import RecipeDetailResponse, RecipeResponse
from app.services import recommendation_service

router = APIRouter()

@router.get("/recommendations", response_model=List[RecipeResponse])
def get_recommendations(
    limit: int = Query(100, ge=1, le=100, description="Ліміт видачі"),
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Повертає стрічку рекомендацій, згенеровану алгоритмом.
    Враховує сезонність, майбутні свята та тривалі події.
    """
    user_diet_ids = current_user.diets or []
    # Для налагодження можете вивести в консоль сервера:
    print(f"Запит від користувача: {current_user.email} (ID: {current_user.id})")

    return recommendation_service.generate_recommendations(db=db, limit=limit, user_diet_ids=user_diet_ids)


@router.get("/tags", response_model=List[TagGroupResponse])
def get_recipe_filters(db: Session = Depends(get_db)):
    """
    Отримати список доступних фільтрів (тегів), 
    згрупованих за категоріями (cuisine, diet, meal_type і т.д.),
    які реально прив'язані до рецептів.
    """
    # 1. Виконуємо запит: вибираємо тип і назву тегу, 
    # з'єднуючи з таблицею зв'язків рецептів
    active_tags = (
        db.query(Tag.type, Tag.name)
        .join(recipe_tags, Tag.id == recipe_tags.c.tag_id)
        .distinct()
        .all()
    )

    # 2. Групуємо результати: {'diet': ['Vegan', 'Keto'], ...}
    grouped = {}
    for t_type, t_name in active_tags:
        if t_type not in grouped:
            grouped[t_type] = []
        grouped[t_type].append(t_name)

    # 3. Формуємо відповідь згідно зі схемою
    return [
        {"category": cat, "tags": tags} 
        for cat, tags in grouped.items()
    ]

@router.get("/search", response_model=List[RecipeResponse])
def search_recipes(
    query: Optional[str] = None,
    tag_name: Optional[str] = Query(None, description="Назва тегу (напр. 'Веган')"),
    tag_type: Optional[str] = Query(None, description="Категорія (напр. 'diet')"),
    db: Session = Depends(get_db),
    limit: int = 50
):
    """
    Пошук за назвою ТА/АБО фільтрація за тегом.
    """
    stmt = db.query(Recipe)

    # 1. Фільтрація за тегами (JOIN потрібен тільки тут)
    if tag_name or tag_type:
        stmt = stmt.join(recipe_tags).join(Tag)
        
        if tag_name:
            stmt = stmt.filter(Tag.name == tag_name)
        if tag_type:
            stmt = stmt.filter(Tag.type == tag_type)

    # 2. Пошук по тексту (ILIKE - нечутливий до регістру)
    if query:
        stmt = stmt.filter(Recipe.title.ilike(f"%{query}%"))

    # 3. DISTINCT важливий, бо один рецепт може мати кілька тегів, 
    # що збігаються з умовою, і SQL може повернути його двічі.
    return stmt.distinct().limit(limit).all()

@router.get("/{recipe_id}", response_model=RecipeDetailResponse)
def get_recipe_details(
    recipe_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
) -> Any:
    """
    Отримати повну інформацію про рецепт:
    - Основні дані
    - Нутрієнти
    - Інгредієнти (з назвами продуктів)
    - Інструкції (з JSONB)
    - is_favorite (чи лайкнув цей юзер)
    """
    recipe = db.query(Recipe).options(
        # 1. Завантажуємо інгредієнти + одразу підтягуємо назви продуктів (щоб уникнути N+1)
        selectinload(Recipe.ingredients).joinedload(RecipeIngredient.product),
        # 2. Завантажуємо нутрієнти (One-to-One)
        joinedload(Recipe.nutrition)
        # Інструкції завантажуються автоматично, бо це колонка в самій таблиці recipes
    ).filter(Recipe.id == recipe_id).first()

    if not recipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Рецепт не знайдено"
        )
    
    is_fav = db.query(
        exists().where(
            favorites.c.user_id == current_user.id,
            favorites.c.recipe_id == recipe_id
        )
    ).scalar()
    recipe.is_favorite = bool(is_fav)

    return recipe