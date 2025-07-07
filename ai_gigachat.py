from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole
import os
from dotenv import load_dotenv

load_dotenv()

GIGACHAT_AUTH_KEY = os.getenv("GIGACHAT_AUTH_KEY")


def ask_gigachat(user_question, context_text):
    client = GigaChat(credentials=GIGACHAT_AUTH_KEY, verify_ssl_certs=False)

    messages = [
        Messages(
            role=MessagesRole.SYSTEM,
            content="Ты бот-помощник по проектам VK Education. Отвечай строго на основе приведённого текста.",
        ),
        Messages(
            role=MessagesRole.USER,
            content=f"Контекст:\n{context_text}\n\nВопрос: {user_question}",
        ),
    ]

    try:
        response = client.chat(Chat(messages=messages))
        return response.choices[0].message.content
    except Exception as e:
        print("❌ Ошибка при обращении к GigaChat SDK:", e)
        raise
