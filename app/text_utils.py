import os
import torch
from autocorrect import Speller
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch.nn.functional as F
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

spell = Speller(lang="ru")

MODEL_NAME = "cointegrated/rubert-tiny-toxicity"
model_path = "local_model/rubert-tiny-toxicity"

if not os.path.exists(model_path):
    logger.info("Загрузка модели и токенизатора...")
    try:
        tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
        model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME)
        tokenizer.save_pretrained(model_path)
        model.save_pretrained(model_path)
        logger.info("Модель и токенизатор успешно сохранены локально.")
    except Exception as e:
        logger.error(f"Ошибка при загрузке и сохранении модели: {e}")
else:
    logger.info("Модель и токенизатор загружены локально.")
    tokenizer = AutoTokenizer.from_pretrained(model_path)
    model = AutoModelForSequenceClassification.from_pretrained(model_path)

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = model.to(device)
model.eval()


def correct_spelling(text):
    logger.debug(f"Коррекция орфографии для текста: {text[:50]}...")
    corrected_text = " ".join([spell(word) for word in text.split()])
    logger.debug(f"Исправленный текст: {corrected_text[:50]}...")
    return corrected_text


def contains_profanity(text: str, threshold: float = 0.7) -> bool:
    """
    Проверка на токсичность/брань через русскоязычную BERT-модель.
    threshold — порог уверенности от 0 до 1 (например, 0.7 = 70% токсичности).
    """
    try:
        logger.debug(f"Проверка текста на токсичность: {text[:50]}...")
        inputs = tokenizer(text, return_tensors="pt", truncation=True, padding=True).to(
            device
        )
        with torch.no_grad():
            outputs = model(**inputs)
            probs = F.softmax(outputs.logits, dim=1)
            toxic_score = probs[0][1].item()

        logger.debug(f"Токсичность текста: {toxic_score:.2f}")
        return toxic_score >= threshold

    except Exception as e:
        logger.error(f"[ERROR in toxicity check]: {e}")
        return False
