"""Клиент для вызова Yandex GPT (Foundation Models API).

Слой llm: аутентификация через IAM, формирование запросов, таймауты, обработка ошибок.
Аутентификация: API Key → Authorization: Api-Key <key> → Foundation Models API.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

from config.settings import settings
from exceptions import LLMConnectionError, LLMResponseError, LLMTimeoutError
logger = logging.getLogger(__name__)

# URI модели — используется gpt-latest для доступа к последней доступной версии
GPT_LATEST_URI = (
    "gpt://b1gvu3hqneggfc5lbq1s/yandexgpt/latest"
)

# Foundation Models API endpoint
FOUNDATION_MODELS_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"

# Сколько раз повторять запрос при transient-ошибках
_DEFAULT_MAX_RETRIES = 3
# Базовая задержка между повторами (сек)
_DEFAULT_RETRY_DELAY = 1.0


class YandexGPTClient:
    """Клиент для Yandex GPT API v2.

    Аутентификация через API Key:
    1. Отправка запроса к GPT API с Authorization: Api-Key <key>
    """

    IAM_TOKEN_URL = "https://iam.api.cloud.yandex.net/iam/v1/tokens"

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        key_id: str | None = None,
        key_secret: str | None = None,
        max_retries: int = _DEFAULT_MAX_RETRIES,
        retry_delay: float = _DEFAULT_RETRY_DELAY,
    ):
        self._base_url = base_url or settings.llm_base_url
        self._model = model or settings.llm_model
        self._key_id = key_id or settings.llm_key_id
        self._key_secret = key_secret or settings.llm_key_secret
        self._timeout = settings.llm_timeout
        self._max_retries = max_retries
        self._retry_delay = retry_delay

        self._session: aiohttp.ClientSession | None = None
        self._iam_token: str | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Ленивая инициализация aiohttp-сессии."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def _close_session(self) -> None:
        """Закрытие aiohttp-сессии."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def _get_iam_token(self) -> str:
        """Возвращает API Key как токен для аутентификации.

        Для API Key в Yandex Cloud используется прямой заголовок:
        Authorization: Api-Key <key>

        Возвращает:
            API Key для аутентификации в YandexGPT API.
        """
        return self._key_secret

    async def generate(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> str:
        """Отправляет промпт в Yandex GPT и возвращает сгенерированный текст.

        Параметры:
            messages: список сообщений в формате {"role": ..., "text": ...}.
            temperature: температура генерации.
            max_tokens: максимальное число токенов в ответе.
            **kwargs: дополнительные параметры для YandexGPT API.

        Возвращает:
            Строка с ответом модели.

        Исключения:
            LLMConnectionError — при потере связи с YandexGPT API.
            LLMTimeoutError — при превышении таймаута.
            LLMResponseError — при пустом или некорректном ответе.
        """
        logger.info(
            "Отправка запроса к Yandex GPT: model=%s, messages=%d, timeout=%.1f",
            self._model,
            len(messages),
            self._timeout,
        )

        # Формируем URI модели
        uri = kwargs.pop("uri", self._model or GPT_LATEST_URI)

        # Foundation Models API v1 format
        payload = {
            "modelUri": uri,
            "completionOptions": {
                "stream": False,
                "temperature": temperature,
                "maxTokens": max_tokens,
            },
            "messages": messages,
        }

        headers = {
            "Content-Type": "application/json",
        }

        # Получаем токен для аутентификации
        try:
            token = await self._get_iam_token()
            headers["Authorization"] = f"Api-Key {token}"
        except LLMConnectionError:
            raise
        except Exception:
            logger.exception("Не удалось получить токен")
            raise LLMConnectionError(base_url=self.IAM_TOKEN_URL)

        session = await self._get_session()

        # --- Ретраи при transient-ошибках ---
        last_exc: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                async with session.post(
                    FOUNDATION_MODELS_URL,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=self._timeout),
                ) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        logger.error(
                            "Yandex GPT API вернул ошибку: status=%d, body=%s",
                            resp.status,
                            body,
                        )
                        # 4xx — не повторяем, это ошибка клиента
                        if 400 <= resp.status < 500:
                            raise LLMConnectionError(
                                base_url=FOUNDATION_MODELS_URL
                            )
                        # 5xx — повторяем
                        if attempt < self._max_retries:
                            delay = self._retry_delay * (2 ** (attempt - 1))
                            logger.warning(
                                "5xx ошибка от Yandex GPT (attempt %d/%d), "
                                "повтор через %.1f сек",
                                attempt,
                                self._max_retries,
                                delay,
                            )
                            await asyncio.sleep(delay)
                            continue
                        raise LLMConnectionError(
                            base_url=FOUNDATION_MODELS_URL
                        )

                    data = await resp.json()
                    break  # Успех — выходим из цикла ретраев

            except TimeoutError:
                last_exc = LLMTimeoutError(timeout=self._timeout)
                if attempt < self._max_retries:
                    delay = self._retry_delay * (2 ** (attempt - 1))
                    logger.warning(
                        "Таймаут (attempt %d/%d), повтор через %.1f сек",
                        attempt,
                        self._max_retries,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                logger.exception(
                    "Превышен таймаут запроса к Yandex GPT (%.1f сек) "
                    "после %d попыток",
                    self._timeout,
                    self._max_retries,
                )
                raise last_exc

            except aiohttp.ClientConnectionError:
                last_exc = LLMConnectionError(base_url=FOUNDATION_MODELS_URL)
                if attempt < self._max_retries:
                    delay = self._retry_delay * (2 ** (attempt - 1))
                    logger.warning(
                        "Сетевая ошибка (attempt %d/%d), повтор через %.1f сек",
                        attempt,
                        self._max_retries,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                logger.exception(
                    "Не удалось подключиться к Yandex GPT API: %s "
                    "после %d попыток",
                    FOUNDATION_MODELS_URL,
                    self._max_retries,
                )
                raise last_exc

            except Exception:
                logger.exception("Неожиданная ошибка при вызове Yandex GPT API")
                raise

        # --- Валидация ответа ---
        try:
            # Foundation Models API returns: result → alternatives → message → text
            result = data.get("result", {})
            alternatives = result.get("alternatives", [])

            if not alternatives:
                logger.warning("Yandex GPT вернул пустой ответ (no alternatives)")
                raise LLMResponseError("Yandex GPT вернул пустой ответ")

            message = alternatives[0].get("message", {})
            text = message.get("text", "")

            if not text or not text.strip():
                logger.warning("Yandex GPT вернул пустой текст")
                raise LLMResponseError("Yandex GPT вернул пустой текст")

            logger.info(
                "Yandex GPT вернул ответ: %d символов",
                len(text),
            )
            return text

        except LLMResponseError:
            raise
        except Exception:
            logger.exception("Ошибка при разборе ответа Yandex GPT")
            raise LLMResponseError("Не удалось разобрать ответ модели")

    async def close(self) -> None:
        """Освобождает ресурсы (закрывает aiohttp-сессию)."""
        await self._close_session()
