import logging
import os
from dotenv import load_dotenv
import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType

from db import init_db, update_if_needed, search_knowledge, get_all_context_text
from text_utils import correct_spelling
from ai_gigachat import ask_gigachat  # SDK-версия GigaChat

load_dotenv()


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GROUP_ID = os.getenv("VK_GROUP_ID")
VK_API_TOKEN = os.getenv("VK_API_TOKEN")

print(f"[DEBUG] VK_API_TOKEN: {VK_API_TOKEN}")
print(f"[DEBUG] VK_GROUP_ID: {GROUP_ID}")


class VkBot:
    def __init__(self):
        self.vk_session = vk_api.VkApi(token=VK_API_TOKEN)
        self.longpoll = VkBotLongPoll(self.vk_session, GROUP_ID)
        self.vk = self.vk_session.get_api()

        logger.info("Бот успешно запущен")

        # Инициализация базы данных
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

            # Поиск в базе
            answer = search_knowledge(corrected_text)

            if answer and "Я не нашёл подходящего ответа" not in answer:
                self.send_message(user_id, answer)
            else:
                context = get_all_context_text()
                try:
                    gpt_answer = ask_gigachat(corrected_text, context)
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
