from spellchecker import SpellChecker
from better_profanity import profanity
from profanity import profanity
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch
import torch.nn.functional as F

spell = SpellChecker(language="ru")  # для русского языка


def correct_spelling(text):
    words = text.split()
    corrected_words = [spell.correction(word) or word for word in words]
    return " ".join(corrected_words)


# Загружаем токенизатор и модель Toxic-BERT (обучена на русском)
MODEL_NAME = "cointegrated/rubert-tiny-toxicity"
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME)
model.eval()  # Отключаем обучение — только предсказания


def contains_profanity(text: str, threshold: float = 0.7) -> bool:
    """
    Проверка на токсичность/брань через русскоязычную BERT-модель.
    threshold — порог уверенности от 0 до 1 (например, 0.7 = 70% токсичности).
    """
    try:
        inputs = tokenizer(text, return_tensors="pt", truncation=True, padding=True)
        with torch.no_grad():
            outputs = model(**inputs)
            probs = F.softmax(outputs.logits, dim=1)
            toxic_score = probs[0][1].item()  # индекс 1 — класс «токсичный»

        return toxic_score >= threshold

    except Exception as e:
        print(f"[ERROR in toxicity check]: {e}")
        return False
