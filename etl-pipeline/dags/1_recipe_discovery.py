import requests
import time
import random
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from airflow.decorators import dag, task
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.operators.trigger_dagrun import TriggerDagRunOperator

# --- КОНФІГУРАЦІЯ ---
PG_CONN_ID = "recipe_db_postgres"
# TARGET_DAG_ID = "2_recipe_processor" # Наступний у ланцюжку

BASE_URL = "https://shuba.life/recipes?page={}"
PAGES_TO_CRAWL = 2089  # Загальна кількість сторінок
BATCH_SIZE = 20        # Скільки сторінок обробляє одна задача (Task)

@dag(
    dag_id="1_recipe_discovery",
    start_date=datetime(2023, 1, 1),
    schedule=None,
    catchup=False,
    tags=["discovery", "crawler"],
    max_active_tasks=3 # Не більше 3 сторінок одночасно (ввічливість)
)
def discovery_dag():

    @task
    def get_page_chunks():
        """
        Генерує пакети сторінок.
        Повертає [[1,2], [3,4]...]
        """
        all_pages = range(1, PAGES_TO_CRAWL + 1)
        
        # Розбиваємо на шматки по BATCH_SIZE
        chunks = [list(all_pages[i:i + BATCH_SIZE]) for i in range(0, len(all_pages), BATCH_SIZE)]
        
        print(f"Розбито {PAGES_TO_CRAWL} сторінок на {len(chunks)} пакетів по {BATCH_SIZE} шт.")
        return chunks

    @task(
        retries=5, 
        retry_delay=timedelta(minutes=1) # Якщо впаде, чекаємо 1 хв перед повтором
    )
    def crawl_page(page_nums: list) -> list:
        """
        отримує список номерів сторінок (напр. [1, 2... 20]) і скануємо їх послідовно.
        """
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
        }
        batch_links = []

        print(f"Починаємо обробку пакету: сторінки {min(page_nums)} - {max(page_nums)}")

        for page_num in page_nums:
            url = BASE_URL.format(page_num)
            # Пауза між сторінками всередині одного батчу (імітація людини)
            time.sleep(random.uniform(2.0, 5.0))
            try:
                response = requests.get(url, headers=headers, timeout=15)
                
                if response.status_code == 404:
                    print(f"Сторінка {page_num} не існує (404).")
                    return []
                
                if response.status_code != 200:
                    print(f"Помилка {response.status_code}")
                    return []

                soup = BeautifulSoup(response.content, 'html.parser')
                
                # 1. Знаходимо всі картки рецептів
                cards = soup.find_all('article', class_='c-primary-card')
                if not cards:
                    # Фоллбек: іноді бувають прості картки (якщо дизайн змішаний)
                    cards = soup.find_all('article', class_='c-simple-card')

                page_count = 0
                for card in cards:
                    try:
                        # 2. Шукаємо заголовок з посиланням
                        # Клас має містити ...card__title
                        title_block = card.find('h2', class_=lambda x: x and 'card__title' in x)
                        
                        if not title_block:
                            continue
                            
                        link = title_block.find('a')
                        if not link:
                            continue
                        
                        href = link.get('href')
                        
                        # 3. Валідація та нормалізація
                        if href:
                            # Фільтрація: беремо тільки рецепти і відео
                            if "/recipes/" in href or "/videos/" in href:
                                batch_links.append(href)
                                page_count += 1
                                
                    except Exception as card_err:
                        print(f"Помилка парсингу картки: {card_err}")
                        continue
                print(f"Знайдено {page_count} посилань.")
            except Exception as e:
                print(f"Помилка на сторінці {page_num}: {e}")
                continue
        print(f"Пакет завершено. Всього зібрано {len(batch_links)} унікальних посилань.")
        return batch_links

    @task
    def filter_and_queue(urls_batch: list):
        """
        Фільтрує URL (чи є в recipes) і додає нові в recipe_queue.
        """
        if not urls_batch:
            return

        pg_hook = PostgresHook(postgres_conn_id=PG_CONN_ID)
        conn = pg_hook.get_conn()
        cursor = conn.cursor()

        # 1. ДЕДУПЛІКАЦІЯ (Історія)
        # Перевіряємо, чи ми ВЖЕ успішно спарсили цей рецепт раніше
        # (Дивимось в таблицю recipes, а не в чергу)
        placeholders = ','.join(['%s'] * len(urls_batch))
        cursor.execute(f"SELECT original_url FROM recipes WHERE original_url IN ({placeholders})", tuple(urls_batch))
        
        existing_in_db = {row[0] for row in cursor.fetchall()}
        
        # Залишаємо тільки ті, яких немає в базі
        new_urls = [u for u in urls_batch if u not in existing_in_db]

        if not new_urls:
            print("Всі знайдені рецепти вже оброблені раніше.")
            return

        print(f"Додаємо в чергу {len(new_urls)} нових завдань...")

        # 2. ВСТАВКА В ЧЕРГУ
        # Використовуємо ON CONFLICT DO NOTHING.
        # Це означає: якщо URL вже є в черзі (наприклад, статус ERROR або NEW), ми його не чіпаємо.
        # Ми додаємо тільки те, чого немає ні в базі, ні в черзі.
        
        args_list = [(u,) for u in new_urls]
        query = """
            INSERT INTO recipe_queue (url, status, created_at) 
            VALUES (%s, 'NEW', NOW())
            ON CONFLICT (url) DO NOTHING;
        """
        cursor.executemany(query, args_list)
        conn.commit()
        
        print(f"Черга оновлена.")

    # --- ТРИГЕР ---
    # Запускає наступний DAG (Process), коли цей закінчить роботу
    # trigger_next = TriggerDagRunOperator(
    #     task_id="trigger_processor",
    #     trigger_dag_id=TARGET_DAG_ID,
    #     wait_for_completion=False 
    # )

    # --- ПОТІК ВИКОНАННЯ ---
    chunks = get_page_chunks()
    
    # 1. Розпаралелений кроулінг (Map)
    extracted_urls = crawl_page.expand(page_nums=chunks)
    
    # 2. Фільтрація і запис (Map)
    queued = filter_and_queue.expand(urls_batch=extracted_urls)
    
    # 3. Після завершення всіх записів - тригер
    # queued >> trigger_next

discovery_dag()