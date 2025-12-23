import logging
from datetime import datetime, timedelta
from airflow.decorators import dag, task
from airflow.providers.postgres.hooks.postgres import PostgresHook
from free_proxy_server import ProxyClient, ProxyFilter

PG_CONN_ID = "recipe_db_postgres"
logger = logging.getLogger("airflow.task")

@dag(
    dag_id="proxy_rotator",
    start_date=datetime(2023, 1, 1),
    schedule="*/5 * * * *", 
    catchup=False,
    tags=["system", "proxy"],
    default_args={"retries": 1, "retry_delay": timedelta(minutes=1)}
)

def proxy_rotator():

    @task
    def update_proxy_pool():
        logger.info("📡 Запитуємо проксі через бібліотеку...")
        
        client = ProxyClient()
        
        # Налаштовуємо фільтр
        filters = ProxyFilter(
            protocol="http",    # Нам потрібен HTTP
            country_code=None,  # Можна 'US', 'DE' якщо треба, але краще будь-які
            max_timeout=3000,   # До 2 секунд
            working_only=True,  # Тільки перевірені
        )

        try:
            proxies = client.get_proxies(filters)
        except Exception as e:
            logger.error(f"❌ Library error: {e}")
            return

        if not proxies:
            logger.warning(" The library did not find any proxies.")
            return

        logger.info(f"✅ Retrieved {len(proxies)} proxies.")

        # --- ГОЛОВНІ ЗМІНИ ТУТ ---
        # Парсимо об'єкт Proxy(address='...', port=..., timeout_ms=...)
        
        db_rows = []
        found_urls = [] # Явний список живих URL для зручності
        for p in proxies:
            # 1. Формуємо URL: http://ip:port
            # Використовуємо атрибути .address і .port з вашого прикладу
            url = f"{p.protocol}://{p.address}:{p.port}"
            
            # 2. Швидкість (беремо timeout_ms)
            speed = int(getattr(p, 'timeout_ms', 1000))
            
            # 3. Додаємо в список для UPSERT
            db_rows.append((url, p.protocol, speed))
            
            # 4. Додаємо в список для перевірки "хто вижив"
            found_urls.append(url)

        # --- ЗАПИС В БД ---
        pg_hook = PostgresHook(postgres_conn_id=PG_CONN_ID)
        conn = pg_hook.get_conn()
        cursor = conn.cursor()

        # КРОК 1: UPSERT
        # Якщо проксі вже є (конфлікт по url) -> Оновлюємо статус на TRUE і час перевірки
        # Якщо немає -> Вставляємо нову
        query = """
            INSERT INTO active_proxies (url, protocol, speed_ms, is_active, last_checked_at)
            VALUES (%s, %s, %s, TRUE, NOW())
            ON CONFLICT (url) DO UPDATE 
            SET is_active = TRUE,
                speed_ms = EXCLUDED.speed_ms,
                last_checked_at = NOW();
        """
        cursor.executemany(query, db_rows)
        
        # КРОК 2: DEACTIVATE MISSING (Вимикаємо тих, кого немає в списку)
        # Ми ставимо is_active = FALSE всім, чий URL НЕ входить у список found_urls
        if found_urls:
            query_deactivate = """
                UPDATE active_proxies
                SET is_active = FALSE,
                    last_checked_at = NOW()
                WHERE url != ALL(%s) 
                AND is_active = TRUE; -- Оптимізація: чіпаємо тільки тих, хто був активним
            """
            # Важливо: передаємо список як один параметр (Postgres array)
            cursor.execute(query_deactivate, (found_urls,))
            
            # Отримуємо кількість вимкнених (для логів)
            deactivated_count = cursor.rowcount
            logger.info(f"💤 Deactivated {deactivated_count} proxies that disappeared from the list.")

        conn.commit()
        logger.info(f"💾 Active pool synchronized: {len(db_rows)} active proxies.")

    update_proxy_pool()

proxy_rotator()