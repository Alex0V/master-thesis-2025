from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.v1.router import api_router
from contextlib import asynccontextmanager
from app.db.session import SessionLocal
from app.services import search_service
from app.db.session import engine
from app.admin import setup_admin
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

# Налаштування логування (щоб бачити повідомлення в консолі)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Створюємо планувальник
scheduler = AsyncIOScheduler()

def update_search_index():
    """
    Ця функція запускається у фоновому потоці.
    Вона оновлює глобальну змінну RECIPE_INDEX.
    """
    logger.info("[Scheduler] Починаю планове оновлення індексу...")
    db = SessionLocal()
    try:
        # Викликаємо важку функцію індексації
        search_service.build_index(db)
        logger.info("[Scheduler] Індекс успішно оновлено!")
    except Exception as e:
        logger.error(f"[Scheduler] Помилка оновлення: {e}")
    finally:
        db.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- СТАРТ СЕРВЕРА ---
    logger.info("Сервер запускається...")
    
    # 1. Запускаємо оновлення одразу (щоб не чекати першу годину з пустим індексом)
    update_search_index()
    
    # 2. Додаємо задачу в розклад (кожні 60 хвилин)
    scheduler.add_job(
        update_search_index, 
        trigger=IntervalTrigger(minutes=60), 
        id="rebuild_index",
        replace_existing=True
    )
    
    # 3. Запускаємо планувальник
    scheduler.start()
    
    yield # Тут сервер працює і обробляє запити
    
    # --- ЗУПИНКА СЕРВЕРА ---
    logger.info("Сервер зупиняється...")
    scheduler.shutdown()

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Backend for Diploma: Event-Adaptive Recipe Recommendation System",
    version="1.0.0",
    lifespan=lifespan
)

# CORS (Дозволяємо фронтенду/мобілці звертатися до нас)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Підключення всіх роутерів
app.include_router(api_router, prefix="/api/v1")

setup_admin(app, engine)

# Простий тест
@app.get("/")
def root():
    return {
        "status": "ok", 
        "recipes_in_memory": len(search_service.RECIPE_INDEX),
        "message": "System is running with APScheduler"
    }

# uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Цей блок дозволяє запускати файл як звичайний скрипт (python app/main.py)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)