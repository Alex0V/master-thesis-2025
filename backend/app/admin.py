from sqladmin import Admin, ModelView
from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request
from starlette.responses import RedirectResponse
from app.db.session import SessionLocal
from app.models import User, Recipe, SystemConfig, HolidayDefinition, Tag, NutritionInfo
from app.core.security import verify_password
from app.core.config import settings


# 1. НАЛАШТУВАННЯ БЕЗПЕКИ (LOGIN) 
class AdminAuth(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        form = await request.form()
        email = form.get("username") # SQLAdmin використовує поле 'username'
        password = form.get("password")

        # Відкриваємо сесію БД вручну, бо це не ендпоінт FastAPI
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.email == email).first()
            
            # Перевіряємо: існування, пароль ТА права адміна
            if user and verify_password(password, user.hashed_password):
                if user.is_superuser:
                    # Успіх! Записуємо в сесію
                    request.session.update({"token": f"admin_{user.id}"})
                    return True
        finally:
            db.close()
            
        return False

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        # Перевіряємо, чи є токен у сесії
        return "token" in request.session


authentication_backend = AdminAuth(secret_key=settings.ADMIN_SECRET_KEY)


# 2. НАЛАШТУВАННЯ ВИГЛЯДУ ТАБЛИЦЬ (VIEWS) 
class UserAdmin(ModelView, model=User):
    name = "Користувач"
    name_plural = "Користувачі"
    icon = "fa-solid fa-user"
    
    # Які колонки показувати в списку
    column_list = [User.id, User.email, User.is_superuser, User.created_at]
    # По яким колонкам можна шукати
    column_searchable_list = [User.email]
    # Які колонки можна сортувати
    column_sortable_list = [User.id, User.created_at]

class SystemConfigAdmin(ModelView, model=SystemConfig):
    name = "Налаштування"
    name_plural = "Конфігурація системи"
    icon = "fa-solid fa-gears"
    
    column_list = [SystemConfig.key_name, SystemConfig.value_num, SystemConfig.description]
    # Робимо так, щоб можна було редагувати опис
    form_columns = [SystemConfig.key_name, SystemConfig.value_num, SystemConfig.description]


class HolidayAdmin(ModelView, model=HolidayDefinition):
    name = "Свято"
    name_plural = "Свята"
    icon = "fa-solid fa-calendar-days"
    
    column_list = [HolidayDefinition.name, HolidayDefinition.coeff]
    form_columns = [
        HolidayDefinition.name, 
        HolidayDefinition.start_month, 
        HolidayDefinition.start_day, 
        HolidayDefinition.start_month, 
        HolidayDefinition.start_day, 
        HolidayDefinition.coeff
        ]

class NutritionAdmin(ModelView, model=NutritionInfo):
    name = "Харчова цінність"
    name_plural = "Харчова цінність"
    icon = "fa-solid fa-chart-pie"
    column_list = [NutritionInfo.recipe_id, NutritionInfo.calories, NutritionInfo.proteins, NutritionInfo.fats, NutritionInfo.carbs]

    def is_visible(self, request: Request) -> bool:
        return False
    
class RecipeAdmin(ModelView, model=Recipe):
    name = "Рецепт"
    name_plural = "Рецепти"
    icon = "fa-solid fa-utensils"
    
    column_list = [Recipe.id, Recipe.title]
    column_searchable_list = [Recipe.title]
    form_columns = [
        Recipe.title,
        Recipe.prep_time_min,
        Recipe.cook_time_min,
        Recipe.image_s3_path,
    ]

    page_size = 20


# 3. ФУНКЦІЯ ПІДКЛЮЧЕННЯ (SETUP) 
def setup_admin(app, engine):
    admin = Admin(
        app=app, 
        engine=engine, 
        authentication_backend=authentication_backend,
        title="Admin Panel",
        base_url="/admin" # URL адмінки
    )
    
    # Реєструємо наші в'юшки
    admin.add_view(UserAdmin)
    admin.add_view(RecipeAdmin)
    admin.add_view(NutritionAdmin)
    admin.add_view(SystemConfigAdmin)
    admin.add_view(HolidayAdmin)
    
    return admin