import os
import logging
from dotenv import load_dotenv
import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from text_utils import correct_spelling
from ai_gigachat import ask_gigachat
from db import (
    init_db,
    update_if_needed,
    search_knowledge,
    get_top_context,
    is_vke_related,
    is_list_request,
    generate_help_link,
    list_projects_for_audience,
)

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()
VK_API_TOKEN = os.getenv("VK_API_TOKEN")
VK_GROUP_ID = int(os.getenv("VK_GROUP_ID"))


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

            corrected_text = correct_spelling(text)
            logger.info(f"Исправленный текст: {corrected_text}")

            yes_no_triggers = [
                "возможно ли",
                "можно ли",
                "нельзя ли",
                "имею ли право",
                "допускается ли",
            ]
            is_binary = any(trigger in corrected_text for trigger in yes_no_triggers)
            is_list = is_list_request(corrected_text)
            external = not is_vke_related(corrected_text)

            # Обработка списочного запроса по аудитории
            if is_list:
                for audience in [
                    "школьник",
                    "студент",
                    "специалист",
                    "преподаватель",
                    "абитуриент",
                    "учащийся",
                    "выпускник",
                ]:
                    if audience in corrected_text:
                        answer = list_projects_for_audience(audience)
                        self.send_message(user_id, answer)
                        return

            # Получение контекста (только если вопрос относится к VK)
            context = "" if external else get_top_context(corrected_text, k=6)

            # Вызов GigaChat
            try:
                gpt_answer = ask_gigachat(
                    user_question=corrected_text,
                    context_text=context,
                    external=external,
                    is_binary=is_binary,
                    is_list=is_list,
                )

                # Умная вставка ссылки
                if not external and any(
                    word in gpt_answer.lower()
                    for word in [
                        "проект",
                        "участие",
                        "курс",
                        "обучение",
                        "программа",
                        "vk education",
                    ]
                ):
                    link = generate_help_link(corrected_text)
                    gpt_answer += f"\n\n🔗 Подробнее: {link}"

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
