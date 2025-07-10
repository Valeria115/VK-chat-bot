import os
from dotenv import load_dotenv

load_dotenv(override=True)


CONFIRMATION_TOKEN = os.getenv("CONFIRMATION_TOKEN")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
VK_API_TOKEN = os.getenv("VK_API_TOKEN")
VK_GROUP_ID = os.getenv("VK_GROUP_ID")
GIGACHAT_AUTH_KEY = os.getenv("GIGACHAT_AUTH_KEY")


DB_PATH = "knowledge.db"
SITE_URL = "https://education.vk.company/"
