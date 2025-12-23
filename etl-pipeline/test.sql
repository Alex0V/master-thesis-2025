-- SELECT DISTINCT section_name FROM recipe_ingredients;
-- SELECT * FROM recipe_ingredients WHERE product_id = 8722;
-- SELECT * FROM recipes WHERE id = 17678;
-- SELECT * FROM products WHERE id = 8722;

/*
SELECT jsonb_build_object(
    'recipe_name', r.title,
    'ingredients', (
        SELECT jsonb_agg(
            jsonb_build_object(
                'product_name', p.name,
                'section_name', ri.section_name,
                'amount', ri.amount,
                'unit', ri.unit
            )
        )
        FROM recipe_ingredients ri
        JOIN products p ON p.id = ri.product_id
        WHERE ri.recipe_id = r.id
    )
) AS recipe_json
FROM recipes r;
*/

-- ALTER TABLE recipe_ingredients ADD COLUMN is_optional BOOLEAN DEFAULT FALSE;

/*
SELECT 
    title,
    LENGTH(title) - LENGTH(REPLACE(title, '\u00A0', '')) AS count_nonbreaking_spaces
FROM recipes
WHERE title LIKE '%\u00A0%';
*/

/*
UPDATE recipes
SET title = REGEXP_REPLACE(title, CHR(160), ' ', 'g')
WHERE title LIKE '%' || CHR(160) || '%';
*/
/*
SELECT title
FROM recipes
WHERE title LIKE '%\u00A0%';
*/

/*
SELECT 
    LENGTH('Соковита свинина у винному соусі — швидкий рецепт відбивних') 
    - LENGTH(REGEXP_REPLACE('Соковита свинина у винному соусі — швидкий рецепт відбивних', '\u00A0', '', 'g')) 
    AS count_nonbreaking_spaces;
*/

/*
UPDATE recipes
SET title = REPLACE(title, CHR(160), ' ')
WHERE title LIKE '%' || CHR(160) || '%';
*/

/*
SELECT
	COUNT(*)
FROM
	RECIPES
WHERE
	TITLE LIKE '%\u00A0%';
*/

/*
UPDATE recipe_queue
SET status = 'OPTIONAL_DONE'
WHERE status = 'TAGGING_PROCESSING';



UPDATE product_queue
SET status = 'DONE'
WHERE status = 'ENRICH_ERROR';
*/
-- SELECT * FROM product_queue WHERE status != 'ENRICH_DONE';
-- OPTIONAL_ERROR  OPTIONAL_DONE   OPTIONAL_PROCESSING
-- SELECT * FROM recipe_queue WHERE status != 'TAGGING_DONE';

-- SELECT * FROM active_proxies WHERE is_active = true;
-- SELECT * FROM proxy_bans;

-- SELECT * FROM tags WHERE name LIKE '%ук%';

-- DROP TABLE IF EXISTS product_tags CASCADE;
-- DROP TABLE IF EXISTS tags CASCADE;
/*
-- рецепт-свята
SELECT 
    r.id,
    r.title,
    STRING_AGG(t.name, ', ') as holidays -- Збирає всі свята в один рядок
FROM recipes r
JOIN recipe_tags rt ON r.id = rt.recipe_id
JOIN tags t ON rt.tag_id = t.id
WHERE t.type = 'occasion' --  Фільтруємо ТІЛЬКИ свята
GROUP BY r.id, r.title
ORDER BY r.id DESC;
*/

-- розподіл свято-кількість рецептів
/*
SELECT t.name, COUNT(rt.recipe_id) as count
FROM tags t
JOIN recipe_tags rt ON t.id = rt.tag_id
WHERE t.type = 'product_cat'
GROUP BY t.name
ORDER BY count DESC;
*/
/*
SELECT r.title 
FROM recipes r
LEFT JOIN recipe_tags rt ON r.id = rt.recipe_id
LEFT JOIN tags t ON rt.tag_id = t.id AND t.type = 'occasion'
WHERE t.id IS NULL -- Немає свята
ORDER BY RANDOM()
LIMIT 20;
*/

/*
"Перекус"	"meal_type"
"Обід"	"meal_type"
"Вечеря"	"meal_type"
"Перекцс"	"meal_type"
"Ланч"	"meal_type"
"Святковий стіл"	"meal_type"
"Снітанок"	"meal_type"
"Пікнік"	"meal_type"
"Вечера"	"meal_type"
4846 "На перекус і пікнік: кускус із запеченими овочами" перемістити в 3832	"Перекус"
UPDATE recipe_tags
SET tag_id = 3832  -- ID нового тегу (наприклад, Млинці)
WHERE tag_id = 9086 -- ID старого тегу (наприклад, Десерт)
AND recipe_id = 4846; -- ID конкретного рецепта
*/

--SELECT * FROM recipes WHERE id = 2881;
-- SELECT * FROM recipe_tags WHERE recipe_id = 18562;
-- SELECT * FROM recipe_tags WHERE tag_id = 3897;
-- SELECT * FROM tags WHERE type ILIKE 'occas%';

/*
SELECT
    p.id AS product_id,
    p.name AS product_name,
	p.seasonality AS seasonality,
    STRING_AGG(t.name || ' (' || t.type || ')', ', ' ORDER BY t.name) AS attached_tags
FROM products p
JOIN product_tags pt ON p.id = pt.product_id
JOIN tags t ON pt.tag_id = t.id
GROUP BY p.id, p.name, p.seasonality
ORDER BY p.name
LIMIT 500; -- Обмежте, якщо у вас тисячі продуктів
*/

-- SELECT name, category, base_product FROM products WHERE name LIKE '%Рис%';

/*
-- теги occasion - кількість рецептів
SELECT 
    t.id,
    t.name,
    COUNT(rt.recipe_id) as recipe_count
FROM tags t
JOIN recipe_tags rt ON t.id = rt.tag_id
WHERE t.type = 'cuisine'
GROUP BY t.id, t.name
ORDER BY recipe_count DESC;
*/


-- 																		виправлення неправильно записаних тегів на правильні
DO $$
DECLARE
    -- 👇 НАЛАШТУВАННЯ (Впишіть сюди ваші дані)
    bad_tag_name  TEXT := 'Східна';  -- Ім'я неправильного тегу
    bad_tag_type  TEXT := 'cuisine';             -- Тип неправильного тегу (важливо!)

    good_tag_name TEXT := 'Азійська';      -- Ім'я правильного тегу
    good_tag_type TEXT := 'cuisine';             -- Тип правильного тегу

    -- Змінні для ID (знайдуться автоматично)
    bad_tag_id INT;
    good_tag_id INT;
BEGIN
    -- 1. Знаходимо ID тегів, враховуючи їх ТИП
    SELECT id INTO bad_tag_id FROM tags WHERE name = bad_tag_name AND type = bad_tag_type;
    SELECT id INTO good_tag_id FROM tags WHERE name = good_tag_name AND type = good_tag_type;

    -- Перевірка
    IF bad_tag_id IS NULL THEN
        RAISE EXCEPTION 'Не знайдено поганий тег: "%" (type: %)', bad_tag_name, bad_tag_type;
    END IF;

    IF good_tag_id IS NULL THEN
        RAISE EXCEPTION 'Не знайдено хороший тег: "%" (type: %)', good_tag_name, good_tag_type;
    END IF;

    RAISE NOTICE '🚀 Починаємо злиття: "%" (id: %) -> "%" (id: %)', bad_tag_name, bad_tag_id, good_tag_name, good_tag_id;

    -- 2. ОНОВЛЮЄМО РЕЦЕПТИ (recipe_tags)
    -- Переносимо рецепти на новий тег, ТІЛЬКИ якщо у них його ще немає
    UPDATE recipe_tags
    SET tag_id = good_tag_id
    WHERE tag_id = bad_tag_id
    AND recipe_id NOT IN (
        SELECT recipe_id 
        FROM recipe_tags 
        WHERE tag_id = good_tag_id
    );

    -- 3. ЧИСТИМО ЗАЛИШКИ в recipe_tags
    -- Видаляємо старі зв'язки (ті, що не оновилися, бо були дублікатами)
    DELETE FROM recipe_tags WHERE tag_id = bad_tag_id;
    
    RAISE NOTICE '✅ Рецепти оновлено.';

    -- 4. СТРАХОВКА: ЧИСТИМО ПРОДУКТИ (product_tags)
    -- Якщо цей "битий" тег випадково потрапив у продукти, відв'язуємо його,
    -- інакше база не дозволить видалити сам тег.
    -- (Якщо таблиці product_tags немає або вона називається інакше - закоментуйте цей блок)
    BEGIN
        DELETE FROM product_tags WHERE tag_id = bad_tag_id;
    EXCEPTION WHEN undefined_table THEN
        RAISE NOTICE '⚠️ Таблиці product_tags немає, пропускаємо.';
    END;

    -- 5. ОНОВЛЮЄМО СВЯТА (holiday_definitions)
    -- Якщо на битому тегу висіло свято - перекидаємо на хороший
    UPDATE holiday_definitions 
    SET tag_id = good_tag_id 
    WHERE tag_id = bad_tag_id;

    -- 6. ФІНАЛЬНЕ ВИДАЛЕННЯ ТЕГУ
    DELETE FROM tags WHERE id = bad_tag_id;

    RAISE NOTICE '🎉 Успішно! Тег "%" видалено, зв''язки перенесено на "%".', bad_tag_name, good_tag_name;
END $$;



/*
-- Виводить теги що входять до product_tags та recipe_tags одночасно
SELECT 
    t.id,
    t.name,
    t.type,
    COUNT(DISTINCT rt.recipe_id) AS recipes_count,  -- Скільки разів вжито в рецептах
    COUNT(DISTINCT pt.product_id) AS products_count -- Скільки разів вжито в продуктах
FROM tags t
-- Робимо INNER JOIN до обох таблиць. 
-- Це означає: "Покажи тільки ті рядки, де тег є В ОБХ таблицях"
JOIN recipe_tags rt ON t.id = rt.tag_id
JOIN product_tags pt ON t.id = pt.tag_id
GROUP BY t.id, t.name, t.type
ORDER BY t.name;
*/

/*
-- видалення унікальності стовбця
ALTER TABLE tags DROP CONSTRAINT IF EXISTS tags_name_key;

-- 2. Додаємо нове складене обмеження (Назва + Тип)
ALTER TABLE tags 
ADD CONSTRAINT tags_name_type_unique UNIQUE (name, type);
*/