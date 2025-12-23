from pydantic import BaseModel, EmailStr, validator
from typing import Optional
from email_validator import validate_email, EmailNotValidError

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    user_id: int
    full_name: Optional[str] = None

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None

    @validator("email")
    def validate_real_email(cls, v):
        try:
            valid = validate_email(v, check_deliverability=True) # DNS перевірка
            return valid.email
        except EmailNotValidError as e:
            raise ValueError(f"Invalid email: {str(e)}")

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class GoogleLogin(BaseModel):
    id_token: str