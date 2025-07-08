import os
import logging
from dotenv import load_dotenv
import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType

from text_utils import correct_spelling
from db import init_db, update_if_needed, search_knowledge, get_top_context
from ai_gigachat import ask_gigachat

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()
VK_API_TOKEN = os.getenv("VK_API_TOKEN")
VK_GROUP_ID = os.getenv("VK_GROUP_ID")


class VkBot:
    def __init__(self):
        self.vk_session = vk_api.VkApi(token=VK_API_TOKEN)
        self.longpoll = VkBotLongPoll(self.vk_session, group_id=VK_GROUP_ID)
        self.vk = self.vk_session.get_api()

        logger.info("Бот успешно запущен")

        # Инициализация базы и обновление
        init_db()
        update_if_needed()

    def send_message(self, user_id, message):
        self.vk.messages.send(
            user_id=user_id,
            message=message,
            random_id=vk_api.utils.get_random_id(),
        )
        logger.info(f"Отправлено сообщение для {user_id}")

    def handle_message(self, event):
        try:
            message = event.object
            user_id = message["from_id"]
            text = message["text"].strip().lower()

            logger.info(f"Новое сообщение от {user_id}: {text}")

            if text in ["/start", "начать"]:
                self.send_message(
                    user_id, "Привет! Я бот VK Education. Задай мне вопрос о проектах."
                )
                return

            if not text:
                self.send_message(user_id, "Пожалуйста, напиши текст вопроса.")
                return

            # Исправление опечаток
            corrected_text = correct_spelling(text)
            logger.info(f"Исправленный текст: {corrected_text}")

            # Поиск по базе
            answer = search_knowledge(corrected_text)

            # Проверка: является ли вопрос закрытым (да/нет)
            yes_no_triggers = [
                "возможно ли",
                "можно ли",
                "нельзя ли",
                "имею ли право",
                "допускается ли",
            ]
            is_binary = any(
                trigger in corrected_text.lower() for trigger in yes_no_triggers
            )

            # Получение релевантного контекста
            context = get_top_context(corrected_text)

            # Если релевантный ответ найден в базе
            if answer and "Я не нашёл подходящего ответа" not in answer:
                self.send_message(user_id, answer)
            else:
                try:
                    gpt_answer = ask_gigachat(
                        user_question=corrected_text,
                        context_text=context,
                        external=True,  # использовать знания вне базы, если не нашёл
                        is_binary=is_binary,  # включить режим да/нет
                    )
                except Exception as e:
                    logger.error(f"GigaChat API Error: {e}")
                    gpt_answer = "Произошла ошибка при обращении к GigaChat."

                self.send_message(user_id, gpt_answer)

        except Exception as e:
            logger.error(f"Ошибка обработки события: {e}")

    def run(self):
        for event in self.longpoll.listen():
            if event.type == VkBotEventType.MESSAGE_NEW:
                self.handle_message(event)


if __name__ == "__main__":
    bot = VkBot()
    bot.run()
