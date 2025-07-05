import os
import logging
from vk_api import VkApi
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()


class VkBot:
    def __init__(self):
        self.token = os.getenv("VK_TOKEN")
        self.group_id = os.getenv("GROUP_ID")
        self.vk_session = None
        self.vk = None
        self.longpoll = None

    def start(self):
        """Инициализация и запуск бота"""
        try:
            # Авторизация
            self.vk_session = VkApi(token=self.token)
            self.vk = self.vk_session.get_api()

            # Подключение к LongPoll
            self.longpoll = VkBotLongPoll(self.vk_session, self.group_id)
            logger.info("Бот успешно запущен")

            # Основной цикл обработки событий
            self.listen()

        except Exception as e:
            logger.error(f"Ошибка при запуске бота: {e}")

    def listen(self):
        """Прослушивание событий LongPoll"""
        for event in self.longpoll.listen():
            try:
                if event.type == VkBotEventType.MESSAGE_NEW:
                    self.handle_message(event)
                elif event.type == VkBotEventType.MESSAGE_TYPING_STATE:
                    self.send_message(event.object["from_id"], "Я слежу за тобой👁️")

            except Exception as e:
                logger.error(f"Ошибка обработки события: {e}")

    def handle_message(self, event):
        """Обработка входящих сообщений"""
        message = event.object
        user_id = message["from_id"]
        text = message["text"].lower()

        logger.info(f"Новое сообщение от {user_id}: {text}")

        # Обработка команд
        if text == "/start":
            self.send_message(user_id, "Привет! Я простой бот ВКонтакте.")
        elif text == "/help":
            self.send_message(
                user_id, "Доступные команды:\n/start - приветствие\n/help - справка"
            )
        else:
            self.send_message(user_id, "Я получил ваше сообщение!")

    def send_message(self, user_id, message):
        """Отправка сообщения пользователю"""
        try:
            self.vk.messages.send(user_id=user_id, message=message, random_id=0)
            logger.info(f"Отправлено сообщение для {user_id}")
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения: {e}")


if __name__ == "__main__":
    bot = VkBot()
    bot.start()
