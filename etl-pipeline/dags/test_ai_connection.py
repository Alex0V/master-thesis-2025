import random
import time
from airflow.decorators import dag, task
import pendulum
import requests
import json
import logging

# Налаштування логера
logger = logging.getLogger("airflow.task")

default_args = {
    'owner': 'airflow',
    'retries': 0, # Для тесту нам не треба повтори, хочемо бачити помилку одразу
}


MODEL_POOL = [
    "gpt-4",
    # "deepseek-v3",
]
PROVIDER = "PollinationsAI"

URL = "http://gpt4free:8080/v1/chat/completions"

@dag(
    dag_id='test_g4f_integration',
    default_args=default_args,
    description='Тестування зв\'язку з G4F Docker контейнером',
    schedule=None, # Запускаємо тільки вручну
    start_date=pendulum.today('UTC').add(days=-1),
    catchup=False,
    tags=['test', 'g4f']
)
def test_g4f_dag():

    # 1. Простий тест: Чи живий сервер?
    @task
    def ping_ai_server():
        logger.info("--- STARTING PING TEST ---")

    
        # Безкінечний цикл
        while True:

            # 🎲 Рандомна модель
            AI_MODEL = random.choice(MODEL_POOL)
            logger.info(f"🔄 Trying model: {AI_MODEL}")

            payload = {
                "model": AI_MODEL,
                "provider": PROVIDER,
                "messages": [
                    {
                        "role": "user",
                        "content": "Чи розумієш ти український контекст?"
                    }
                ],
                "stream": False
            }

            try:
                response = requests.post(URL, json=payload, timeout=10)
                logger.info(f"Status Code: {response.status_code}")

                if response.status_code == 200:
                    logger.info(f"ALL Raw AI Output: {response.json()}")
                    content = response.json()['choices'][0]['message']['content']
                    logger.info(f"✅ AI Answer ({AI_MODEL}): {content}")
                    return "OK"

                else:
                    logger.error(f"❌ Error Response: {response.text}")

            except Exception as e:
                logger.error(f"❌ Connection failed: {e}")

            logger.info("⏳ Waiting 2s and retrying...")
            time.sleep(2)

    # 2. Складний тест: Чи може він повернути JSON для калорій?
    @task
    def test_json_parsing():
        logger.info("--- STARTING JSON TEST ---")
        
        product_name = "Авокадо хасс"
        
        prompt = (
            f"Напишіть КБЖВ для продукту '{product_name}' на 100г. "
            f"Відповідь має бути ТІЛЬКИ у форматі JSON: "
            f'{{"calories": int, "proteins": float, "fats": float, "carbs": float}}. '
            f"Більше ніякого тексту."
        )

        while True:
            # 🎲 Рандомна модель
            AI_MODEL = random.choice(MODEL_POOL)
            logger.info(f"🔄 Trying model: {AI_MODEL}")

            payload = {
                "model": AI_MODEL,
                "provider": PROVIDER,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "stream": False
            }
            try:
                response = requests.post(URL, json=payload, timeout=5)
                logger.info(f"AI OUT: {response}")

                # ====== STATUS CODE ======
                logger.info(f"Status Code: {response.status_code}")

                if response.status_code != 200:
                    logger.error(f"❌ Error Response: {response.text}")
                    logger.info("⏳ Retrying in 2 seconds...")
                    time.sleep(2)
                    continue

                # ====== VALID 200 ======
                json_response = response.json()
                logger.info(f"ALL Raw AI Output: {json_response}")

                raw_content = json_response['choices'][0]['message']['content']
                logger.info(f"Raw AI Output: {raw_content}")

                # ====== CLEAN MARKDOWN ======
                clean_text = (
                    raw_content
                    .replace("```json", "")
                    .replace("```", "")
                    .strip()
                )

                # Якщо є зайвий текст перед JSON → вирізаємо
                if "{" in clean_text:
                    start = clean_text.find("{")
                    end = clean_text.rfind("}") + 1
                    clean_text = clean_text[start:end]

                # ====== PARSE JSON ======
                data = json.loads(clean_text)

                logger.info(f"Parsed Data ✔: {data}")
                logger.info(f"Calories: {data.get('calories')}")
                return data  # 🎉 УСПІХ

            except json.JSONDecodeError:
                logger.error("❌ JSON parse error — AI повернув сміття. Retrying...")
            except Exception as e:
                logger.error(f"❌ Connection/Error: {e}")

            logger.info("⏳ Retrying in 2 seconds...")
            time.sleep(2)


    # Порядок виконання
    ping_ai_server() >> test_json_parsing()

test_dag = test_g4f_dag()