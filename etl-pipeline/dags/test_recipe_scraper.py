import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import hashlib

from airflow.decorators import dag, task
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.providers.amazon.aws.hooks.s3 import S3Hook

# комент для перевірки оновлення, ну і що оновилось?

# --- КОНФІГУРАЦІЯ ---
PG_CONN_ID = "recipe_db_postgres"
S3_CONN_ID = "minio_s3_storage"
BUCKET_IMAGES = "recipe-images"

# Список URL для скрапінгу (можна розширити)
URLS_TO_SCRAPE = [
    "https://klopotenko.com/ukrainskyi-borshch-na-svynyachomu-rebri/",
    "https://klopotenko.com/banosh-z-brynzoyu-i-shkvarkamy/"
]

@dag(
    dag_id="test_recipe_scraper",
    start_date=datetime(2023, 1, 1),
    schedule=None,
    catchup=False,
    tags=["production", "recipes", "scraping"]
)
def scraper_dag():

    @task
    def init_db_schema():
        """Створює фінальну таблицю для рецептів"""
        pg_hook = PostgresHook(postgres_conn_id=PG_CONN_ID)
        pg_hook.run("""
            CREATE TABLE IF NOT EXISTS parsed_recipes (
                id SERIAL PRIMARY KEY,
                title VARCHAR(255),
                url TEXT UNIQUE,
                image_minio_path VARCHAR(255),
                ingredients TEXT,
                parsed_at TIMESTAMP DEFAULT NOW()
            );
        """)
        print("✅ Таблиця parsed_recipes готова.")

    @task
    def extract_recipe_data(urls: list) -> list:
        """
        Завантажує HTML та парсить його за допомогою BeautifulSoup.
        """
        extracted_data = []
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        for url in urls:
            try:
                print(f"🔍 Скануємо: {url}")
                response = requests.get(url, headers=headers)
                response.raise_for_status() # Перевірка на помилки 404/500

                soup = BeautifulSoup(response.content, 'html.parser')

                # --- ЛОГІКА ПАРСИНГУ (ПІД САЙТ KLOPOTENKO) ---
                
                # 1. Назва страви
                title_tag = soup.find('div', class_='recipe-header__main-info')
                title = title_tag.find('h1').text.strip() if title_tag else "Невідома страва"

                # 2. Головне фото (шукаємо в блоці зображення)
                img_tag = soup.find('div', class_='recipe-header__img')
                if img_tag:
                    # Іноді картинка в 'src', іноді в 'data-src' (lazy load)
                    img_obj = img_tag.find('img')
                    image_url = img_obj.get('src') or img_obj.get('data-src')
                else:
                    image_url = None

                # 3. Інгредієнти (збираємо всі li в блоці інгредієнтів)
                ing_div = soup.find('div', class_='ingredients__list')
                ingredients_list = []
                if ing_div:
                    for li in ing_div.find_all('div', class_='checkbox-item'):
                         ingredients_list.append(li.get_text(strip=True))
                
                ingredients_text = "; ".join(ingredients_list)

                # Додаємо в результат
                extracted_data.append({
                    "title": title,
                    "url": url,
                    "image_url": image_url,
                    "ingredients": ingredients_text
                })
                print(f"   -> Знайдено: {title}")

            except Exception as e:
                print(f"❌ Помилка при обробці {url}: {e}")
        
        return extracted_data

    @task
    def upload_images_to_minio(recipes: list) -> list:
        """
        Завантажує фото з інтернету і кладе в MinIO.
        """
        s3_hook = S3Hook(aws_conn_id=S3_CONN_ID)
        
        # Переконаємось, що бакет існує
        if not s3_hook.check_for_bucket(BUCKET_IMAGES):
            s3_hook.create_bucket(BUCKET_IMAGES)

        processed_recipes = []

        for item in recipes:
            image_url = item.get("image_url")
            minio_path = None

            if image_url:
                try:
                    # Генеруємо унікальне ім'я файлу (хеш від URL), щоб не було дублів
                    url_hash = hashlib.md5(item['url'].encode()).hexdigest()
                    file_ext = image_url.split('.')[-1].split('?')[0] # jpg, png...
                    if len(file_ext) > 4: file_ext = "jpg" # Фоллбек, якщо розширення дивне
                    
                    filename = f"photos/{url_hash}.{file_ext}"

                    print(f"📥 Завантаження: {image_url}")
                    img_data = requests.get(image_url, stream=True).content
                    
                    s3_hook.load_bytes(
                        bytes_data=img_data,
                        key=filename,
                        bucket_name=BUCKET_IMAGES,
                        replace=True
                    )
                    minio_path = filename
                    print(f"   -> Збережено в MinIO: {filename}")

                except Exception as e:
                    print(f"⚠️ Не вдалося завантажити фото: {e}")
            
            # Оновлюємо словник новим шляхом
            item['minio_path'] = minio_path
            processed_recipes.append(item)

        return processed_recipes

    @task
    def save_to_postgres(recipes: list):
        """
        Зберігає фінальні дані (з посиланням на MinIO) в Postgres
        """
        pg_hook = PostgresHook(postgres_conn_id=PG_CONN_ID)
        
        inserted_count = 0
        for item in recipes:
            sql = """
                INSERT INTO parsed_recipes (title, url, image_minio_path, ingredients)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (url) DO UPDATE 
                SET title = EXCLUDED.title,
                    image_minio_path = EXCLUDED.image_minio_path,
                    ingredients = EXCLUDED.ingredients,
                    parsed_at = NOW();
            """
            pg_hook.run(sql, parameters=(
                item['title'],
                item['url'],
                item['minio_path'],
                item['ingredients']
            ))
            inserted_count += 1
            
        print(f"💾 Успішно збережено/оновлено {inserted_count} рецептів у БД.")

    # --- ПОТІК ВИКОНАННЯ ---
    init = init_db_schema()
    raw_data = extract_recipe_data(URLS_TO_SCRAPE)
    data_with_images = upload_images_to_minio(raw_data)
    save_final = save_to_postgres(data_with_images)

    # Встановлюємо порядок
    init >> raw_data >> data_with_images >> save_final

scraper_dag()