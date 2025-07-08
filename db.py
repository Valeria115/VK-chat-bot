import sqlite3
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
from sentence_transformers import SentenceTransformer
from urllib.parse import urljoin
import numpy as np
from numpy.linalg import norm

DB_PATH = "knowledge.db"
SITE_URL = "https://education.vk.company/"
model = SentenceTransformer("all-MiniLM-L6-v2")


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


# Косинусная похожесть
def cosine_similarity(a, b):
    return float(np.dot(a, b) / (norm(a) * norm(b)))


# Поиск по базе знаний с логами
def search_knowledge(question):
    """Поиск в базе данных с использованием эмбеддингов и логов"""
    query_embedding = model.encode(question)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT title, content, content_embedding FROM knowledge")
    rows = cursor.fetchall()

    best_score = -1
    best_answer = None
    threshold = 0.5

    for title, content, content_embedding in rows:
        if content_embedding is None:
            continue

        content_embedding = np.frombuffer(content_embedding, dtype=np.float32)
        similarity = cosine_similarity(query_embedding, content_embedding)

        print(f"[DEBUG] Похожесть с '{title}': {similarity:.4f}")

        if similarity > best_score:
            best_score = similarity
            best_answer = f"{content[:700]}..."

    print(f"[DEBUG] Лучшая похожесть: {best_score:.4f}")
    conn.close()

    return best_answer if best_score > threshold else "Я не нашёл подходящего ответа."


# Получение всех текстов (для GigaChat)
def get_all_context_text():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT title, content FROM knowledge")
    rows = cursor.fetchall()
    conn.close()

    context = ""
    for title, content in rows:
        context += f"{title}:\n{content}\n\n"

    return context[:7000]


# Извлечение одной страницы
def fetch_page_data(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")
    parsed = []

    for section in soup.find_all("section"):
        title_tag = section.find(["h2", "h3", "h4"])
        if title_tag:
            title = title_tag.text.strip()
            content = section.get_text(separator=" ", strip=True)
            content_embedding = (
                model.encode(content, normalize_embeddings=True)
                .astype(np.float32)
                .tobytes()
            )
            parsed.append((title, content, content_embedding))

    return parsed


# Извлечение сайта и ссылок
def fetch_site_data():
    response = requests.get(SITE_URL)
    soup = BeautifulSoup(response.text, "html.parser")
    parsed_data = []

    internal_links = set()
    for link in soup.find_all("a", href=True):
        href = link["href"].strip()
        full_url = urljoin(SITE_URL, href)
        clean_url = full_url.split("#")[0]

        if clean_url.startswith(SITE_URL):
            internal_links.add(clean_url)

    internal_links.discard(SITE_URL)

    print("[DEBUG] Найдено внутренних ссылок:")
    for url in internal_links:
        print(" └─", url)

    parsed_data.extend(fetch_page_data(SITE_URL))

    for link in internal_links:
        try:
            print(f"[DEBUG] Парсинг страницы: {link}")
            parsed_data.extend(fetch_page_data(link))
        except Exception as e:
            print(f"[WARNING] Не удалось распарсить {link}: {e}")

    return parsed_data


# Сохранение данных в базу
def save_to_db(data):
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
    set_meta_value("last_updated", now.isoformat())
    print(f"[DEBUG] Сохранено записей: {len(data)}")


# Meta-таблица
def set_meta_value(key, value):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("REPLACE INTO meta (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()


def get_meta_value(key):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM meta WHERE key = ?", (key,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None


# Проверка, нужно ли обновлять
def update_if_needed():
    last_updated = get_meta_value("last_updated")
    now = datetime.now()
    if not last_updated or (now - datetime.fromisoformat(last_updated)) > timedelta(
        days=4
    ):
        print("[DEBUG] Обновление базы знаний с сайта...")
        data = fetch_site_data()
        save_to_db(data)
    else:
        print("Обновление не требуется.")


def get_top_context(question, k=3):
    """Возвращает top-k наиболее релевантных блоков контекста"""
    query_embedding = model.encode(question)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT title, content, content_embedding FROM knowledge")
    rows = cursor.fetchall()
    conn.close()

    scored = []
    for title, content, embedding in rows:
        if embedding is None:
            continue
        content_embedding = np.frombuffer(embedding, dtype=np.float32)
        score = cosine_similarity(query_embedding, content_embedding)
        scored.append((score, title, content))

    top = sorted(scored, reverse=True)[:k]
    return "\n\n".join([f"{title}:\n{content}" for _, title, content in top])
