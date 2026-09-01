"""Конфигурация приложения — чтение переменных из .env."""


from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Настройки приложения, загружаемые из окружения / .env."""

    # --- Yandex GPT ---
    llm_base_url: str = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
    llm_model: str = "gpt://b1gvu3hqneggfc5lbq1s/yandexgpt/latest"
    llm_key_id: str = ""
    llm_key_secret: str = ""
    llm_timeout: float = 60.0

    # --- API ---
    host: str = "0.0.0.0"
    port: int = 8000
    max_text_length: int = 50_000

    # --- Logging ---
    log_level: str = "info"

    # --- Fallback ---
    fallback_enabled: bool = True
    fallback_summary: str = (
        "Сервис суммаризации временно недоступен. "
        "Повторите запрос позже или обратитесь к администратору."
    )

    # --- Yandex Service Account ---
    yandex_sa_id: str = "aje0c1kevi9a8qjrmb06"
    yandex_folder_id: str = "b1gvu3hqneggfc5lbq1s"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
