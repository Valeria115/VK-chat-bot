import logging
import time
from config import VK_API_TOKEN, VK_GROUP_ID
import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from text_utils import correct_spelling
from ai_gigachat import ask_gigachat
from db import get_intro_text
from text_utils import contains_profanity

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


class VkBot:
    def __init__(self):
        logger.info("Запуск бота...")
        start_time = time.time()

        # Инициализация VK API
        self.vk_session = vk_api.VkApi(token=VK_API_TOKEN)
        self.longpoll = VkBotLongPoll(self.vk_session, group_id=VK_GROUP_ID)
        self.vk = self.vk_session.get_api()

        logger.info("Инициализация VK API завершена.")

        # Инициализация базы и обновление
        init_db()
        update_if_needed()

        init_duration = time.time() - start_time
        logger.info(f"Инициализация бота завершена за {init_duration:.2f} секунд.")

    def send_message(self, user_id, message):
        logger.info(f"Отправка сообщения для {user_id}...")
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

            if contains_profanity(corrected_text):
                self.send_message(
                    user_id,
                    "⚠️ Пожалуйста, избегайте нецензурной лексики. Я помогу, если вы переформулируете вопрос корректно.",
                )
                return

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
                    "студент",
                    "школьник",
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
            if external:
                context = ""
            else:
                dynamic = get_top_context(corrected_text, k=6)
                intro = get_intro_text()
                context = intro + "\n\n" + dynamic

            # Вызов GigaChat
            try:
                logger.info("Запрос к GigaChat...")
                start_gigachat_time = time.time()
                gpt_answer = ask_gigachat(
                    user_question=corrected_text,
                    context_text=context,
                    external=external,
                    is_binary=is_binary,
                    is_list=is_list,
                )
                gigachat_duration = time.time() - start_gigachat_time
                logger.info(
                    f"Запрос к GigaChat выполнен за {gigachat_duration:.2f} секунд."
                )

                # Умная вставка ссылки
                # Умная вставка нескольких ссылок
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
                    links = generate_help_link(
                        corrected_text, top_k=3
                    )  # Выбираем топ-3 ссылки
                    gpt_answer += f"\n\n🔗 Подробнее: \n{links}"

            except Exception as e:
                logger.error(f"GigaChat API Error: {e}")
                gpt_answer = "Произошла ошибка при обращении к GigaChat."

            self.send_message(user_id, gpt_answer)

        except Exception as e:
            logger.error(f"Ошибка обработки события: {e}")

    def run(self):
        logger.info("Бот запущен и слушает сообщения...")
        for event in self.longpoll.listen():
            if event.type == VkBotEventType.MESSAGE_NEW:
                self.handle_message(event)


if __name__ == "__main__":
    bot = VkBot()
    bot.run()
