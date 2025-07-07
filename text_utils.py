# text_utils.py
from spellchecker import SpellChecker

spell = SpellChecker(language="ru")  # для русского языка


def correct_spelling(text):
    words = text.split()
    corrected_words = [spell.correction(word) or word for word in words]
    return " ".join(corrected_words)
