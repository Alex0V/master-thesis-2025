from pydantic import BaseModel, ConfigDict
from typing import List

class TagGroupResponse(BaseModel):
    category: str  # поле 'type' з бази даних
    tags: List[str]

    model_config = ConfigDict(from_attributes=True)

class DietTag(BaseModel):
    id: int
    name: str
    class Config:
        from_attributes = True