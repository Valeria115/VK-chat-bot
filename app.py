import os
import logging
from dotenv import load_dotenv
import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from db import is_vke_related, is_list_request
from text_utils import correct_spelling
from ai_gigachat import ask_gigachat


from db import (
    init_db,
    update_if_needed,
    search_knowledge,
    get_top_context,
    generate_help_link,
)


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

            # Исправление орфографии
            corrected_text = correct_spelling(text)
            logger.info(f"Исправленный текст: {corrected_text}")

            # Импорт вспомогательных функций
            from db import (
                is_vke_related,
                is_list_request,
                get_top_context,
                search_knowledge,
                generate_help_link,
            )

            # Определение типа вопроса
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
            is_list = is_list_request(corrected_text)
            external = not is_vke_related(corrected_text)

            # Дополнительная логика
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
                        from db import list_projects_for_audience

                        answer = list_projects_for_audience(audience)
                        self.send_message(user_id, answer)
                        return

            # Получение релевантного контекста
            context = get_top_context(corrected_text, k=6 if is_list else 3)

            # Поиск локального ответа
            answer = search_knowledge(corrected_text)

            if answer and "Я не нашёл подходящего ответа" not in answer:
                help_link = generate_help_link(corrected_text)
                full_reply = f"{answer}\n\n🔗 Подробнее: {help_link}"
                self.send_message(user_id, full_reply)
            else:
                try:
                    gpt_answer = ask_gigachat(
                        user_question=corrected_text,
                        context_text=context,
                        external=external,
                        is_binary=is_binary,
                        is_list=is_list,
                    )

                    if (
                        "ответа нет" in gpt_answer.lower()
                        or "не могу ответить" in gpt_answer.lower()
                    ):
                        gpt_answer += "\n\nℹ️ Возможно, нужную информацию можно найти на сайте VK Education: https://education.vk.company/"
                    else:
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
