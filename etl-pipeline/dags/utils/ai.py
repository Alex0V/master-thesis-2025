import re
import requests
import json
import logging
import time
import random
import logging
from airflow.providers.postgres.hooks.postgres import PostgresHook
# Імпортуємо всі можливі помилки з'єднання
from requests.exceptions import (
    ProxyError, 
    ConnectTimeout, 
    ReadTimeout, 
    ConnectionError, 
    SSLError,
    ChunkedEncodingError
)

PG_CONN_ID = "recipe_db_postgres"

# URL G4F сервера
AI_URL = "http://gpt4free:8080/v1/chat/completions"

# строго модель-провайдер, авто-вибір не кладемо бо авто вибере забанене проксі для даного провайдера,
# і лише коли отримаємо відповідь з повторним повідомленням про бан знову запишемо в бд і так по колу)
AI_CONFIGS = [
    # {"model": "gpt-4", "provider": "Yqcloud"}, # працює але не надійна
    # {"model": "gpt-4", "provider": "WeWordle"},# працює але не надійна

    {"model": "deepseek-ai/DeepSeek-V3", "provider": "DeepInfra"},
    {"model": "openai/gpt-oss-120b", "provider": "DeepInfra"},
    {"model": "deepseek-ai/DeepSeek-V3", "provider": "DeepInfra"},
    {"model": "deepseek-ai/DeepSeek-V3", "provider": "DeepInfra"},
    {"model": "deepseek-ai/DeepSeek-V3", "provider": "DeepInfra"},
]

# ЄДИНИЙ СПИСОК МАРКЕРІВ БАНУ (в нижньому регістрі)
# Якщо хоч одне з цих слів є у відповіді (навіть при 200 OK або 403) -> БАНИМО.
BAN_MARKERS = [
    # Китайські (WeWordle)
    "请求过多", "限流", 
    # Стандартні
    "access denied", "rate limit reached", "too many requests", "forbidden", "banned",
    # Cloudflare / WAF
    "just a moment...", "verify you are human", "challenge", 
    "cloudflare", "firewall", "security", "traffic from your network",
]

# Налаштування логера
logger = logging.getLogger("airflow.task")   

def get_best_proxy(target_provider: str):
    """
    Бере проксі, який:
    1. Живий (is_active = True)
    2. НЕ забанений для провайдера (provider_name)
    """

    if not target_provider:
        return None # Без провайдера не працюємо
    
    try:
        pg_hook = PostgresHook(postgres_conn_id=PG_CONN_ID)
        conn = pg_hook.get_conn()
        cursor = conn.cursor()
        
        # SQL MAGIC: LEFT JOIN або NOT EXISTS
        # Шукаємо проксі, якого НЕМАЄ в таблиці банів для цієї моделі (або час бану вийшов)
        query = """
            SELECT p.url 
            FROM active_proxies p
            LEFT JOIN proxy_bans b 
                ON p.url = b.proxy_url 
                AND b.provider_name = %s  -- Перевіряємо конкретного провайдера
                AND b.banned_until > NOW()
            WHERE p.is_active = TRUE 
              AND b.proxy_url IS NULL     -- Бану немає
              AND p.speed_ms < 5000       -- Тільки швидкі
            ORDER BY RANDOM()
            LIMIT 1;
        """
        cursor.execute(query, (target_provider,))
        row = cursor.fetchone()
        
        if row:
            return row[0]
            
    except Exception as e:
        logger.warning(f"DB Error: {e}")
    return None

def ban_proxy_for_provider(proxy_url: str, provider: str, hours: int = 1):
    """
    Записує в базу: 'Цей IP не пускає до WeWordle'
    """
    if not proxy_url or not provider: return
    try:
        pg_hook = PostgresHook(postgres_conn_id=PG_CONN_ID)
        conn = pg_hook.get_conn()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO proxy_bans (proxy_url, provider_name, banned_until)
            VALUES (%s, %s, NOW() + INTERVAL '%s hours')
            ON CONFLICT (proxy_url, provider_name) 
            DO UPDATE SET banned_until = EXCLUDED.banned_until;
        """, (proxy_url, provider, hours))
        
        conn.commit()
        logger.warning(f"🚫 BANNED {proxy_url} for provider '{provider}' ({hours}h).")
    except Exception as e:
        logger.error(f"Ban failed: {e}")



def ask_ai_json(prompt: str):
    """
    Відправляє запит до випадкової моделі з MODEL_POOL.
    Виконує retry доти, поки не отримає валідний JSON.
    Повертає Python-об'єкт (dict або list) або None, якщо зупинено вручну.
    """

    headers = {"Content-Type": "application/json"}

    # Додаємо інструкцію для моделі: тільки JSON
    json_prompt = prompt + " Повернути лише JSON. Жодного Markdown, ніяких пояснень."
    
    while True:
        # 1. Вибираємо КОНКРЕТНУ пару (Модель + Провайдер)
        config = random.choice(AI_CONFIGS)
        AI_MODEL = config["model"]
        AI_PROVIDER = config["provider"]

        logger.info(f"🔄 Trying model: {AI_MODEL}, provider: {AI_PROVIDER}")

        # 2. Шукаємо проксі, який НЕ в бані саме для цієї моделі
        current_proxy = get_best_proxy(target_provider=AI_PROVIDER)
        
        # Якщо всі проксі забанені для цієї моделі - пробуємо іншу модель
        if not current_proxy:
            logger.warning(f"⚠️ No clean proxies for {AI_MODEL}. Switching model...")
            time.sleep(1) # Трохи чекаємо
            continue

        payload = {
        "model": AI_MODEL,
        "provider": AI_PROVIDER,
        "messages": [{"role": "user", "content": json_prompt}],
        "stream": False,
        "proxy": current_proxy
        }

        try:
            # Тайм-аут: 
            # 8 сек: якщо проксі не конектиться - кидаємо ConnectTimeout (і йдемо на next proxy)
            # 20 сек: якщо AI тупить - кидаємо ReadTimeout
            response = requests.post(AI_URL, json=payload, headers=headers, timeout=(15, 60))
            logger.info(f"Status Code: {response.status_code}")
            logger.info(f"RESPONSE {response.json()}")
            # Переводимо текст в нижній регістр один раз для перевірки
            response_text_lower = response.text.lower()
            # --- 1. ПЕРЕВІРКА НА БАН (Status 403/429 або Text Marker) ---
            # Логіка: Якщо статус підозрілий АБО в тексті є маркер бану
            is_ban = False
            
            # а) 429 завжди бан
            if response.status_code == 429:
                is_ban = True
            
            # б) 403 або 200 - перевіряємо текст на наявність маркерів
            elif response.status_code in [200, 403]:
                if any(marker in response_text_lower for marker in BAN_MARKERS):
                    is_ban = True
            
            # Якщо це бан - блокуємо
            if is_ban:
                logger.warning(f"BAN DETECTED ({response.status_code}) from {AI_PROVIDER}. Block pair.")
                ban_proxy_for_provider(current_proxy, AI_PROVIDER, hours=1)
                continue # NEXT TRY
            
            # --- ОБРОБКА ІНШИХ ПОМИЛОК API ---
            if response.status_code != 200:
                logger.error(f"❌ Error Response: {response.text}")
                logger.info("⏳ Waiting 2s before retry...")
                time.sleep(2)
                continue
            
            try:
                # Беремо контент
                res_json = response.json()
                if 'choices' in res_json:
                    raw_content = res_json['choices'][0]['message']['content']
                else:
                    raw_content = str(res_json)

                # Чистимо сміття
                clean_text = raw_content.replace("```json", "").replace("```", "").strip()
                
                # Витягаємо весь JSON (масив або об'єкт)
                match = re.search(r'(\{.*\}|\[.*\])', clean_text, re.DOTALL)
                if not match:
                    logger.info("❌ No JSON found in response")

                clean_text = match.group(1)

                data = json.loads(clean_text)
                
                if not data:
                    logger.warning(f"⚠️ Empty JSON received from {AI_PROVIDER}. Retrying...")
                    continue
                logger.info(f"✅ JSON {data} Parsed from {AI_PROVIDER}")
                return data
            except json.JSONDecodeError:
                logger.warning("❌ JSON parse error — retrying...")
                continue
            except Exception:
                continue
        # Цей блок ловить HTTPSConnectionPool, ProxyError, ConnectTimeoutError
        except (ProxyError, ConnectTimeout, ReadTimeout, ConnectionError, SSLError, ChunkedEncodingError) as e:
            # Логуємо, що проксі "мовчить" або перевантажений і йдемо на нове коло.
            # Не витрачаємо час на sleep. Беремо наступний проксі з 300 доступних.
            logger.warning(f"❌ ERROR: {e}. Next!")
            logger.warning(f"⏩ Slow/Dead Proxy: {current_proxy}. Next!")
            continue
        except Exception as e:
            logger.error(f"❌ Connection/Error: {e}")

        logger.info("⏳ Waiting 3s before retry...")
        time.sleep(3)
