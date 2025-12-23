from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "Smart Recipe Recommender"
    # Postgres
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_SERVER: str
    POSTGRES_DB: str = "recipe_db"

    # Redis 
    # REDIS_HOST: str = "localhost"
    # REDIS_PORT: int = 6379

    ADMIN_SECRET_KEY: str
    MINIO_BASE_URL: str

    # Token
    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 60

    # Склеюємо URL автоматично
    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@localhost:{self.POSTGRES_SERVER}/{self.POSTGRES_DB}"

    model_config = SettingsConfigDict(
        env_file = ".env", # Читати з .env, якщо є
        extra = "ignore", # Ігнорувати зайві змінні в файлі
        env_file_encoding="utf-8"
    )

settings = Settings()