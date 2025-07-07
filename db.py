import sqlite3
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
from sentence_transformers import SentenceTransformer
from urllib.parse import urljoin
import numpy as np

DB_PATH = "knowledge.db"
SITE_URL = "https://education.vk.company/"
model = SentenceTransformer("all-MiniLM-L6-v2")  # используем предобученную модель


# Инициализация базы данных
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS knowledge (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        content TEXT,
        content_embedding BLOB,
        last_updated TIMESTAMP
    )
    """
    )
    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS meta (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """
    )
    conn.commit()
    conn.close()


def safe_encode(text):
    """Функция для безопасной генерации эмбеддинга"""
    try:
        embedding = model.encode(text)
        if embedding is not None:
            print(f"Эмбеддинг для текста: {text[:100]}... успешно сгенерирован.")
            return embedding.tobytes()  # Преобразуем в байты для сохранения в БД
        else:
            print(f"Ошибка: Эмбеддинг для текста не был сгенерирован.")
            return None
    except Exception as e:
        print(f"Ошибка при генерации эмбеддинга: {e}")
        return None


def fetch_page_data(url):
    """Функция для извлечения данных с отдельной страницы"""
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")
    parsed = []

    # Извлекаем разделы с заголовками и содержимым
    for section in soup.find_all("section"):
        title_tag = section.find(["h2", "h3", "h4"])
        if title_tag:
            title = title_tag.text.strip()
            content = section.get_text(separator=" ", strip=True)

            # Проверка на пустой контент
            if content:
                content_embedding = safe_encode(content)
                if content_embedding:
                    parsed.append((title, content, content_embedding))
                else:
                    print(
                        f"Предупреждение: Не удалось создать эмбеддинг для раздела: {title}"
                    )
            else:
                print(f"Предупреждение: Пустой контент на странице {url}")

    return parsed


def fetch_site_data():
    """Основная функция парсинга главной страницы и всех внутренних ссылок"""
    response = requests.get(SITE_URL)
    soup = BeautifulSoup(response.text, "html.parser")
    parsed_data = []

    # Извлекаем ссылки на все внутренние страницы
    internal_links = set()
    for link in soup.find_all("a", href=True):
        href = link["href"]
        # Если ссылка относительная, создаём полную ссылку
        if href.startswith("#"):
            href = urljoin(SITE_URL, href)
        if href.startswith(SITE_URL):
            internal_links.add(href)

    # Парсим главную страницу
    parsed_data.extend(fetch_page_data(SITE_URL))

    # Парсим каждую внутреннюю страницу
    for link in internal_links:
        print(f"Парсинг страницы: {link}")
        parsed_data.extend(fetch_page_data(link))

    return parsed_data


def save_to_db(data):
    """Сохранение данных в базу"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("DELETE FROM knowledge")
    now = datetime.now()
    for title, content, content_embedding in data:
        cursor.execute(
            """
        INSERT INTO knowledge (title, content, content_embedding, last_updated)
        VALUES (?, ?, ?, ?)
        """,
            (title, content, content_embedding, now),
        )

    conn.commit()
    conn.close()

    # Обновляем дату последнего обновления
    set_meta_value("last_updated", now.isoformat())


def set_meta_value(key, value):
    """Запись данных в таблицу meta"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("REPLACE INTO meta (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()


def get_meta_value(key):
    """Получение данных из таблицы meta"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM meta WHERE key = ?", (key,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None


def update_if_needed():
    """Обновление данных с сайта раз в 4 дня"""
    last_updated = get_meta_value("last_updated")
    now = datetime.now()
    if not last_updated or (now - datetime.fromisoformat(last_updated)) > timedelta(
        days=4
    ):
        print("Обновление базы знаний с сайта...")
        data = fetch_site_data()
        save_to_db(data)
    else:
        print("Обновление не требуется.")


def check_data_in_db():
    """Проверка данных в базе данных"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT title, content FROM knowledge LIMIT 5"
    )  # Печатаем первые 5 записей
    rows = cursor.fetchall()
    conn.close()

    for row in rows:
        print(f"Title: {row[0]}")
        print(f"Content: {row[1][:300]}...")  # Печатаем первые 300 символов


def search_knowledge(question):
    """Поиск в базе данных с использованием эмбеддингов"""
    query_embedding = model.encode(question)

    if query_embedding is None:
        return "Ошибка: Не удалось создать эмбеддинг для вашего запроса."

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT title, content, content_embedding FROM knowledge")
    rows = cursor.fetchall()

    best_score = -1
    best_answer = None

    for title, content, content_embedding in rows:
        if content_embedding:  # Проверяем, что эмбеддинг существует
            content_embedding = np.frombuffer(content_embedding, dtype=np.float32)
            similarity = model.similarity(query_embedding, content_embedding)

            print(f"Запрос: {question}")
            print(f"Заголовок: {title}")
            print(f"Схожесть: {similarity}")

            if similarity > best_score:
                best_score = similarity
                best_answer = f"Title: {title}\nContent: {content[:500]}..."

    conn.close()
    return best_answer if best_answer else "Я не нашёл подходящего ответа."


def get_all_context_text():
    """Объединяет все тексты из базы в один контекст"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT title, content FROM knowledge")
    rows = cursor.fetchall()
    conn.close()

    context = ""
    for title, content in rows:
        context += f"{title}:\n{content}\n\n"

    return context[:7000]  # Ограничим длину (лимит токенов GigaChat)
