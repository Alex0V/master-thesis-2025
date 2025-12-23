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
BATCH_SIZE = 4   # Маленький батч, бо AI може думати довго
CONCURRENCY = 25  # паралельні процеси

logger = logging.getLogger("airflow.task")

@dag(
    dag_id="4_enrich_ai_sharded",
    start_date=datetime(2023, 1, 1),
    schedule=None,
    catchup=False,
    tags=["enrichment", "ai", "sharded"],
    max_active_tasks=CONCURRENCY
)
def optional_enricher():

    @task(retries=3, retry_delay=timedelta(seconds=30))
    def worker_task(worker_id: int):
        pg_hook = PostgresHook(postgres_conn_id=PG_CONN_ID)
        conn = pg_hook.get_conn()
        cursor = conn.cursor()

        logger.info(f"Worker #{worker_id} is searching for recipes (Status: PARSED_DONE)...")

        while True:
            # 1. ЗАБИРАЄМО РОБОТУ (Перехід: PARSED_DONE -> OPTIONAL_PROCESSING)
            cursor.execute(f"""
                UPDATE recipe_queue
                SET status = 'OPTIONAL_PROCESSING', updated_at = NOW()
                WHERE url IN (
                    SELECT url FROM recipe_queue
                    WHERE status = 'PARSED_DONE' -- Беремо ті, що успішно спарсені
                    LIMIT {BATCH_SIZE}
                    FOR UPDATE SKIP LOCKED
                )
                RETURNING url;
            """)
            
            batch_urls = [row[0] for row in cursor.fetchall()]
            conn.commit()

            if not batch_urls:
                logger.info("The queue is empty. I'm finishing work.")
                break

            logger.info(f"Fetched  {len(batch_urls)} recipes for analysis.")

            for url in batch_urls:
                try:
                    # 2. Отримуємо ID та Назву рецепта
                    cursor.execute("SELECT id, title FROM recipes WHERE original_url = %s", (url,))
                    res = cursor.fetchone()
                    if not res:
                        logger.error(f"Recipe not found in DB: {url}")
                        cursor.execute("UPDATE recipe_queue SET status='OPTIONAL_ERROR', error_message='Recipe missing' WHERE url=%s", (url,))
                        conn.commit()
                        continue
                        
                    r_id, r_title = res
                    logger.info(f"Processing recipe: id={r_id}, title='{r_title}', url='{url}'")

                    # 3. Отримуємо інгредієнти цього рецепта
                    cursor.execute("""
                        SELECT ri.product_id, p.name, ri.amount, ri.unit, ri.section_name
                        FROM recipe_ingredients ri
                        JOIN products p ON ri.product_id = p.id
                        WHERE ri.recipe_id = %s
                    """, (r_id,))
                    
                    ingredients = cursor.fetchall()
                    
                    if not ingredients:
                        logger.warning(f"No ingredients for {r_title}. Skipping AI.")
                        cursor.execute("UPDATE recipe_queue SET status='OPTIONAL_ERROR' WHERE url=%s", (url,))
                        conn.commit()
                        continue

                    # Формуємо текст списку для AI
                    ing_list_text = "\n".join([
                        f"ID {row[0]}: {row[1]} ({row[2] or ''} {row[3] or ''}) [Секція: {row[4]}]" 
                        for row in ingredients
                    ])

                    # 4. Формуємо Промпт
                    prompt = (
                        f"Аналізуємо рецепт: '{r_title}'.\n"
                        f"Інгредієнти:\n{ing_list_text}\n\n"
                        f"Завдання: Визнач інгредієнти, які є опційним, а точніше не обов'язковими (для подачі, декору, 'за бажанням', хліб до супу, ...).\n"
                        f"Якщо інгредієнт у секції 'Подача' або 'Декор' - він точно опційним.\n"
                        f"Якщо інгредієнт 'за смаком' він може бути опційним, але не завджи.\n"
                        f"Поверни JSON: {{ \"optional_ids\": [список_id_int] }}.\n"
                        f"Якщо всі важливі - поверни порожній список [список_id_int]."
                    )
                    # print(prompt)

                    # 5. Запит до AI
                    ai_result = ask_ai_json(prompt)

                    # 6. Обробляємо результат
                    if ai_result and "optional_ids" in ai_result:
                        opt_ids = ai_result["optional_ids"]
                        
                        if opt_ids:
                            # Ставимо is_optional = TRUE
                            cursor.execute("""
                                UPDATE recipe_ingredients
                                SET is_optional = TRUE
                                WHERE recipe_id = %s AND product_id = ANY(%s)
                            """, (r_id, opt_ids))
                            logger.info(f"[OK] '{r_title}': marked {len(opt_ids)} optional ingredients.")
                        else:
                            logger.info(f"[OK] '{r_title}': all ingredients are mandatory.")
                        
                        # УСПІШНЕ ЗАВЕРШЕННЯ
                        cursor.execute("UPDATE recipe_queue SET status='OPTIONAL_DONE', updated_at=NOW(), error_message=NULL WHERE url=%s", (url,))

                    else:
                        # ЛОГІЧНА ПОМИЛКА AI (повернув None або сміття)
                        error_msg = "AI returned None or invalid JSON"
                        logger.error(f"[FAIL] '{r_title}': {error_msg}")
                        
                        cursor.execute("""
                            UPDATE recipe_queue 
                            SET status='OPTIONAL_ERROR', error_message=%s, updated_at=NOW()
                            WHERE url=%s
                        """, (error_msg, url))

                    logger.info(f"Processing of '{r_title}' completed.")
                    # Фіксуємо транзакцію для цього рецепта
                    conn.commit()

                except Exception as e:
                    # ТЕХНІЧНА ПОМИЛКА (Exception)
                    conn.rollback() # Відкочуємо зміни в recipe_ingredients, якщо вони були наполовину зроблені
                    logger.error(f"[CRASH] Processing {url}: {e}")
                    
                    # Записуємо помилку в чергу
                    try:
                        cursor.execute("""
                            UPDATE recipe_queue 
                            SET status='OPTIONAL_ERROR', error_message=%s, attempts=attempts+1, updated_at=NOW()
                            WHERE url=%s
                        """, (f"Exception: {str(e)[:200]}", url))
                        conn.commit()
                    except:
                        pass # Якщо навіть це впало (наприклад, втрата зв'язку з БД), то нічого не зробиш
    # Запуск воркерів
    worker_ids = list(range(CONCURRENCY))
    worker_task.expand(worker_id=worker_ids)

optional_enricher()