import os
from dotenv import load_dotenv
from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole

load_dotenv()

# Загружаем Authorization Key из .env
GIGACHAT_AUTH_KEY = os.getenv("GIGACHAT_AUTH_KEY")


def ask_gigachat(user_question, context_text, external=False, is_binary=False):
    client = GigaChat(credentials=GIGACHAT_AUTH_KEY, verify_ssl_certs=False)

    # SYSTEM PROMPT
    if external:
        system_prompt = "Ты — универсальный помощник. Отвечай честно и полно на вопрос пользователя, используя все свои знания."
    elif is_binary:
        system_prompt = (
            "Ты — эксперт по VK Education. Ответь только 'Да.' или 'Нет.' строго на основе предоставленного текста. "
            "Если недостаточно информации, ответь: 'Не могу ответить на этот вопрос точно.'"
        )
    else:
        system_prompt = (
            "Ты — бот-помощник по проектам VK Education. Используй только текст ниже. "
            "Не придумывай, если нет ответа — честно скажи, что он отсутствует."
        )

    messages = [
        Messages(role=MessagesRole.SYSTEM, content=system_prompt),
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
