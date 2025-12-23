from datetime import datetime
from airflow.decorators import dag, task
from airflow.providers.postgres.hooks.postgres import PostgresHook

PG_CONN_ID = "recipe_db_postgres"

@dag(
    dag_id="0_setup_db_schema",
    start_date=datetime(2023, 1, 1),
    schedule=None,
    catchup=False,
    tags=["setup", "db_schema"]
)
def setup_schema_dag():

    @task
    def create_tables():
        pg_hook = PostgresHook(postgres_conn_id=PG_CONN_ID)
        
        # -------------------------------------------------------
        # 1. ТАБЛИЦЯ КАТЕГОРІЙ (Сніданки, Перші страви...)
        # -------------------------------------------------------
        pg_hook.run("""
            CREATE TABLE IF NOT EXISTS categories (
                id SERIAL PRIMARY KEY,
                title VARCHAR(255) UNIQUE NOT NULL,
                slug VARCHAR(255) UNIQUE NOT NULL
            );
        """)

        print("Таблиця 'categories' готова.")

        # -------------------------------------------------------
        # 2. ТАБЛИЦЯ РЕЦЕПТІВ
        # -------------------------------------------------------
        pg_hook.run("""
            CREATE TABLE IF NOT EXISTS recipes (
                id SERIAL PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                slug VARCHAR(255) UNIQUE NOT NULL, -- для URL у додатку
                
                -- Якщо категорію видалять, рецепт залишиться (SET NULL)
                category_id INT REFERENCES categories(id) ON DELETE SET NULL,
                    
                -- Метадані джерела
                original_url TEXT,
                image_s3_path VARCHAR(255),     -- Шлях у MinIO
                portions_num DECIMAL(10,2),     -- Кількість порцій
                prep_time_min INT,              -- Час підготовки (хв)
                cook_time_min INT,              -- Час готування (хв)
                
                -- Інструкції приготування (Кроки)
                -- Зберігаємо як JSONB: [{"step": 1, "text": "..."}, {"step": 2...}]
                instructions JSONB,
                
                parsed_at TIMESTAMP DEFAULT NOW(),   -- коли спарсено

                CONSTRAINT unique_source_url UNIQUE (original_url)
            );
                    
            ALTER TABLE recipes ADD COLUMN IF NOT EXISTS difficulty SMALLINT DEFAULT 1; -- 1=Easy, 2=Medium, 3=Hard
        """)

        print("Таблиця 'recipes' готова.")

        # -------------------------------------------------------
        # 3. ТАБЛИЦЯ НУТРІЄНТІВ ДЛЯ ОДНІЄЇ ПОРЦІЇ (1 до 1)
        # -------------------------------------------------------
        pg_hook.run("""
            CREATE TABLE IF NOT EXISTS nutrition_info (
                -- Якщо рецепт видалять, нутрієнти теж зникнуть (CASCADE)
                recipe_id INT PRIMARY KEY REFERENCES recipes(id) ON DELETE CASCADE,
                calories DECIMAL(10,2), -- ккал
                proteins DECIMAL(10,2), -- білки
                fats DECIMAL(10,2),     -- жири
                carbs DECIMAL(10,2)     -- вуглеводи
            );
        """)

        print("Таблиця 'nutrition_info' готова.")

        # -------------------------------------------------------
        # 4. ДОВІДНИК ПРОДУКТІВ (Словник; унікальні назви: "Морква", "Сіль", "Борошно")
        # -------------------------------------------------------
        pg_hook.run("""
            CREATE TABLE IF NOT EXISTS products (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) UNIQUE NOT NULL, -- "морква", "філе куряче"
                slug VARCHAR(255) UNIQUE NOT NULL, -- для URL у додатку
                
                image_s3_path VARCHAR(255),     -- Шлях у MinIO
                original_url TEXT UNIQUE,
                    
                calories_per_100g DECIMAL(10,2),
                proteins_per_100g DECIMAL(10,2),
                fats_per_100g DECIMAL(10,2),
                carbs_per_100g DECIMAL(10,2),
                
                parsed_at TIMESTAMP DEFAULT NOW()   -- коли спарсено
            );
                    
            ALTER TABLE products ADD COLUMN IF NOT EXISTS seasonality INT[];  -- сезонність, місяці коли найбільш популярний 
                    
            -- GIN для миттєвого пошуку по сезонах
            -- Це дозволить робити миттєві запити типу "Дай продукти, доступні у Вересні"
            -- (WHERE seasonality @> '{9}')
            CREATE INDEX IF NOT EXISTS idx_products_seasonality ON products USING GIN (seasonality);

            -- B-Tree для швидкого з'єднання з чергою по URL
            CREATE INDEX IF NOT EXISTS idx_products_original_url ON products(original_url);
        """)

        print("Таблиця 'products' готова.")

        # -------------------------------------------------------
        # 5. ЗВ'ЯЗОК (РЕЦЕПТ <-> ІНГРЕДІЄНТИ; Зберігає: У якому рецепті, у якій секції, скільки продукту)
        # -------------------------------------------------------
        pg_hook.run("""
            CREATE TABLE IF NOT EXISTS recipe_ingredients (
                id SERIAL PRIMARY KEY,
                
                -- Видаляємо зв'язок, якщо видалили рецепт
                recipe_id INT REFERENCES recipes(id) ON DELETE CASCADE,
                -- Забороняємо видаляти продукт, якщо він використовується в рецептах
                product_id INT REFERENCES products(id),
                
                section_name VARCHAR(100) DEFAULT 'Основне',    -- Напр. "Для тіста"
                
                amount DECIMAL(10, 2),                          -- кількість
                unit VARCHAR(20),                               -- міра, наприклад, 'г', 'мл', 'фунти' 'шт', 'ч.л.', тощо
                is_optional BOOLEAN DEFAULT FALSE,
                -- Унікальність: в одній секції рецепта продукт не має дублюватися
                UNIQUE(recipe_id, product_id, section_name)
            );
        """)
        print("Таблиця 'recipe_ingredients' готова.")
        # 6. черга для інгрідієнтів 
        pg_hook.run("""
            CREATE TABLE IF NOT EXISTS product_queue (
                url TEXT PRIMARY KEY,
                status VARCHAR(20) DEFAULT 'NEW',
                attempts INT DEFAULT 0,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_product_queue_status ON product_queue(status);
        """)
        print("Таблиця 'product_queue' готова.")
        # 7. черга для рецептів 
        pg_hook.run("""
            CREATE TABLE IF NOT EXISTS recipe_queue (
                url TEXT PRIMARY KEY,
                status VARCHAR(60) DEFAULT 'NEW', -- NEW, PROCESSING, DONE, ERROR
                attempts INT DEFAULT 0,
                priority INT DEFAULT 10,          -- Можна додати пріоритет (нові вище)
                error_message TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            );
            -- Індекс для швидкого пошуку задач
            CREATE INDEX IF NOT EXISTS idx_recipe_queue_status ON recipe_queue(status);
        """)
        print("Таблиця 'recipe_queue' готова.")
        
        # 8. Таблиця для проксі
        pg_hook.run("""
            CREATE TABLE IF NOT EXISTS active_proxies (
                url TEXT PRIMARY KEY,
                protocol VARCHAR(10) DEFAULT 'http',
                speed_ms INT,
                is_active BOOLEAN DEFAULT TRUE,
                last_checked_at TIMESTAMP DEFAULT NOW(),
                created_at TIMESTAMP DEFAULT NOW()
            );
            
            CREATE INDEX IF NOT EXISTS idx_proxies_priority 
            ON active_proxies(speed_ms) 
            WHERE is_active = TRUE;
        """)
        print("Таблиця 'active_proxies' готова.")

        # 9. Таблиця для тимчасово забанених по ip проксі
        pg_hook.run("""
            CREATE TABLE IF NOT EXISTS proxy_bans (
                proxy_url TEXT NOT NULL,
                provider_name TEXT NOT NULL,       -- Наприклад: 'gpt-4'
                banned_until TIMESTAMP,         -- Коли знімається бан
                created_at TIMESTAMP DEFAULT NOW(),
                
                -- Унікальний ключ: один запис для пари "проксі + модель"
                PRIMARY KEY (proxy_url, provider_name)
            );

            -- Індекс для швидкого пошуку
            CREATE INDEX IF NOT EXISTS idx_bans_provider 
            ON proxy_bans(proxy_url, provider_name);
        """)
        print("Таблиця 'proxy_bans' готова.")

        # 10. Таблиця довідник тегів
        pg_hook.run("""
            CREATE TABLE IF NOT EXISTS tags (
                id SERIAL PRIMARY KEY,
                name TEXT UNIQUE NOT NULL
            );
                    
            ALTER TABLE tags ADD COLUMN IF NOT EXISTS type VARCHAR(50); -- 'dish_type', 'cuisine', 'diet', 'occasion'
            -- Індекс, щоб меню на сайті ("Показати всі кухні") літало
            CREATE INDEX IF NOT EXISTS idx_tags_type ON tags(type);
        """)
        print("Таблиця 'tags' готова.")

        # 11. Таблиця зв'язків (Багато-до-багатьох)
        pg_hook.run("""
            CREATE TABLE IF NOT EXISTS product_tags (
                product_id INT REFERENCES products(id) ON DELETE CASCADE,
                tag_id INT REFERENCES tags(id) ON DELETE CASCADE,
                PRIMARY KEY (product_id, tag_id)
            );
        """)
        print("Таблиця 'product_tags' готова.")

        # 12. Таблиця зв'язків RECIPE_TAGS
        pg_hook.run("""
            CREATE TABLE IF NOT EXISTS recipe_tags (
                recipe_id INT REFERENCES recipes(id) ON DELETE CASCADE,
                tag_id INT REFERENCES tags(id) ON DELETE CASCADE,
                PRIMARY KEY (recipe_id, tag_id)
            );
            
            -- Індекс для фасетного пошуку ("Знайти всі Італійські (tag_id=X) рецепти")
            CREATE INDEX IF NOT EXISTS idx_recipe_tags_tag ON recipe_tags(tag_id);
        """)
        print("Таблиця 'recipe_tags' створена.")

        # 13. Таблиця СВЯТ (Holiday Calendar)
        pg_hook.run("""
            CREATE TABLE IF NOT EXISTS holiday_definitions (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,       -- Назва для адмінки ("Різдво")
                
                -- Період дії свята
                start_month INT NOT NULL,
                start_day INT NOT NULL,
                end_month INT NOT NULL,
                end_day INT NOT NULL,
                
                -- Посилання на тег, який треба "бустити" в цей період
                tag_id INT REFERENCES tags(id) ON DELETE SET NULL,
                coeff DECIMAL(3,1) DEFAULT 2.0    -- Сила рекомендації
            );
            
            -- Це дозволить базі швидко знаходити "Всі свята, що починаються в 1-му місяці"
            CREATE INDEX IF NOT EXISTS idx_holiday_start 
            ON holiday_definitions(start_month, start_day);
        """)
        print("Таблиця 'holiday_definitions' створена.")

        # # 14. Заповнення таблиць з святами та тегами для них
        # # 14.1. ТЕГИ (Tags) - Повний спектр
        # pg_hook.run("""
        #     INSERT INTO tags (name, type) VALUES 
        #     -- Зимові традиції
        #     ('Різдво', 'occasion'),
        #     ('Новий Рік', 'occasion'),
        #     ('Щедрий Вечір', 'occasion'), 
        #     ('Водохреща', 'occasion'),
        #     ('День Миколая', 'occasion'),
            
        #     -- Світські та Популярні
        #     ('День Закоханих', 'occasion'),   -- Романтика
        #     ('Свято Весни', 'occasion'),      -- 8 березня (легкі страви)
        #     ('Хелловін', 'occasion'),         -- Страви з гарбуза
        #     ('День Знань', 'occasion'),       -- 1 вересня (торти, дитяче меню)
            
        #     -- Весняно-Літні традиції
        #     ('Масляна', 'occasion'),          -- Млинці
        #     ('Великдень', 'occasion'),        -- Паска
        #     ('Івана Купала', 'occasion'),
            
        #     -- Спаси (Серпень)
        #     ('Медовий Спас', 'occasion'),
        #     ('Яблучний Спас', 'occasion'),
        #     ('Горіховий Спас', 'occasion'),
            
        #     -- Патріотичні
        #     ('День Незалежності', 'occasion'),
        #     ('Покрова', 'occasion'),
            
        #     -- Сезонні активності (Тривалі періоди)
        #     ('Великий Піст', 'occasion'),     -- або 'diet'
        #     ('Різдвяний Піст', 'occasion'),
        #     ('Сезон консервації', 'occasion'), -- Серпень-Вересень (Маринади)
        #     ('Пікнік та Гриль', 'occasion')    -- Травневі, День Конституції тощо
            
        #     ON CONFLICT (name) DO UPDATE SET type = EXCLUDED.type;
        # """)

        # # 14.2. КАЛЕНДАР (Holiday Definitions)
        # # Увага: Для рухомих свят (Великдень, Масляна) дати тут орієнтовні на 2025 рік.
        # # Їх треба оновлювати скриптом раз на рік.
        # pg_hook.run("""
            # INSERT INTO holiday_definitions (name, start_month, start_day, end_month, end_day, tag_id, coeff)
            # VALUES 
            # -- === ЗИМА ===
            # ('Миколая', 12, 5, 12, 6, (SELECT id FROM tags WHERE name='День Миколая'), 3.5),
            # ('Різдво (Святвечір)', 12, 24, 12, 26, (SELECT id FROM tags WHERE name='Різдво'), 5.0),
            # ('Новий Рік', 12, 28, 1, 3, (SELECT id FROM tags WHERE name='Новий Рік'), 4.5),
            # ('Щедрий Вечір (Маланка)', 12, 31, 1, 1, (SELECT id FROM tags WHERE name='Щедрий Вечір'), 3.5),
            # ('Водохреща', 1, 5, 1, 7, (SELECT id FROM tags WHERE name='Водохреща'), 3.0),
            # ('День Закоханих', 2, 12, 2, 15, (SELECT id FROM tags WHERE name='День Закоханих'), 4.0),

            # -- === ВЕСНА ===
            # ('Свято Весни (8 Березня)', 3, 6, 3, 9, (SELECT id FROM tags WHERE name='Свято Весни'), 4.0),
            # ('Масляна', 2, 24, 3, 2, (SELECT id FROM tags WHERE name='Масляна'), 4.0), -- 2025 рік
            # ('Великий Піст', 3, 3, 4, 19, (SELECT id FROM tags WHERE name='Великий Піст'), 2.0), -- 2025 рік
            # ('Великдень', 4, 18, 4, 25, (SELECT id FROM tags WHERE name='Великдень'), 5.0), -- 2025 рік
            # ('Сезон Пікніків (Травневі)', 5, 1, 5, 15, (SELECT id FROM tags WHERE name='Пікнік та Гриль'), 3.0),

            # -- === ЛІТО ===
            # ('День Конституції (Пікнік)', 6, 27, 6, 29, (SELECT id FROM tags WHERE name='Пікнік та Гриль'), 3.0),
            # ('Івана Купала', 7, 6, 7, 7, (SELECT id FROM tags WHERE name='Івана Купала'), 2.5),
            # ('Маковія (Медовий Спас)', 8, 1, 8, 2, (SELECT id FROM tags WHERE name='Медовий Спас'), 3.0),
            # ('Яблучний Спас', 8, 5, 8, 7, (SELECT id FROM tags WHERE name='Яблучний Спас'), 3.0),
            # ('Горіховий Спас', 8, 15, 8, 17, (SELECT id FROM tags WHERE name='Горіховий Спас'), 3.0),
            # ('День Незалежності', 8, 23, 8, 25, (SELECT id FROM tags WHERE name='День Незалежності'), 3.5),

            # -- === ОСІНЬ ===
            # ('1 Вересня (День Знань)', 8, 30, 9, 2, (SELECT id FROM tags WHERE name='День Знань'), 3.0),
            # ('Сезон Консервації', 8, 20, 9, 25, (SELECT id FROM tags WHERE name='Сезон консервації'), 2.5),
            # ('Покрова', 9, 30, 10, 2, (SELECT id FROM tags WHERE name='Покрова'), 3.0),
            # ('Хелловін (Гарбуз)', 10, 25, 11, 1, (SELECT id FROM tags WHERE name='Хелловін'), 3.5),
            # ('Різдвяний Піст', 11, 15, 12, 24, (SELECT id FROM tags WHERE name='Різдвяний Піст'), 1.5)

            # ON CONFLICT DO NOTHING;
        # """)
        print("Таблиці успішно створено")
        


    create_tables()

setup_schema_dag()