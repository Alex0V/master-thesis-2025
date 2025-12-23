-- ============================================================
-- 1. ТАБЛИЦЯ КОНФІГУРАЦІЇ (Block A5)
-- Глобальні налаштування алгоритму рекомендацій
-- ============================================================
CREATE TABLE IF NOT EXISTS system_config (
    key_name VARCHAR(50) PRIMARY KEY,
    value_num DECIMAL(10, 2) NOT NULL,
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Наповнення базовими вагами (Seed Data)
INSERT INTO system_config (key_name, value_num, description) VALUES 
    ('holiday_base_score', 100.00, 'Базовий бал для свят (множиться на coeff свята)'),
    ('seasonal_bonus',      50.00, 'Бонус за сезонність'),
    ('preference_match',    30.00, 'Бонус за збіг з positive_tags'),
    ('penalty_avoid',    -1000.00, 'Штраф за збіг з negative_tags або hard filters'),
    ('min_score_show',      10.00, 'Поріг показу рецепта в рекомендаціях')
ON CONFLICT (key_name) DO UPDATE 
SET value_num = EXCLUDED.value_num;

-- ============================================================
-- 2. ТАБЛИЦЯ КОРИСТУВАЧІВ (Block A2)
-- Включає Auth, Persona, Hard Filters та Soft Preferences
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    -- AUTH & TECH
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    is_superuser BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- PERSONA
    family_size INT DEFAULT 1,
    cooking_skill_level INT DEFAULT 1, -- 1=Novice, 2=Amateur, 3=Chef

    diets JSONB DEFAULT '[]'::jsonb,

    -- SOFT PREFERENCES (Детальні налаштування)
    -- Зберігаємо масиви рядків: ["М'ясні страви", "Свинина", "Борщ"]
    -- Алгоритм шукатиме збіги і в тегах (категорії), і в інгредієнтах (продукти)
    
    positive_tags JSONB DEFAULT '[]'::jsonb, -- Те, що любимо (+30 балів)
    negative_tags JSONB DEFAULT '[]'::jsonb  -- Те, що не любимо (-30 балів)

);

CREATE INDEX idx_users_email ON users(email);

-- ============================================================
-- 3. ТАБЛИЦЯ УЛЮБЛЕНИХ (Favorites)
-- Зв'язок Many-to-Many
-- ============================================================
CREATE TABLE IF NOT EXISTS favorites (
    user_id INT NOT NULL,
    recipe_id INT NOT NULL,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (user_id, recipe_id),

    CONSTRAINT fk_favorites_user 
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_favorites_recipe 
        FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE CASCADE
);

CREATE INDEX idx_favorites_user_added ON favorites(user_id, added_at DESC);
CREATE INDEX idx_favorites_recipe ON favorites(recipe_id);




-- 1. Оновлюємо таблицю користувачів (якщо вона вже є)
-- Робимо пароль необов'язковим (для Google) і додаємо статус верифікації
ALTER TABLE users ALTER COLUMN hashed_password DROP NOT NULL;
ALTER TABLE users ADD COLUMN is_verified BOOLEAN DEFAULT FALSE;

-- 2. Створюємо окрему таблицю для токенів (для мульти-девайс підтримки)
CREATE TABLE IF NOT EXISTS refresh_tokens (
    id SERIAL PRIMARY KEY,
    token VARCHAR(255) UNIQUE NOT NULL,
    expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc'),
    user_id INTEGER NOT NULL,
    
    CONSTRAINT fk_refresh_token_user
        FOREIGN KEY (user_id)
        REFERENCES users (id)
        ON DELETE CASCADE -- Видалили юзера -> зникли всі його сесії
);

CREATE INDEX IF NOT EXISTS idx_refresh_tokens_token ON refresh_tokens(token);