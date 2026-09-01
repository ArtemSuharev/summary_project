## Цель изменений

Сервис суммаризации текстов на основе Yandex GPT Foundation Models API.

Принимает произвольный текст через REST API, формирует промпт, отправляет запрос к Yandex GPT и возвращает краткое содержание.

### Что реализовано

- [ ] REST API на базе FastAPI (Swagger / ReDoc)
- [ ] Интеграция с Yandex GPT (Foundation Models API v1)
- [ ] Fallback-режим при недоступности LLM
- [ ] Валидация входных данных (Pydantic)
- [ ] JSON-логирование с `request_id`
- [ ] Набор pytest-тестов

---

## Архитектура и основные компоненты

Слоистая архитектура с чётким разделением ответственности:

```
┌─────────────────────────────────────────────────┐
│                  FastAPI (API)                   │
│   Маршруты · Валидация · Middleware ·            │
│   Exception Handlers                             │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────┐
│           Pipeline (services)                    │
│   build_prompt → llm.generate → post_process     │
│   Fallback-логика при недоступности Yandex GPT   │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────┐
│         Yandex GPT Client (llm)                  │
│   aiohttp · API Key · Таймауты ·                 │
│   Обработка сетевых ошибок · Ретраи              │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────┐
│   Foundation Models API v1                       │
│   (llm.api.cloud.yandex.net)                     │
└─────────────────────────────────────────────────┘
```

### Компоненты

| Слой | Модуль | Ответственность |
|---|---|---|
| **API** | `api/routes.py` | Приём HTTP-запросов, валидация Pydantic, маршрутизация |
| **Pipeline** | `services/pipeline.py` | Бизнес-логика: сборка промпта → вызов Yandex GPT → пост-обработка, fallback |
| **Yandex GPT Client** | `llm/client.py` | Асинхронный вызов API, API Key, обработка таймаутов, ретраи |
| **Prompts** | `llm/prompts.py` | Системный и пользовательский промпты для суммаризации |
| **Post-processing** | `llm/postprocess.py` | Очистка ответа: удаление артефактов, Markdown-блоков |
| **Config** | `config/settings.py` | Чтение настроек из `.env` через pydantic-settings |

### Поток данных

1. Клиент отправляет `POST /api/summarize` с полем `text`
2. **API** валидирует входные данные (не пустой, не длиннее `MAX_TEXT_LENGTH`)
3. **Pipeline** формирует промпт (system + user сообщения)
4. **Yandex GPT Client** отправляет промпт на `llm.api.cloud.yandex.net` с аутентификацией через API Key
5. **Post-processing** очищает ответ модели от артефактов
6. Результат возвращается клиенту с метаданными (`input_length`, `output_length`, `request_id`)
7. При ошибке Yandex GPT (сеть / таймаут) возвращается **fallback-сообщение**, если `FALLBACK_ENABLED=true`

---

## Чек-лист самопроверки

### Функциональность

- [ ] Сервис запускается локально: `uvicorn main:app --reload --port 8000`
- [ ] Health-check: `GET /health` → `{"status": "ok"}`
- [ ] Успешная суммаризация: `POST /api/summarize` → 200 с полем `summary`
- [ ] Пустой текст → 422 (валидация Pydantic)
- [ ] Текст свыше `MAX_TEXT_LENGTH` → 400
- [ ] При недоступности Yandex GPT возвращается fallback-ответ (если `FALLBACK_ENABLED=true`)
- [ ] Swagger UI доступен на `/docs`, ReDoc на `/redoc`

### Качество кода

- [ ] Тесты проходят: `pytest tests/ -v`
- [ ] Линтер проходит: `ruff check .`
- [ ] Форматтер не ругается: `ruff format --check .`
- [ ] Нет секретов в `.env` (используется `.env.example`)
- [ ] Исключения определены в `exceptions.py` и обработаны на уровне API

### Документация

- [ ] README обновлён: описание API, конфигурация, примеры запросов
- [ ] `.env.example` содержит все переменные с описаниями
- [ ] Структура проекта и архитектура описаны в README

### Безопасность и надёжность

- [ ] Fallback-режим корректно обрабатывает `LLMConnectionError` и `LLMTimeoutError`
- [ ] При `FALLBACK_ENABLED=false` бросается исключение (500)
- [ ] Логи содержат `request_id` для трассировки запросов
- [ ] Таймауты настроены через `LLM_TIMEOUT`
