from typing import Generator, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.orm import Session
from pydantic import ValidationError
from app.core.config import settings

from app.db.session import SessionLocal 
from app.models.user import User # модель User

# 1. Вказуємо шлях, де отримують токен (для документації Swagger)
reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"/api/v1/auth/login" 
)

# Функція отримання БД (вона у вас вже може бути десь в іншому місці)
def get_db() -> Generator:
    try:
        db = SessionLocal()
        yield db
    finally:
        db.close()

# 2. ГОЛОВНА ФУНКЦІЯ: Перевірка токена
def get_current_user(
    db: Session = Depends(get_db),
    token: str = Depends(reusable_oauth2)
) -> User:
    try:
        # Розшифровуємо токен
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        
        # Дістаємо ID користувача (зазвичай це поле "sub")
        token_data = payload.get("sub")
        
        if token_data is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
            )
            
        # Якщо user_id це число (Int), конвертуємо:
        user_id = int(token_data) 
        
    except (JWTError, ValidationError, ValueError):
        # САМЕ ЦЮ ПОМИЛКУ (401) ЧЕКАЄ ВАШ ANDROID
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )

    # Шукаємо користувача в БД
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    return user