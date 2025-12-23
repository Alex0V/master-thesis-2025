import json
from datetime import datetime
from airflow.decorators import dag, task
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.providers.amazon.aws.hooks.s3 import S3Hook

# Використовуємо ID, які ми прописали в docker-compose -> airflow-init
PG_CONN_ID = "recipe_db_postgres"
S3_CONN_ID = "minio_s3_storage"
BUCKET_NAME = "recipe-test-data"

@dag(
    dag_id="test_recipes_infrastructure",
    start_date=datetime(2023, 1, 1),
    schedule=None, # Запуск вручну
    catchup=False,
    tags=["test", "recipes"]
)
def test_infrastructure():

    @task
    def check_postgres_connection():
        """
        1. Підключається до recipe_db.
        2. Створює таблицю.
        3. Додає тестовий запис.
        """
        try:
            pg_hook = PostgresHook(postgres_conn_id=PG_CONN_ID)
            
            # Створюємо таблицю
            pg_hook.run("""
                CREATE TABLE IF NOT EXISTS test_recipes (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100),
                    status VARCHAR(50),
                    created_at TIMESTAMP DEFAULT NOW()
                );
            """)
            
            # Вставляємо дані
            pg_hook.run("""
                INSERT INTO test_recipes (name, status) 
                VALUES ('Test Borscht', 'Draft');
            """)
            
            print("✅ Postgres: Таблиця створена, дані записані.")
            return "Success"
            
        except Exception as e:
            print(f"❌ Postgres Error: {e}")
            raise e

    @task
    def check_minio_connection(prev_task_status):
        """
        1. Читає дані з Postgres (щоб перевірити читання).
        2. Зберігає їх у MinIO.
        """
        try:
            # Читаємо з БД
            pg_hook = PostgresHook(postgres_conn_id=PG_CONN_ID)
            records = pg_hook.get_records("SELECT * FROM test_recipes ORDER BY id DESC LIMIT 1;")
            record = records[0]
            
            data_to_save = {
                "id": record[0],
                "recipe": record[1],
                "status": record[2],
                "timestamp": str(record[3])
            }
            
            # Пишемо в MinIO
            s3_hook = S3Hook(aws_conn_id=S3_CONN_ID)
            
            if not s3_hook.check_for_bucket(BUCKET_NAME):
                s3_hook.create_bucket(BUCKET_NAME)
                
            file_name = f"test_recipe_{datetime.now().strftime('%H%M%S')}.json"
            
            s3_hook.load_string(
                string_data=json.dumps(data_to_save, indent=4),
                key=file_name,
                bucket_name=BUCKET_NAME,
                replace=True
            )
            
            print(f"✅ MinIO: Файл {file_name} збережено.")
            
        except Exception as e:
            print(f"❌ MinIO Error: {e}")
            raise e

    # Запускаємо послідовно
    status = check_postgres_connection()
    check_minio_connection(status)

test_infrastructure()