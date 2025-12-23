from datetime import datetime, timedelta, timezone
from jose import jwt
import bcrypt 
import secrets
from app.core.config import settings


# --- 1. ХЕШУВАННЯ ---

def verify_password(plain_password: str, hashed_password: str | None) -> bool:
    """
    Перевіряє пароль.
    Додав перевірку на None, бо у Google-юзерів пароля немає.
    """
    if hashed_password is None:
        return False
        
    # bcrypt вимагає bytes. Якщо прийшов рядок - кодуємо.
    if isinstance(hashed_password, str):
        hashed_password_bytes = hashed_password.encode('utf-8')
    else:
        hashed_password_bytes = hashed_password

    plain_password_bytes = plain_password.encode('utf-8')
    
    # Використовуємо try-except, бо іноді пошкоджений хеш може викликати помилку
    try:
        return bcrypt.checkpw(plain_password_bytes, hashed_password_bytes)
    except ValueError:
        return False

def get_password_hash(password: str) -> str:
    """
    Генерує хеш для збереження в БД.
    """
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode('utf-8')


# --- 2. ГЕНЕРАЦІЯ ТОКЕНІВ (JWT) ---
# Тут використовуємо datetime.utcnow(), щоб дружити з БД без TimeZone
def create_tokens(user_id: int):
    # Access Token (JWT)
    access_expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    access_token = jwt.encode(
        {"sub": str(user_id), "exp": access_expire, "type": "access"}, 
        settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )

    # Refresh Token (Random String)
    refresh_expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    refresh_token = secrets.token_urlsafe(64)
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "refresh_expires_at": refresh_expire
    }