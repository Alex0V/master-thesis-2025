from app.schemas.tag import DietTag
from pydantic import BaseModel
from typing import List, Optional

# --- READ MODEL (Server -> Client) ---
class UserRead(BaseModel):
    id: int
    email: str
    full_name: Optional[str] = None
    family_size: int = 1
    cooking_skill_level: int = 1
    
    # Ключовий момент: Клієнт отримує об'єкти з назвами!
    diets: List[DietTag] = [] 

    class Config:
        from_attributes = True

# --- WRITE MODEL (Client -> Server) ---
class UserUpdateProfile(BaseModel):
    full_name: Optional[str] = None
    family_size: Optional[int] = None
    cooking_skill_level: Optional[int] = None
    
    # Ключовий момент: Клієнт шле тільки ID!
    diets: Optional[List[int]] = None