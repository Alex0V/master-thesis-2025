import re
from bs4 import BeautifulSoup
from utils.parsers import parse_qty_unit, parse_time_str

# ==========================================
# 1. СПІЛЬНИЙ БАТЬКО ДЛЯ SHUBA
# ==========================================
class ShubaBaseParser:
    """
    Тут живе логіка, спільна для всіх сторінок Shuba.life
    """

    def _get_title(self, soup):
        try:
            return soup.find('h1', class_='c-heading__title c-title c-title--h1').get_text(strip=True)
        except:
            return "Unknown Title"

    def _get_image_url(self, soup):
        # На Shuba картинка часто в u-cover
        div = soup.find('picture', class_='u-cover')
        if div:
            img = div.find('img')
            if img:
                return img.get('src')
        return None

# ==========================================
# 2. ПАРСЕР РЕЦЕПТІВ (Наслідує ShubaBaseParser)
# ==========================================
class ShubaRecipeParser(ShubaBaseParser):
    
    def parse(self, html_content, url):
        soup = BeautifulSoup(html_content, 'html.parser')
        meta = self._get_meta_data(soup)

        return {
            "title": self._get_title(soup),
            "category": self._get_category(soup),
            "original_url": url,
            "image_url": self._get_image_url(soup),

            # Метадані
            "portions_num": meta.get('portions_num'),
            "prep_time": meta.get('prep_time'),
            "cook_time": meta.get('cook_time'),

            # Складні дані
            "ingredients_list": self._get_ingredients(soup),
            "instructions": self._get_instructions(soup),
            "nutrition": self._get_nutrition(soup)
        }

    def _get_category(self, soup):
        breadcrumb = soup.find('div', class_='c-breadcrumbs')
        if not breadcrumb:
            return None

        items = breadcrumb.find_all('li', class_='c-breadcrumbs__item')

        # шукаємо <a> всередині кожного li
        links = [li.find('a') for li in items]

        # фільтруємо тільки ті, що мають текст
        links = [a.get_text(strip=True) for a in links if a]

        # Очікувана структура:
        # 0 -> "Головна"
        # 1 -> "Рецепти"
        # 2 -> Категорія (Сніданки, Десерти тощо)
        if len(links) >= 3:
            return links[2]

        return None
    
    def _get_meta_data(self, soup):
        data = {"portions_num": None, "prep_time": None, "cook_time": None}

        # Шукаємо блок c-details (ми це розбирали раніше)
        for item in soup.find_all('div', class_='c-details'):
            try:
                val = item.find('dd').get_text(strip=True)
                lbl = item.find('dt').get_text(strip=True).lower()

                if "порц" in lbl:
                    data['portions_num'] = int(val)
                elif "готув" in lbl:
                    data['cook_time'] = parse_time_str(val)
                elif "підготов" in lbl:
                    data['prep_time'] = parse_time_str(val)
            except: continue
        return data

    def _get_ingredients(self, soup):
        """
        Парсить таблицю інгредієнтів.
        Повертає: [{'section': 'Тісто', 'product': 'Мука', 'qty': '200', 'unit': 'г', 'product_url': '...'}]
        """
        ingredients_list = []
        # Знаходимо всі блоки секцій (Опара, Тісто, Соус і т.д.)
        main_sec = soup.find('div', class_='bg-white px-4 py-8 md:py-10 md:px-12 my-15 lg:my-25 c-prose__ignore')
        sections = main_sec.find_all('div', recursive=False)

        for section in sections[1:-1]:
            title_tag = section.find_previous_sibling('span')
            section_name = title_tag.get_text(strip=True).rstrip(':') if title_tag else "Основне"
            for row in section.find_all('div', class_='flex items-center gap-3'):
                try:
                    label_tag = row.find('label', class_='f-check__label')
                    a_tag = label_tag.find('a')
                    if a_tag:
                        # Варіант А: Є посилання
                        product_name = a_tag.get_text(strip=True)
                        product_url = a_tag.get('href')
                    else:
                        # Варіант Б: Посилання немає (просто текст)
                        product_name = label_tag.get_text(strip=True)
                        product_url = None
                    
                    if not product_name:
                        continue

                    # Кількість знаходиться у останньому <span>
                    qty_span = row.find_all('span')[-1] if row.find_all('span') else None
                    qty_text = qty_span.get_text(strip=True) if qty_span else None
                    qty, unit = parse_qty_unit(qty_text)
                    ingredients_list.append({
                        "section": section_name,
                        "product": product_name,
                        "amount": qty,
                        "unit": unit,
                        "product_url": product_url
                    })
                except Exception as e:
                    print(f"Помилка рядка інгредієнта: {e}")
                    continue

        return ingredients_list

    def _get_instructions(self, soup):
            """
            Парсить кроки приготування (актуальна верстка Shuba).
            Розділяє заголовок ("Підготуй...") та опис.
            """
            steps = []
            
            # 1. Знаходимо всі заголовки кроків
            step_headers = soup.find_all('div', class_='c-tag--step')
            
            for idx, header in enumerate(step_headers, 1):
                try:
                    # --- A. ЗАГОЛОВОК КРОКУ ---
                    # Вхід: "1/8. Підготуй інгредієнти"
                    raw_header = header.get_text(strip=True)
                    
                    # Чистимо від нумерації ("1/8.", "Крок 1")
                    clean_title = re.sub(r'^(?:Крок\s*)?\d+(?:/\d+)?\.?\s*', '', raw_header).strip()
                    
                    # --- Б. ОПИС ТА КОНТЕЙНЕР ---
                    description = ""
                    container = header.find_parent('div') # Батьківський блок кроку
                    
                    if container:
                        # Шукаємо блок з текстом
                        content_div = container.find('div', class_='c-prose')
                        if content_div:
                            # separator=' ' гарантує, що абзаци <p> не злипнуться
                            description = content_div.get_text(separator=' ', strip=True)
                            # Прибираємо зайві подвійні пробіли
                            description = re.sub(r'\s+', ' ', description)

                    # --- В. КАРТИНКА ---
                    step_image = None
                    if container:
                        img = container.find('img')
                        if img:
                            src = img.get('src') or img.get('data-src')
                            if src:
                                if not src.startswith('http'):
                                    src = "https://shuba.life" + src
                                step_image = src

                    # --- Г. ЗБИРАЄМО РЕЗУЛЬТАТ ---
                    steps.append({
                        "step_number": idx,
                        "title": clean_title,       # "Підготуй інгредієнти"
                        "description": description, # "Натри сир..."
                        "image_url": step_image
                    })

                except Exception as e:
                    print(f"Помилка парсингу кроку {idx}: {e}")
                    continue
                    
            return steps

    def _get_nutrition(self, soup):
        """
        Парсить блок БЖВ (c-nutritional).
        """
        nutr = {
            "calories": None,
            "proteins": None,
            "fats": None,
            "carbs": None
        }

        # 1. Знаходимо головний блок
        container = soup.find('div', class_='c-nutritional')
        if not container:
            return nutr

        # 2. Калорії (Текст всередині кола)
        pie_text_div = container.find('div', class_='c-nutritional__pie-text')
        if pie_text_div:
            raw_cals = pie_text_div.get_text(strip=True) # "816ккал"
            # Шукаємо число
            amount, _ = parse_qty_unit(raw_cals)
            if amount:
                nutr['calories'] = float(amount)

        # 3. БЖВ (Легенда)
        legend_items = container.find_all('div', class_='c-nutritional__legend-item')
        
        for item in legend_items:
            try:
                # dd = Значення ("30 г")
                # dt = Назва ("білки")
                val_tag = item.find('dd')
                key_tag = item.find('dt')
                
                if not val_tag or not key_tag: continue
                
                val_text = val_tag.get_text(strip=True) # "30 г"
                key_text = key_tag.get_text(strip=True).lower() # "білки"
                
                amount, _ = parse_qty_unit(val_text)

                # Мапимо на наші поля
                if 'біл' in key_text:
                    nutr['proteins'] = amount
                elif 'жир' in key_text:
                    nutr['fats'] = amount
                elif 'вугл' in key_text:
                    nutr['carbs'] = amount
                    
            except Exception:
                continue

        return nutr

# ==========================================
# 3. ПАРСЕР ПРОДУКТІВ (Наслідує ShubaBaseParser)
# ==========================================
class ShubaProductParser(ShubaBaseParser):
    def parse(self, html_content, url):
        soup = BeautifulSoup(html_content, 'html.parser')

        return {
            # Беремо методи з батька
            "name": self._get_title(soup),
            "image_url": self._get_image_url(soup),
            "nutrition": self._get_nutrition(soup),
            "url": url,
        }
    
    def _get_nutrition(self, soup):
        """
        Логіка БЖВ для ПРОДУКТУ
        """
        nutr = {"calories": None, "proteins": None, "fats": None, "carbs": None}

        # 1. Знаходимо головний блок
        nutri_block = soup.find('div', class_='flex flex-wrap items-center gap-x-2 text-base')
        if nutri_block:
            # Калорії — завжди перший <div>
            kcal_text = nutri_block.find('div').get_text(strip=True)
            # Шукаємо число
            amount, _ = parse_qty_unit(kcal_text)
            if amount:
                nutr['calories'] = float(amount)
            # Другий <div> — білки, жири, вуглеводи
            details = nutri_block.find_all('div')[1].get_text(" ", strip=True)
            for item in details.split(","):
                qty, text = parse_qty_unit(item)
                if 'біл' in text:
                    nutr['proteins'] = qty
                elif 'жир' in text:
                    nutr['fats'] = qty
                elif 'вугл' in text:
                    nutr['carbs'] = qty
        return nutr