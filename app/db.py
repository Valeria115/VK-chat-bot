import logging
import os

from datetime import datetime, timedelta
import sqlite3
from bs4 import BeautifulSoup
from sentence_transformers import SentenceTransformer
from urllib.parse import urljoin
from numpy.linalg import norm
import numpy as np
from playwright.sync_api import sync_playwright
from config import DB_PATH, SITE_URL

model_path = "local_model/all-MiniLM-L6-v2"

if not os.path.exists(model_path):
    print("Загрузка модели и сохранение локально...")
    model = SentenceTransformer("all-MiniLM-L6-v2")
    model.save(model_path)
else:
    print("Модель уже сохранена локально.")

model = SentenceTransformer(model_path)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_rendered_html(url):
    with sync_playwright() as p:
        browser = p.romium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, timeout=60000)
        page.wait_for_load_state("networkidle")
        html = page.content()
        browser.close()
        return html


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS knowledge (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            content TEXT,
            url TEXT,
            content_embedding BLOB,
            last_updated TIMESTAMP
        )
        """
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_title_hash ON knowledge (title)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_url_hash ON knowledge (url)")

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


def cosine_similarity(a, b):
    return float(np.dot(a, b) / (norm(a) * norm(b)))


def search_knowledge(question):
    query_embedding = model.encode(question)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT title, content, content_embedding FROM knowledge")
    rows = cursor.fetchall()
    conn.close()

    best_score = -1
    best_answer = None
    threshold = 0.5

    for title, content, content_embedding in rows:
        if content_embedding is None:
            continue
        content_embedding = np.frombuffer(content_embedding, dtype=np.float32)
        similarity = cosine_similarity(query_embedding, content_embedding)
        if similarity > best_score:
            best_score = similarity
            best_answer = f"{content[:700]}..."

    return best_answer if best_score > threshold else "Я не нашёл подходящего ответа."


def get_top_context(question, k=3):
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


def is_vke_related(question, threshold=0.4):
    query_embedding = model.encode(question)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT content_embedding FROM knowledge")
    rows = cursor.fetchall()
    conn.close()

    for (embedding,) in rows:
        if embedding is None:
            continue
        content_embedding = np.frombuffer(embedding, dtype=np.float32)
        score = cosine_similarity(query_embedding, content_embedding)
        if score > threshold:
            return True
    return False


def is_list_request(question):
    triggers = ["какие", "перечисли", "список", "доступны", "есть ли проекты"]
    return any(word in question.lower() for word in triggers)


def generate_help_link(question, top_k=3, threshold=0.5):
    query_embedding = model.encode(question)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT title, url, content_embedding FROM knowledge")
    rows = cursor.fetchall()
    conn.close()

    relevant_links = []

    for title, url, embedding in rows:
        if embedding is None or url is None:
            continue
        content_embedding = np.frombuffer(embedding, dtype=np.float32)
        score = cosine_similarity(query_embedding, content_embedding)

        if score >= threshold:
            relevant_links.append((score, url))

    relevant_links.sort(reverse=True, key=lambda x: x[0])

    top_links = [url for _, url in relevant_links[:top_k]]

    if not top_links:
        return SITE_URL

    return "\n".join(top_links)


def fetch_page_data(url):
    logger.info(f"Парсинг: {url}")
    html = get_rendered_html(url)
    soup = BeautifulSoup(html, "html.parser")
    parsed = []

    for card in soup.find_all("div", class_=lambda x: x and "card" in x):
        content = card.get_text(" ", strip=True)
        if content and len(content.split()) >= 5:
            title = content[:40].strip()
            embedding = model.encode(content).astype(np.float32).tobytes()
            parsed.append((title, content, url, embedding))

    for section in soup.find_all("section"):
        title_tag = section.find(["h2", "h3", "h4"])
        if title_tag:
            title = title_tag.text.strip()
            content = section.get_text(separator=" ", strip=True)
            embedding = model.encode(content).astype(np.float32).tobytes()
            parsed.append((title, content, url, embedding))

    return parsed


def fetch_site_data():
    html = get_rendered_html(SITE_URL)
    soup = BeautifulSoup(html, "html.parser")
    parsed_data = []

    internal_links = set()
    for link in soup.find_all("a", href=True):
        href = link["href"].strip()
        full_url = urljoin(SITE_URL, href)
        clean_url = full_url.split("#")[0]
        if clean_url.startswith(SITE_URL):
            internal_links.add(clean_url)

    internal_links.discard(SITE_URL)
    parsed_data.extend(fetch_page_data(SITE_URL))

    for link in internal_links:
        try:
            parsed_data.extend(fetch_page_data(link))
        except Exception as e:
            logger.warning(f"Ошибка парсинга {link}: {e}")

    return parsed_data


def save_to_db(data):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM knowledge")
    now = datetime.now()
    cursor.executemany(
        """
        INSERT INTO knowledge (title, content, url, content_embedding, last_updated)
        VALUES (?, ?, ?, ?, ?)
        """,
        [
            (title, content, url, embedding, now)
            for title, content, url, embedding in data
        ],
    )

    conn.commit()
    conn.close()
    set_meta_value("last_updated", now.isoformat())


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


def update_if_needed():
    last_updated = get_meta_value("last_updated")
    now = datetime.now()
    if not last_updated or (now - datetime.fromisoformat(last_updated)) > timedelta(
        days=4
    ):
        logger.debug("Обновление базы знаний с сайта...")
        data = fetch_site_data()
        save_to_db(data)
    else:
        logger.debug("Обновление не требуется.")


def list_projects_for_audience(audience_keyword="студент"):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT title, content, url FROM knowledge")
    rows = cursor.fetchall()
    conn.close()

    audience_pages = {
        "школьник": "/students",
        "студент": "/students",
        "специалист": "/professionals",
        "преподаватель": "/teachers",
        "учащийся": "/students",
        "выпускник": "/students",
        "абитуриент": "/students",
    }

    relevant_url = audience_pages["студент"]
    if not relevant_url:
        return "Для указанной категории не найдено подходящего раздела."

    projects = []
    seen_titles = set()

    for title, content, url in rows:
        if relevant_url not in url:
            continue

        if "/students" in url and audience_keyword.lower() == "студент":
            pass
        else:
            if not any(
                kw in title.lower()
                for kw in [
                    "проект",
                    "курс",
                    "школа",
                    "программа",
                    "стажировка",
                    "академия",
                    "трек",
                ]
            ):
                continue

        summary = content.strip().split(". ")[0][:160].strip()
        if title not in seen_titles and summary:
            seen_titles.add(title)
            projects.append((title.strip(), summary, url))

    if not projects:
        return "Не удалось найти проекты по заданной категории."

    formatted = []
    for title, summary, url in projects:
        formatted.append(f"- {title}\n  {summary}...\n  🔗 {url}")

    return "\n\n".join(formatted)


def get_intro_text():
    """Возвращает общий вводный текст о VK Education (вставляется вручную или парсится один раз)"""
    return (
        "VK Education — это платформа, включающая множество бесплатных образовательных программ для студентов, школьников и специалистов. "
        "Пользователи могут проходить курсы, участвовать в мероприятиях, подавать заявки на участие в нескольких проектах при условии соответствия требованиям каждой программы. "
        "Участие в нескольких проектах одновременно возможно, если не возникает конфликтов по времени и требованиям."
    )
