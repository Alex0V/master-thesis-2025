import json
import time
import random
import requests
import logging
from datetime import datetime, timedelta
from airflow.decorators import dag, task
from airflow.providers.postgres.hooks.postgres import PostgresHook

# ІМПОРТУЄМО УТИЛІТУ
from utils.ai import ask_ai_json

# --- КОНФІГУРАЦІЯ ---
PG_CONN_ID = "recipe_db_postgres"

# Налаштування Воркерів
BATCH_SIZE = 5   # Маленький батч, бо AI може думати довго
CONCURRENCY = 3  # паралельні процеси

logger = logging.getLogger("airflow.task")

@dag(
    dag_id="5_product_enricher",
    start_date=datetime(2023, 1, 1),
    schedule=None,
    catchup=False,
    tags=["enrichment", "ai", "sharded"],
    max_active_tasks=CONCURRENCY
)
def product_enricher():
    @task
    def sync_orphaned_products():
        """
        Знаходить продукти, яких немає в черзі (сироти).
        1. Якщо у продукту немає URL -> генерує 'internal://product/<id>'.
        2. Додає їх у чергу зі статусом DONE (скрапити не треба) і AI WAITING.
        """
        pg_hook = PostgresHook(postgres_conn_id=PG_CONN_ID)
        conn = pg_hook.get_conn()
        cursor = conn.cursor()

        # КРОК 1: Заповнюємо пусті URL в таблиці products технічними посиланнями
        # Це потрібно, щоб працював JOIN по original_url
        cursor.execute("""
            UPDATE products
            SET original_url = 'internal://product/' || id
            WHERE original_url IS NULL;
        """)
        if cursor.rowcount > 0:
            logger.info(f"🔧 Generated technical URLs for {cursor.rowcount} products.")

        # КРОК 2: Вставляємо в чергу тих, кого там ще немає
        # Статус 'DONE' означає "Скрапінг пропущено/завершено", можна йти до AI
        cursor.execute("""
            INSERT INTO product_queue (url, status, created_at, updated_at)
            SELECT original_url, 'DONE', NOW(), NOW()
            FROM products p
            WHERE NOT EXISTS (
                SELECT 1 FROM product_queue q WHERE q.url = p.original_url
            );
        """)
        
        if cursor.rowcount > 0:
            logger.info(f"📥 Added {cursor.rowcount} orphaned products to AI Queue.")
        else:
            logger.info("✅ No orphans found. Queue is in sync.")

        conn.commit()

    @task(retries=3, retry_delay=timedelta(seconds=30))
    def worker_task(worker_id: int):
        pg_hook = PostgresHook(postgres_conn_id=PG_CONN_ID)
        conn = pg_hook.get_conn()
        cursor = conn.cursor()

        logger.info(f"Worker #{worker_id} looking for 'DONE' tasks...")

        while True:
            # 1. ЗАБИРАЄМО РОБОТУ (Atomic Lock)
            # - Якщо статус DONE (перший запуск AI) -> скидаємо attempts на 0
            # - Якщо статус ENRICH_ERROR (ретрай) -> інкрементуємо attempts
            cursor.execute(f"""
                UPDATE product_queue
                SET status = 'ENRICH_PROCESSING', 
                    updated_at = NOW(),
                    error_message = NULL
                WHERE url IN (
                    SELECT url FROM product_queue
                    WHERE status = 'DONE'
                    LIMIT {BATCH_SIZE}
                    FOR UPDATE SKIP LOCKED
                )
                RETURNING url;
            """)

            locked_urls = [row[0] for row in cursor.fetchall()]
            # Комітимо одразу, щоб відпустити базу.
            # Тепер ці рядки мають статус 'ENRICH_PROCESSING' і ніхто інший їх не візьме.
            conn.commit()
            
            if not locked_urls:
                logger.info("💤 No 'PARSED_DONE' tasks found. Finishing.")
                break

            logger.info(f"🔒 Locked {len(locked_urls)} products. Processing...")

            try:
                # 2. ГОТУЄМО ДАНІ ДЛЯ AI
                cursor.execute("""
                    SELECT id, name, original_url FROM products 
                    WHERE original_url = ANY(%s)
                """, (locked_urls,))
                
                rows = cursor.fetchall()
                # Словники для швидкого пошуку
                products_list = [{"id": r[0], "name": r[1]} for r in rows]
                url_map = {r[0]: r[2] for r in rows} # ID -> URL
                
                if not products_list:
                    # Якщо URL є в черзі, а продуктів немає - закриваємо задачу з помилкою
                    cursor.execute("UPDATE product_queue SET status='ENRICH_ERROR', error_message='No product data' WHERE url = ANY(%s)", (locked_urls,))
                    conn.commit()
                    continue

                # 3. AI REQUEST (ОДИН ЗАПИТ НА ВСЮ ПАЧКУ!)
                # --- 3. ФОРМУЄМО ПРОМПТ ---
                prompt = f"""
                Ти — експерт-товарознавець (контекст: Україна). 
                Проаналізуй вхідний список продуктів.
                Поверни ЛИШЕ валідний JSON-список. Жодного Markdown (```json), жодних пояснень.

                Правила заповнення полів:
                1. "tags": масив ключових характеристик продукту українською, з великої літери, що описує тип, категорію або властивість продукту.
                   - Включай **загальні категорії**: Молочне, М’ясо, Овочі, Фрукти, Випічка, Крупи, Консерви, Напої тощо.
                   - Включай підкатегорію або більш узагальнена назва продукту: Свинина, Курятина, Сир, Картопля, Цибуля, Варення, Паста тощо.
                   - Включай додаткові характеристики: "Лактоза", "Глютен" тощо.
                   - Не додавай назву окремого продукта: "Сир маскарпоне", "Ароматна зелень", "Гранульований часник" тощо.
                   Приклад: ["Молочне", "Лактоза", "Молоко"], ["М'ясо", "Свинина"]
                
                2. "season_peak":
                   - Якщо продукт має виражений сезон (кавун, гарбуз, молода картопля): поверни масив місяців [6, 7, 8, ...].
                   - Якщо продукт доступний та дешевий увесь рік (сіль, цукор, крупи, макарони, курка, банан): поверни порожній масив [].

                ВХІДНІ ДАНІ:
                {json.dumps(products_list, ensure_ascii=False)}

                ОЧІКУВАНИЙ ФОРМАТ ВІДПОВІДІ:
                [
                  {{"id": 10, "tags": ["Фрукти", "Цитрусові"], "season_peak": [11, 12, 1]}},
                  {{"id": 20, "tags": ["Молочне", "Лактоза", "Молоко"], "season_peak": []}}
                ]
                """
                print(prompt)
                ai_response = ask_ai_json(prompt)

                if not ai_response or not isinstance(ai_response, list):
                    error_msg = "AI returned None or invalid JSON"
                    logger.error(f"[FAIL]: {error_msg}")
                    # зробити запис в бд помилки
                
                # --- 4. ОБРОБКА РЕЗУЛЬТАТІВ ---
                product_updates = []
                tag_ops = [] 
                processed_ids = set()

                for item in ai_response:
                    p_id = item.get("id")
                    if p_id not in url_map: continue

                    # Сезонність
                    raw_season = item.get("season_peak")
                    clean_season = []
                    if raw_season:
                        clean_season = [int(m) for m in raw_season if isinstance(m, int) and 1 <= m <= 12]
                    product_updates.append((clean_season, p_id))

                    # Теги
                    tags = item.get("tags", [])
                    for t_name in tags:
                        clean_name = str(t_name).strip().capitalize()
                        
                        # Тип 'product_cat' для всього, що прийшло
                        tag_ops.append((clean_name, "product_cat", p_id))
                    
                    processed_ids.add(p_id)

                # --- 6. ЗАПИС ---
                
                # A. Вставка тегів (тип завжди product_cat)
                unique_tags = {(t[0], t[1]) for t in tag_ops}
                if unique_tags:
                    cursor.executemany("""
                        INSERT INTO tags (name, type) VALUES (%s, %s)
                        ON CONFLICT (name) DO UPDATE 
                        SET type = EXCLUDED.type 
                        WHERE tags.type = 'general';
                    """, list(unique_tags))

                # B. Лінковка
                all_tag_names = list({t[0] for t in tag_ops})
                tag_id_map = {}
                if all_tag_names:
                    cursor.execute("SELECT name, id FROM tags WHERE name = ANY(%s)", (all_tag_names,))
                    tag_id_map = {row[0]: row[1] for row in cursor.fetchall()}

                links_to_insert = []
                for t_name, _, p_id in tag_ops:
                    if t_name in tag_id_map:
                        links_to_insert.append((p_id, tag_id_map[t_name]))
                
                if links_to_insert:
                    cursor.executemany("INSERT INTO product_tags (product_id, tag_id) VALUES (%s, %s) ON CONFLICT DO NOTHING;", links_to_insert)

                # C. Оновлення
                if product_updates:
                    cursor.executemany("UPDATE products SET seasonality = %s WHERE id = %s;", product_updates)

                # D. Статуси
                success_urls = [url_map[pid] for pid in processed_ids]
                failed = list(set(locked_urls) - set(success_urls))
                
                if success_urls:
                    cursor.execute("UPDATE product_queue SET status='ENRICH_DONE', updated_at=NOW() WHERE url = ANY(%s)", (success_urls,))
                if failed:
                    cursor.execute("UPDATE product_queue SET status='ENRICH_ERROR', error_message='AI missed item' WHERE url = ANY(%s)", (failed,))

                conn.commit()
                logger.info(f"✅ Batch: {len(success_urls)} OK")

            except Exception as e:
                # Обробка помилки всього батчу
                conn.rollback()
                logger.error(f"❌ Batch Failed: {e}")
                cursor.execute("UPDATE product_queue SET status='ENRICH_ERROR', error_message=%s WHERE url = ANY(%s)", (str(e)[:200], locked_urls))
                conn.commit()
                logger.error(f"[OK]: {ai_response}")
            #break
                
    # ЛАНЦЮЖОК ЗАПУСКУ
    # 1. Спочатку синхронізуємо сиріт
    sync = sync_orphaned_products()
    
    # 2. Потім запускаємо воркерів
    workers = worker_task.expand(worker_id=list(range(CONCURRENCY)))

    sync >> workers
product_enricher()
