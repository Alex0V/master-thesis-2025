from pydantic import BaseModel
from typing import List, Optional

class ProductSimple(BaseModel):
    id: int
    name: str
    seasonality: List[int] = []  # Наприклад: [6, 7, 8]

    class Config:
        from_attributes = True