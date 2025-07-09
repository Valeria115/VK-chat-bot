import logging
import urllib3
from config import GIGACHAT_AUTH_KEY
from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole

# Отключаем предупреждения SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Настройка логгирования
logging.basicConfig(
    level=logging.DEBUG,  # Уровень логирования
    format="%(asctime)s - %(levelname)s - %(message)s",  # Формат вывода
)
logger = logging.getLogger(__name__)


def ask_gigachat(
    user_question, context_text, external=False, is_binary=False, is_list=False
):
    client = GigaChat(credentials=GIGACHAT_AUTH_KEY, verify_ssl_certs=False)

    # УНИВЕРСАЛЬНЫЙ SYSTEM PROMPT
    if external:
        system_prompt = (
            "Ты — бот-консультант по образовательным проектам VK Education. "
            "Используй только предоставленный контекст, чтобы ответить на вопрос. "
            "Контекст может включать описания разных проектов — анализируй всю информацию в целом. "
            "Если информации недостаточно, честно скажи об этом. "
            "Если вопрос закрытый (да/нет), ответь обоснованно, не ограничиваясь одним проектом."
        )

    else:
        system_prompt = (
            "Ты — бот-консультант по образовательным проектам VK Education. "
            "К тебе часто обращаются за помощью студенты. Будь внимателен, определи статус человека, не выдавай нерелевантную ссылку"
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

    # Логгирование запроса
    logger.debug("Отправка запроса к GigaChat")
    logger.debug(f"Вопрос: {user_question}")
    logger.debug(f"Контекст (обрезан): {context_text[:400]}...")

    try:
        response = client.chat(Chat(messages=messages))
        content = response.choices[0].message.content

        # Логгирование ответа
        logger.debug("Ответ от GigaChat:")
        logger.debug(f"{content[:500]}{'...' if len(content) > 500 else ''}")

        return content
    except Exception as e:
        logger.error(f"Ошибка при обращении к GigaChat SDK: {e}")
        return "Произошла ошибка при обращении к GigaChat."
