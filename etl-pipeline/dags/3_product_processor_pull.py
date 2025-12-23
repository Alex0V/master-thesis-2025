import json
import os
import requests
import hashlib
import time
import random
from datetime import datetime, timedelta
from urllib.parse import urlparse
from psycopg2.extras import Json
from slugify import slugify
from airflow.decorators import dag, task
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.providers.amazon.aws.hooks.s3 import S3Hook

# Імпорти наших утиліт
from utils.scrapers import ShubaProductParser # <--- ВИКОРИСТОВУЄМО SHUBA

# --- КОНФІГУРАЦІЯ ---
PG_CONN_ID = "recipe_db_postgres"
S3_CONN_ID = "minio_s3_storage"
BUCKET_IMAGES = os.getenv("ASSETS_BUCKET", "recipe-app-assets")

# Налаштування
WORKER_BATCH_SIZE = 5      # Скільки рецептів бере воркер за один раз
CONCURRENCY = 3             # Скільки паралельних процесів

@dag(
    dag_id="3_product_processor_pull",
    start_date=datetime(2023, 1, 1),
    schedule=None,
    catchup=False,
    tags=["products", "processing", "pull-model"],
    max_active_tasks=CONCURRENCY
)
def product_details_dag():

    # СКИДАННЯ ЗАВИСЛИХ
    @task
    def reset_stuck_tasks():
        """
        Перед початком роботи скидає всі задачі, які залишилися в стані PROCESSING
        (наприклад, через перезавантаження сервера).
        """
        pg_hook = PostgresHook(postgres_conn_id=PG_CONN_ID)
        conn = pg_hook.get_conn()
        cursor = conn.cursor()
        
        print("Перевірка черги на наявність завислих задач...")
        
        cursor.execute("""
            UPDATE product_queue 
            SET 
                status = 'NEW', 
                updated_at = NOW() 
            WHERE status = 'PROCESSING';
        """)
        
        count = cursor.rowcount
        conn.commit()
        
        if count > 0:
            print(f"Відновлено {count} завислих рецептів (повернуто в чергу).")
        else:
            print("Черга чиста. Завислих задач немає.")

    @task(retries=3, retry_delay=timedelta(seconds=30))
    def worker_task(worker_id: int):
        """
        Воркер, який працює в циклі (Loop), доки є робота.
        """

        print(f"Воркер #{worker_id} вийшов на зміну.")
        pg_hook = PostgresHook(postgres_conn_id=PG_CONN_ID)
        s3_hook = S3Hook(aws_conn_id=S3_CONN_ID)
        
        if not s3_hook.check_for_bucket(BUCKET_IMAGES):
            s3_hook.create_bucket(BUCKET_IMAGES)

        conn = pg_hook.get_conn()
        cursor = conn.cursor()
        parser = ShubaProductParser()
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'}
        # --- НЕСКІНЧЕННИЙ ЦИКЛ (Поки є робота) ---
        while True:
            # 1. БЕРЕМО ПАЧКУ ЗАДАЧ з черги
            cursor.execute(f"""
                UPDATE product_queue
                SET status = 'PROCESSING', updated_at = NOW()
                WHERE url IN (
                    SELECT url FROM product_queue
                    WHERE status = 'NEW'
                    LIMIT {WORKER_BATCH_SIZE}
                    FOR UPDATE SKIP LOCKED -- <--- Магія, що дозволяє працювати паралельно
                )
                RETURNING url;
            """)
            batch_urls = [row[0] for row in cursor.fetchall()]
            conn.commit() # Важливо зафіксувати статус PROCESSING
            
            # 2. УМОВА ВИХОДУ: Якщо база не повернула URL -> Черга пуста
            if not batch_urls:
                print(f"Воркер #{worker_id}: Робота закінчилась.")
                break
            
            print(f"Воркер #{worker_id}: Взяв пакет {len(batch_urls)} рецептів.")
            
            # 3. ОБРОБКА ПАКЕТУ
            for url in batch_urls:
                try:
                    time.sleep(random.uniform(1.5, 3.5))
                    print(f"   -> Processing: {url}")
                    
                    # --- ЗАВАНТАЖЕННЯ ---
                    response = requests.get(url, headers=headers, timeout=15)
                    if response.status_code != 200:
                        raise Exception(f"HTTP {response.status_code}")
                    
                    # --- ПАРСИНГ ---
                    data = parser.parse(response.content, url)
                    print(f"пройшов ПАРСИНГ")
                    
                    # --- ЗБЕРЕЖЕННЯ ФОТО (Simple & Smart) ---
                    minio_path = None
                    img_url = data.get('image_url')
                    if img_url:
                        try:
                            # Перевірка на абсолютний URL картинки
                            if not img_url.startswith('http'):
                                img_url = "https://shuba.life" + img_url
                            
                            path = urlparse(img_url).path 
                            # os.path.splitext повертає кортеж ('шлях/файл', '.jpg')
                            ext = os.path.splitext(path)[1].lower().strip('.')
                            
                            # Фоллбек, якщо розширення немає або воно дивне
                            if not ext or len(ext) > 4:
                                ext = 'jpg'
                            
                            # Хешування зображення
                            img_hash = hashlib.md5(img_url.encode()).hexdigest()
                            filename = f"products/{img_hash}.{ext}"

                            # Перевірка на існування (щоб не качати зайве)
                            if s3_hook.check_for_key(key=filename, bucket_name=BUCKET_IMAGES):
                                print(f"Фото вже є: {filename}")
                                minio_path = filename
                            else:
                                img_resp = requests.get(img_url, headers=headers, timeout=10)
                                if img_resp.status_code == 200:
                                    s3_hook.load_bytes(
                                        bytes_data=img_resp.content, 
                                        key=filename, 
                                        bucket_name=BUCKET_IMAGES, 
                                        replace=True
                                    )
                                minio_path = filename
                                print(f"Фото завантажено: {filename}")
                        except Exception as e:
                            print(f"Фото не завантажено: {e}")
                    print("Пройшов Фото")

                    # --- C. DB UPDATE ---
                    cursor.execute("""
                        UPDATE products
                        SET 
                            image_s3_path = %s,
                            calories_per_100g = %s,
                            proteins_per_100g = %s,
                            fats_per_100g = %s,
                            carbs_per_100g = %s,
                            parsed_at = NOW()
                        WHERE original_url = %s;
                    """, (
                        minio_path,
                        data['nutrition'].get('calories'),
                        data['nutrition'].get('proteins'),
                        data['nutrition'].get('fats'),
                        data['nutrition'].get('carbs'),
                        url
                    ))
                    print(f"Пройшов оновлення бд якщо є запис")

                    # Генеруємо slug з назви (якщо це новий запис)
                    product_slug = None
                    if data.get('name'):
                        try:
                            product_slug = slugify(data['name'])
                        except ImportError:
                             product_slug = hashlib.md5(data['name'].encode()).hexdigest()[:10]
                    print(f"Пройшов створення слагу")
                    # --- C. DB UPSERT (Вставка або Оновлення) ---
                    cursor.execute("""
                        INSERT INTO products (
                            name, slug, original_url, 
                            image_s3_path, 
                            calories_per_100g, proteins_per_100g, 
                            fats_per_100g, carbs_per_100g
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        
                        ON CONFLICT (original_url) DO UPDATE 
                        SET 
                            -- Оновлюємо поля, якщо запис вже є
                            image_s3_path = EXCLUDED.image_s3_path,
                            calories_per_100g = EXCLUDED.calories_per_100g,
                            proteins_per_100g = EXCLUDED.proteins_per_100g,
                            fats_per_100g = EXCLUDED.fats_per_100g,
                            carbs_per_100g = EXCLUDED.carbs_per_100g,
                            -- Назву і слаг краще не чіпати при оновленні, 
                            -- щоб не поламати посилання в додатку,
                            -- але якщо хочете актуалізувати назву, розкоментуйте:
                            -- name = EXCLUDED.name,
                            parsed_at = NOW();
                    """, (
                        data.get('name'),      # Для INSERT
                        product_slug,          # Для INSERT
                        url,                   # Для INSERT (original_url)
                        minio_path,
                        data['nutrition'].get('calories'),
                        data['nutrition'].get('proteins'),
                        data['nutrition'].get('fats'),
                        data['nutrition'].get('carbs')
                    ))
                    print(f"Пройшов вставку чи оновлення")
                    # --- DONE ---
                    cursor.execute("UPDATE product_queue SET status='PARSED_DONE', updated_at=NOW() WHERE url=%s", (url,))
                    conn.commit()
                    print(f"Оновлено: {data['name']}")
                except Exception as e:
                    conn.rollback()
                    print(f"Error on {url}: {e}")
                    cursor.execute("UPDATE product_queue SET status='ERROR', error_message=%s WHERE url=%s", (str(e)[:200], url))
                    conn.commit()
            # break
    # --- ПОТІК ВИКОНАННЯ ---
    
    # 1. Спочатку запускаємо очистку
    clean_step = reset_stuck_tasks()
    
    # 2. Потім створюємо список воркерів
    workers_list = list(range(CONCURRENCY))
    
    # 3. Запускаємо воркерів ТІЛЬКИ після завершення очистки
    # Оператор >> задає порядок
    clean_step >> worker_task.expand(worker_id=workers_list)

product_details_dag()