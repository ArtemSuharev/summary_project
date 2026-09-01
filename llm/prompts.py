"""Формирование промптов для Yandex GPT."""

from __future__ import annotations

SUMMARIZATION_SYSTEM_PROMPT = (
    "Ты — помощник для суммаризации текста. "
    "Твоя задача — кратко и точно передавать основной смысл текста, "
    "сохраняя ключевые факты и идеи. "
    "Отвечай только результатом суммаризации, без лишних комментариев."
)

SUMMARIZATION_USER_PROMPT = (
    "Прошу пройтись по тексту и выделить самое важное, "
    "сохранив ключевые моменты. "
    "Вот текст:\n\n{text}"
)


def build_summarization_prompt(text: str) -> list[dict[str, str]]:
    """Собирает системный и пользовательский промпты для Yandex GPT.

    Формат сообщений соответствует YandexGPT API v2:
    [{"role": "system", "text": "..."}, {"role": "user", "text": "..."}]
    """
    return [
        {"role": "system", "text": SUMMARIZATION_SYSTEM_PROMPT},
        {"role": "user", "text": SUMMARIZATION_USER_PROMPT.format(text=text)},
    ]
