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
from utils.scrapers import ShubaRecipeParser # <--- ВИКОРИСТОВУЄМО SHUBA

# --- КОНФІГУРАЦІЯ ---
PG_CONN_ID = "recipe_db_postgres"
S3_CONN_ID = "minio_s3_storage"
BUCKET_IMAGES = os.getenv("ASSETS_BUCKET", "recipe-app-assets")

# Налаштування
WORKER_BATCH_SIZE = 5      # Скільки рецептів бере воркер за один раз
CONCURRENCY = 3             # Скільки паралельних процесів

@dag(
    dag_id="2_recipe_processor_pull",
    start_date=datetime(2023, 1, 1),
    schedule=None,
    catchup=False,
    tags=["processing", "pull-model"],
    max_active_tasks=CONCURRENCY
)
def processor_dag():

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
            UPDATE recipe_queue 
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
        parser = ShubaRecipeParser()
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'}
        # --- НЕСКІНЧЕННИЙ ЦИКЛ (Поки є робота) ---
        while True:
            # 1. БЕРЕМО ПАЧКУ ЗАДАЧ з черги
            cursor.execute(f"""
                UPDATE recipe_queue
                SET status = 'PROCESSING', updated_at = NOW()
                WHERE url IN (
                    SELECT url FROM recipe_queue
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

                    # --- ЗБЕРЕЖЕННЯ ФОТО ---
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
                            filename = f"recipes/{img_hash}.{ext}"

                            # Перевірка на існування (щоб не качати зайве)
                            if s3_hook.check_for_key(key=filename, bucket_name=BUCKET_IMAGES):
                                print(f"Фото вже є: {filename}")
                                minio_path = filename

                            img_resp = requests.get(img_url, headers=headers, timeout=10)
                            if img_resp.status_code == 200:
                                s3_hook.load_bytes(img_resp.content, key=filename, bucket_name=BUCKET_IMAGES, replace=True)
                                minio_path = filename
                        except Exception as e:
                            print(f"Фото не завантажено: {e}")

                    # --- C. КАТЕГОРІЯ (GET OR CREATE) ---
                    category_id = None
                    cat_title = data.get('category') # "Сніданки"
                    
                    if cat_title:
                        cat_title = cat_title.strip()
                        # Генеруємо slug (наприклад "snidanky")
                        cat_slug = slugify(cat_title)
                        
                        # Атомарна вставка: якщо є - повертає ID, якщо ні - створює і повертає ID
                        cursor.execute("""
                            INSERT INTO categories (title, slug)
                            VALUES (%s, %s)
                            ON CONFLICT (title) DO UPDATE 
                            SET title = EXCLUDED.title -- пусте оновлення, щоб спрацював RETURNING
                            RETURNING id;
                        """, (cat_title, cat_slug))
                        
                        category_id = cursor.fetchone()[0]
                    
                    # --- ЗАПИС РЕЦЕПТА ---
                    cursor.execute("""
                        INSERT INTO recipes (
                            title, slug, category_id, original_url,
                            image_s3_path, 
                            portions_num, prep_time_min, cook_time_min,
                            instructions, -- JSONB
                            parsed_at
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                        ON CONFLICT (original_url) DO UPDATE 
                        SET 
                            title = EXCLUDED.title,
                            image_s3_path = EXCLUDED.image_s3_path,
                            instructions = EXCLUDED.instructions,
                            parsed_at = NOW()
                        RETURNING id;
                    """, (
                        data['title'],
                        slugify(data['title']),
                        category_id,
                        data['original_url'],
                        minio_path,
                        data.get('portions_num'),
                        data.get('prep_time'),
                        data.get('cook_time'),
                        Json(data.get('instructions'))
                    ))
                    recipe_id = cursor.fetchone()[0]

                    # --- F. НУТРІЄНТИ ---
                    nutr = data.get('nutrition', {})
                    cursor.execute("""
                        INSERT INTO nutrition_info (recipe_id, calories, proteins, fats, carbs)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (recipe_id) DO UPDATE SET calories=EXCLUDED.calories;
                    """, (recipe_id, nutr.get('calories'), nutr.get('proteins'), nutr.get('fats'), nutr.get('carbs')))

                    # --- ЗАПИС ІНГРЕДІЄНТІВ ---
                    cursor.execute("DELETE FROM recipe_ingredients WHERE recipe_id = %s", (recipe_id,))
                    for item in data.get('ingredients_list', []):
                        prod_name = item['product'].strip()
                        if not prod_name: continue
                        
                        prod_url = item.get('product_url')
                        prod_id = None
                        
                        # 1. ЛІНИВЕ ВИЯВЛЕННЯ ПРОДУКТІВ (LAZY DISCOVERY)
                        if prod_url:
                            # Якщо є URL, шукаємо по ньому
                            cursor.execute("""
                                INSERT INTO products (name, slug, original_url)
                                VALUES (%s, %s, %s)
                                ON CONFLICT (original_url) DO UPDATE SET name = EXCLUDED.name
                                RETURNING id;
                            """, (prod_name, slugify(prod_name), prod_url))
                            prod_id = cursor.fetchone()[0]
                            
                            # Додаємо URL продукту в чергу на збагачення!
                            cursor.execute("""
                                INSERT INTO product_queue (url, status) 
                                VALUES (%s, 'NEW') 
                                ON CONFLICT (url) DO NOTHING;
                            """, (prod_url,))
                            
                        else:
                            # Якщо URL немає, шукаємо по назві
                            # (Спрощена логіка, без fuzzy поки що)
                            cursor.execute("SELECT id FROM products WHERE name = %s", (prod_name,))
                            res = cursor.fetchone()
                            if res:
                                prod_id = res[0]
                            else:
                                cursor.execute("""
                                    INSERT INTO products (name, slug) 
                                    VALUES (%s, %s) RETURNING id
                                """, (prod_name, slugify(prod_name)))
                                prod_id = cursor.fetchone()[0]

                        # 2. ЗВ'ЯЗОК
                        cursor.execute("""
                            INSERT INTO recipe_ingredients (
                                recipe_id, product_id, section_name, 
                                amount, unit
                            )
                            VALUES (%s, %s, %s, %s, %s)
                            ON CONFLICT DO NOTHING;
                        """, (
                            recipe_id, 
                            prod_id, 
                            item.get('section', 'Основні'),
                            item.get('amount'),
                            item.get('unit'),
                        ))

                    # --- ЗАВЕРШЕННЯ ---
                    cursor.execute("UPDATE recipe_queue SET status='DONE', updated_at=NOW() WHERE url=%s", (url,))
                    conn.commit()
                    print(f"Готово: {data['title']}")

                except Exception as e:
                    conn.rollback()
                    print(f"Error: {e}")
                    cursor.execute("UPDATE recipe_queue SET status='ERROR', error_message=%s WHERE url=%s", (str(e)[:200], url))
                    conn.commit()
    
    # --- ПОТІК ВИКОНАННЯ ---
    
    # 1. Спочатку запускаємо очистку
    clean_step = reset_stuck_tasks()
    
    # 2. Потім створюємо список воркерів
    workers_list = list(range(CONCURRENCY))
    
    # 3. Запускаємо воркерів ТІЛЬКИ після завершення очистки
    # Оператор >> задає порядок
    clean_step >> worker_task.expand(worker_id=workers_list)

processor_dag()