import os
import urllib3
from dotenv import load_dotenv
from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()

GIGACHAT_AUTH_KEY = os.getenv("GIGACHAT_AUTH_KEY")


def ask_gigachat(
    user_question, context_text, external=False, is_binary=False, is_list=False
):
    client = GigaChat(credentials=GIGACHAT_AUTH_KEY, verify_ssl_certs=False)

    # УНИВЕРСАЛЬНЫЙ SYSTEM PROMPT
    if external:
        system_prompt = (
            "Ты — универсальный AI-помощник. Отвечай честно и полно на вопросы пользователей. "
            "Если информация отсутствует, скажи об этом прямо."
        )
    else:
        system_prompt = (
            "Ты — бот-консультант по образовательным проектам VK Education. "
            "Используй только контекст, который тебе предоставлен, чтобы ответить на вопрос. "
            "Если информации недостаточно, честно скажи об этом. "
            "Если вопрос закрытый (да/нет), дай короткий, но обоснованный ответ. "
            "Если вопрос требует объяснения — сделай его полезным. Не выдумывай, отвечай только по контексту."
        )

    messages = [
        Messages(role=MessagesRole.SYSTEM, content=system_prompt),
        Messages(
            role=MessagesRole.USER,
            content=f"Контекст:\n{context_text}\n\nВопрос: {user_question}",
        ),
    ]

    print("[GIGACHAT DEBUG] --- Отправка запроса к GigaChat ---")
    print(f"[GIGACHAT DEBUG] Вопрос: {user_question}")
    print(f"[GIGACHAT DEBUG] Контекст (обрезан): {context_text[:400]}...")
    print("[GIGACHAT DEBUG] ------------------------------------")

    try:
        response = client.chat(Chat(messages=messages))
        content = response.choices[0].message.content

        print("[GIGACHAT DEBUG] --- Ответ от GigaChat ---")
        print(content[:500], "..." if len(content) > 500 else "")
        print("[GIGACHAT DEBUG] --------------------------")

        return content
    except Exception as e:
        print("❌ Ошибка при обращении к GigaChat SDK:", e)
        return "Произошла ошибка при обращении к GigaChat."
