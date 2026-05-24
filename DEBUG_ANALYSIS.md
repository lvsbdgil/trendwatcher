# Отладка TrendWatcher

## Локальный запуск

Бэкенд:

```bash
cd backend
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
```

Фронтенд:

```bash
cd frontend
npm install
npm run dev
```

Vite dev-сервер проксирует `/api` на бэкенд. По умолчанию — `http://127.0.0.1:8000`.
Если бэкенд запущен на другом адресе — задайте `VITE_API_URL` в `frontend/.env`.
Авторизация работает через httpOnly-куки `tw_session`, запросы должны идти same-origin.

## Переменные окружения

- `FIRECRAWL_API_KEY` — для поиска, скрейпинга и краула через Firecrawl.
- `OPENAI_API_KEY` и опционально `OPENAI_MODEL` — основной LLM-провайдер.
- `OPENROUTER_API_KEY` и опционально `OPENROUTER_MODEL` — альтернативный LLM-провайдер (OpenRouter).
- `GEMINI_API_KEY` — опционально, добавляет Gemini-верификацию топ-сигналов (по умолчанию `gemini-1.5-flash`).
- `ADMIN_LOGIN` и `ADMIN_PASSWORD` или `ADMIN_PASSWORD_HASH` — создание/обновление администратора при старте.
- `SESSION_SECRET` или `JWT_SECRET` — для стабильных сессий. Без явного значения приложение генерирует
  персистентный секрет рядом с базой SQLite.

## Проверка компонентов

Firecrawl:

```bash
curl -X POST http://localhost:8000/api/firecrawl/search \
  -H "Content-Type: application/json" \
  -b "tw_session=<cookie>" \
  -d "{\"query\":\"fintech payments bank launch\",\"limit\":5,\"lang\":\"ru\"}"
```

LLM (требует авторизации):

```bash
curl http://localhost:8000/api/llm-status \
  -b "tw_session=<cookie>"
```

Пайплайн:

```bash
pytest backend/tests
```

## Логи

В dev-режиме анализ пишет в `trendwatcher.analysis` и выводит в `stderr`:

- `request_id`
- запрос и лимит
- id текущего пользователя
- старт/завершение каждого шага пайплайна
- количество URL, извлечённых документов, отфильтрованных документов
- количество карточек сигналов
- stack trace при исключениях бэкенда
- сырой ответ LLM при ошибке JSON-парсинга
- схема финального ответа

Чтобы скрыть dev-диагностику из логов и технические блоки на фронтенде —
задайте `APP_ENV=production` (также работает `ENV=production`).

## Коды ошибок

- `FIRECRAWL_API_KEY_MISSING`
- `FIRECRAWL_REQUEST_FAILED`
- `NO_URLS_FOUND`
- `EXTRACTION_FAILED`
- `NO_VALID_ARTICLES`
- `LLM_API_KEY_MISSING`
- `LLM_REQUEST_FAILED`
- `LLM_JSON_PARSE_FAILED`
- `SCORING_FAILED`
- `AUTH_REQUIRED`
- `UNKNOWN_ERROR`
