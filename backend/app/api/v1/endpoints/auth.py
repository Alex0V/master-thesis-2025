from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from datetime import datetime

from app.db.session import get_db
from app.models.user import User, RefreshToken
from app.schemas.auth import UserCreate, UserLogin, GoogleLogin, Token
from app.core.security import get_password_hash, verify_password, create_tokens

router = APIRouter()

# --- HELPER ---
def save_refresh_token(db: Session, user_id: int, tokens: dict):
    db_token = RefreshToken(
        token=tokens["refresh_token"],
        expires_at=tokens["refresh_expires_at"],
        user_id=user_id
    )
    db.add(db_token)
    db.commit()

# --- ENDPOINTS ---

@router.post("/register", response_model=Token)
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == user_in.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        full_name=user_in.full_name,
        is_verified=False # Пошта не підтверджена
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    tokens = create_tokens(user.id)
    save_refresh_token(db, user.id, tokens)
    
    return {**tokens, "token_type": "bearer", "user_id": user.id, "full_name": user.full_name}

@router.post("/login", response_model=Token)
def login(user_in: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == user_in.email).first()
    if not user or not verify_password(user_in.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect email or password")

    tokens = create_tokens(user.id)
    save_refresh_token(db, user.id, tokens)

    return {**tokens, "token_type": "bearer", "user_id": user.id, "full_name": user.full_name}

@router.post("/google", response_model=Token)
def google_login(login_data: GoogleLogin, db: Session = Depends(get_db)):
    try:
        # Тут можна додати audience="YOUR_CLIENT_ID" для строгості
        id_info = id_token.verify_oauth2_token(login_data.id_token, google_requests.Request())
        email = id_info.get('email')
        name = id_info.get('name')
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid Google Token")

    user = db.query(User).filter(User.email == email).first()

    if not user:
        # Створення нового через Google
        user = User(
            email=email, full_name=name, hashed_password=None,
            is_active=True, is_verified=True # Google = Verified
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        # Злиття акаунтів: якщо такий email вже був, просто підтверджуємо його
        if not user.is_verified:
            user.is_verified = True
            db.commit()

    tokens = create_tokens(user.id)
    save_refresh_token(db, user.id, tokens)

    return {**tokens, "token_type": "bearer", "user_id": user.id, "full_name": user.full_name}

@router.post("/refresh", response_model=Token)
def refresh_token_endpoint(refresh_token: str = Body(..., embed=True), db: Session = Depends(get_db)):
    stored_token = db.query(RefreshToken).filter(RefreshToken.token == refresh_token).first()
    
    if not stored_token:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    
    if stored_token.expires_at < datetime.utcnow():
        db.delete(stored_token)
        db.commit()
        raise HTTPException(status_code=401, detail="Token expired")

    # Rotation: видаляємо використаний, створюємо новий
    user_id = stored_token.user_id
    db.delete(stored_token)
    db.commit()

    new_tokens = create_tokens(user_id)
    save_refresh_token(db, user_id, new_tokens)

    return {**new_tokens, "token_type": "bearer", "user_id": user_id}

@router.post("/logout")
def logout(refresh_token: str = Body(..., embed=True), db: Session = Depends(get_db)):
    stored_token = db.query(RefreshToken).filter(RefreshToken.token == refresh_token).first()
    if stored_token:
        db.delete(stored_token)
        db.commit()
    return {"message": "Logged out successfully"}