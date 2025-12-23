from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.api import deps
from app.models.user import User
from app.models.tag import Tag
from app.schemas.user import UserRead, UserUpdateProfile

router = APIRouter()

@router.get("/me", response_model=UserRead)
def read_user_me(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
):
    # 1. Отримуємо ID збережених дієт (List[int])
    diet_ids = current_user.diets 
    
    # 2. Знаходимо реальні об'єкти тегів у базі
    diet_objects = []
    if diet_ids:
        diet_objects = db.query(Tag).filter(Tag.id.in_(diet_ids)).all()

    # 3. Формуємо відповідь вручну, підставляючи об'єкти замість ID
    return UserRead(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        family_size=current_user.family_size,
        cooking_skill_level=current_user.cooking_skill_level,
        diets=diet_objects # Pydantic схаває це і перетворить у List[DietTagDTO]
    )

@router.patch("/me", response_model=UserRead)
def update_user_me(
    user_in: UserUpdateProfile,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
):
    # 1. Оновлюємо поля
    if user_in.full_name is not None:
        current_user.full_name = user_in.full_name
    if user_in.family_size is not None:
        current_user.family_size = user_in.family_size
    if user_in.cooking_skill_level is not None:
        current_user.cooking_skill_level = user_in.cooking_skill_level
    
    # 2. Оновлюємо дієти (зберігаємо ID, які прислав клієнт)
    if user_in.diets is not None:
        current_user.diets = user_in.diets # це List[int]

    # 3. Зберігаємо в БД
    db.add(current_user)
    db.commit()
    db.refresh(current_user) # Тепер в current_user актуальні дані

    # 4. "ГІДРАТАЦІЯ" (Наповнення об'єктами)
    # Нам треба повернути UserRead, де diets - це список об'єктів {id, name}.
    # А в базі у нас тільки ID. Тому робимо додатковий запит:
    
    diet_objects = []
    # Перевіряємо, чи є збережені дієти
    if current_user.diets:
        # SELECT * FROM tags WHERE id IN (1, 5, ...)
        diet_objects = db.query(Tag).filter(Tag.id.in_(current_user.diets)).all()

    # 5. Формуємо відповідь
    # Pydantic візьме прості поля з current_user (id, email...),
    # а поле diets ми підміняємо вручну на список об'єктів.
    return UserRead(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        family_size=current_user.family_size,
        cooking_skill_level=current_user.cooking_skill_level,
        diets=diet_objects # Передаємо об'єкти, а не ID
    )