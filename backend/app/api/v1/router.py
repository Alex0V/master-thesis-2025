from fastapi import APIRouter
from app.api.v1.endpoints import auth, recipes, favorites, users, tags

api_router = APIRouter()


api_router.include_router(recipes.router, prefix="/recipes", tags=["Recipes"])
api_router.include_router(auth.router, prefix="/auth", tags=["Auth"])
api_router.include_router(favorites.router, prefix="/favorites", tags=["Favorites"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(tags.router, prefix="/tags", tags=["Tags"])