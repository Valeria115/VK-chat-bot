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

    # SYSTEM PROMPT
    if external:
        system_prompt = (
            "Ты — универсальный AI-помощник. Отвечай честно и полно на вопросы пользователей. "
            "Если информация отсутствует, скажи об этом прямо."
        )
    elif is_binary:
        system_prompt = (
            "Ты — помощник по проектам VK Education. Ответь строго 'Да.' или 'Нет.' на основе текста. "
            "Если информации недостаточно, скажи: 'Не могу ответить на этот вопрос точно.'"
        )
    elif is_list:
        system_prompt = (
            "Ты — бот VK Education. В вопросе пользователь просит список проектов. "
            "Внимательно проанализируй текст. Если найдены несколько проектов, выведи их в формате списка:\n"
            "- Название проекта 1\n"
            "- Название проекта 2\n"
            "- ...\n\n"
            "Если найден только один проект, выведи только его. Не выдумывай. Используй только контекст."
        )
    else:
        system_prompt = (
            "Ты — помощник по проектам VK Education. Используй только предоставленный текст. "
            "Если ответа нет, скажи об этом честно. Не используй внешние знания."
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
        raise
