# TrendWatcher · Fintech Signal Monitor

Сервис мониторинга финтех-публикаций для продуктовой команды банка.

Входные публикации → очистка → дедупликация → оценка важности → сигнальные карточки → markdown-дайджест.

---

## Содержание

1. [Быстрый старт](#быстрый-старт)
2. [Переменные окружения](#переменные-окружения)
3. [Архитектура](#архитектура)
4. [Пайплайн](#пайплайн)
5. [Финтех-фильтр](#финтех-фильтр-relevance-gate)
6. [Скоринг сигналов](#скоринг-сигналов)
7. [Режимы ввода](#режимы-ввода)
8. [Авторизация и доступ](#авторизация-и-доступ)
9. [API](#api)
10. [Тесты](#тесты)

---

## Быстрый старт

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

API доступен на `http://127.0.0.1:8000`. Swagger UI (`/docs`) включён только при `DEBUG=true`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Фронтенд на `http://127.0.0.1:5173`, проксирует API на `http://127.0.0.1:8000`.



---

## Архитектура

```
backend/
  app/
    main.py                  — FastAPI: app factory, middleware, lifespan, маршруты
    auth.py                  — JWT, bcrypt, session cookie
    deps.py                  — FastAPI dependencies для auth-gating
    db.py                    — sqlite3 connection pool
    schemas.py               — Pydantic-модели
    config.py                — пути, dotenv
    pipeline/                — бизнес-логика (без HTTP)
      runner.py              — оркестратор пайплайна
      cleaner.py             — нормализация текста, удаление HTML
      recency_filter.py      — фильтр по дате публикации (окно 12 месяцев)
      relevance.py           — финтех-gate (LLM или rule-based)
      noise_filter.py        — детектор шума (конференции, awards, funding без продукта)
      deduplicator.py        — дедупликация, canonical_event_key
      classifier.py          — категоризация
      signal_extractor.py    — извлечение сигналов с evidence-цитатами
      scorer.py              — hotness 0–100, алиас importance
      quality_scorer.py      — формула importance и confidence (7 факторов)
      source_quality.py      — primary / trusted_media / reprint
      cards.py               — rule-based карточки сигналов
      llm_enricher.py        — LLM-постпроцессинг и кросс-критика
      verifier.py            — консенсус двух LLM
      digest.py              — markdown-дайджест
      normalizer.py          — нормализация выходных структур (signal card, result)
      logging.py             — AnalysisLogger (структурированные шаги пайплайна)
      errors.py              — AnalysisPipelineError и error_payload
    adapters/                — тонкие HTTP-клиенты (только I/O)
      openai.py              — OpenAI / OpenRouter
      gemini.py              — Google Gemini
      firecrawl.py           — scrape / search / crawl
      _json.py               — парсинг LLM-ответов (JSON / markdown-фенсинг)
    repositories/            — весь SQL сосредоточен здесь
      users.py               — CRUD пользователей
      rate_limit.py          — rate-limit по IP
    routers/                 — HTTP-слой (только входные/выходные данные)
      auth_router.py         — /api/auth/*
      analyze_router.py      — /api/analyze, /api/sample/*
      firecrawl_router.py    — /api/firecrawl/*
      user_router.py         — /api/user/*
      _errors.py             — http_error / handle_pipeline_error
  scripts/
    create_admin.py          — CLI для создания admin-пользователя
  tests/
    test_offline_fallback.py
    test_analysis_resilience.py
    test_firecrawl_service.py
    test_pipeline_quality.py
    test_trendwatcher_demo_quality.py
    test_relevance.py
frontend/
  src/
    App.jsx                  — главный компонент
    api.js                   — HTTP-клиент
    components/              — Header, SignalCard, DigestPanel, SourceTable, ...
    styles.css               — дизайн-система Brief (тёмная, зелёный акцент)
  public/vendor/             — React, ReactDOM, PapaParser (vendored)
data/
  sample_articles.csv        — тестовый набор публикаций
```

---

## Пайплайн

```
Статьи → [1] Cleaner → [2] RecencyFilter → [3] RelevanceGate
       → [4] Deduplicator → [5] SignalExtractor → [6] Scorer
       → [7] Cards → [8] LLM-обогащение → [9] Кросс-критика → [10] Digest
```

1. **Cleaner** — нормализация текста, удаление HTML
2. **RecencyFilter** — отбрасывает статьи старше 12 месяцев и без подтверждённой даты
3. **RelevanceGate** — финтех-фильтр: спорт, рецепты, фильмы, общая политика отсекаются здесь (подробнее — [Финтех-фильтр](#финтех-фильтр-relevance-gate))
4. **Deduplicator** — склейка по `canonical_event_key` и сходству заголовков; `source_quality.py` помечает primary / trusted_media / reprint
5. **SignalExtractor** — извлечение события (запуск продукта, платёжная механика, UX, партнёрство, регулирование) с 1–3 evidence-цитатами; шум (конференции, awards, funding без продукта) получает `decision=reject`
6. **Scorer** — hotness 0–100 (подробнее — [Скоринг сигналов](#скоринг-сигналов))
7. **Cards** — rule-based карточки с headline, summary, draft, sources
8. **LLM-обогащение** (опц.) — LLM-постпроцессинг формулировок топ-сигналов; при ошибке используется rule-based карточка
9. **Кросс-критика** (опц.) — параллельная проверка двумя LLM:
   - Поток A: **Gemini** независимо оценивает каждый сигнал OpenAI (`gemini_grade`, `gemini_note`)
   - Поток B: **OpenAI** играет роль адвоката дьявола — ищет причины не включать свой же сигнал
   - Оба потока выполняются параллельно (`ThreadPoolExecutor`), таймаут 35с на сигнал
   - **Консенсус**: `both_agree` / `openai_holds` / `gemini_flags` / `both_reject`
   - Сигналы со статусом `both_reject` автоматически удаляются из выдачи
   - Полная отказоустойчивость: если любой LLM недоступен — пайплайн продолжает без него
10. **Digest** — markdown с executive summary, top signals, next steps, источниками и статистикой отброшенного шума

---

## Финтех-фильтр (relevance gate)

Перед извлечением сигналов каждая статья проходит через **gate**, который отсекает нефинтех-контент.

Логика:

1. **Pre-check**: если в тексте нет ни одного финтех-якоря (банк, платеж, карта, кредит, ипотека, регулятор и т.д. — ~80 термов RU+EN) → сразу `reject`, LLM не вызывается
2. **LLM-классификатор**: остальные статьи отправляются в gpt-4o-mini с подсказкой «это про финтех?». ~$0.0001 за статью
3. **Fallback**: если LLM недоступен — мягкие правила (≥2 финтех-якоря)

Переменная `RELEVANCE_GATE`:

| Значение | Поведение |
|---|---|
| `llm` (default, если ключ есть) | LLM на каждую статью |
| `rule` | только rule-based |
| `off` | отключить |

Регрессия проверяется набором `data/test_relevance.csv` (25 примеров) и `backend/tests/test_relevance.py` (precision/recall ≥ 0.85 для rule, ≥ 0.92 для LLM).

---

## Скоринг сигналов

`hotness` (алиас `importance`) — детерминированная сумма 7 факторов минус штрафы, диапазон 0–100. Порог попадания в дайджест: **≥ 55**.

| Фактор | Макс | Что считает |
|---|---|---|
| `bank_relevance` | 25 | Категория + product_area + плотность финтех-якорей в тексте |
| `signal_type_weight` | 20 | Тип события: regulation(19) > launch(16) > ux_change(14) > partnership(13) > market(7) |
| `novelty` | 15 | primary source (+2.5), reprint (−5); launch/regulation > market_signal |
| `source_quality` | 15 | source_score/100 × 12.5 + бонус за first-party URL |
| `recency` | 10 | Плавное затухание: 0–1 дн.=10, 7 дн.=8, 30 дн.=6, 90 дн.=4 |
| `evidence_strength` | 10 | Кол-во цитат + объём + наличие цифр + cross-source подтверждения |
| `user_or_market_impact` | 5 | Наличие user_scenario, geography (UK/EU/Global), product_area |

**Штрафы** (вычитаются из суммы): −35 за rejected/is_noise, −6 за одиночную перепечатку, −4 за текст < 200 символов.

Дополнительно каждый сигнал получает `confidence` (0.05–0.98) — оценка доверия к карточке на основе наличия даты, заголовка, длины текста, надёжности источника и cross-source подтверждений. Порог: **≥ 0.45**.

---

## Режимы ввода

| Режим | Описание |
|---|---|
| Вставить текст вручную | Paste текста или загрузка CSV |
| Загрузить по URL через Firecrawl | Список URL → scrape → анализ |
| Firecrawl · поиск | Запрос на русском → Firecrawl находит URL в вебе → scrape → анализ |
| Firecrawl · обход | Корневой URL сайта → crawl всех страниц → анализ |

Есть пресеты для одного клика: «Актуальные финтех-новости», «BNPL и рассрочки», «Цифровой рубль», «Регулирование ЦБ».

**CSV-формат:**

```csv
id,title,source,url,date,snippet,full_text,markdown,fetched_at
```

`full_text`, `markdown`, `fetched_at` — опциональны.

---

## Авторизация и доступ

### Роли и ограничения

| Действие | Гость | User |
|---|---|---|
| Демо-запуск («Запустить пример») | ✓ | ✓ |
| Свои тексты / CSV / URL | — | ✓ |
| Firecrawl search / crawl | — | ✓ |
| Профиль и история | — | ✓ |

- Сессии — JWT в `httpOnly` cookie (`SameSite=Lax`).
- Пароли — bcrypt (никогда не plaintext).
- Login + register rate-limit: 15 попыток в минуту на IP.

### Регистрация и вход

В шапке сайта — кнопки **«Войти»** и **«Регистрация»**. Модалка открывается автоматически, если гость пытается запустить защищённый режим — после входа действие выполняется автоматически.

Правила регистрации: логин 3–32 символа (латиница / цифры / `_ . -`), пароль минимум 6 символов. После регистрации сразу выдаётся cookie-сессия.

### Профиль пользователя

В шапке для авторизованного — аватар + username. По клику открывается popover с метриками, последними действиями, сменой пароля и кнопкой выхода.

### Vite proxy (dev)

В dev-режиме Vite на `:5173` проксирует все `/api/*` на бэкенд (`http://127.0.0.1:8000`). Если бэкенд на другом адресе — задать `VITE_API_URL` в `.env`.

---

## API

| Метод | Путь | Auth | Описание |
|---|---|---|---|
| GET | `/api/health` | public | Health check |
| GET | `/api/llm-status` | user | Статус LLM-ключей |
| GET | `/api/auth/me` | public | Текущий пользователь / `null` |
| POST | `/api/auth/register` | public | Регистрация (cookie-сессия) |
| POST | `/api/auth/login` | public | Логин (cookie-сессия) |
| POST | `/api/auth/logout` | public | Сброс сессии |
| GET | `/api/sample` | public | Тестовый набор статей (данные) |
| POST | `/api/sample/analyze` | public | Демо-анализ встроенного тестового набора |
| POST | `/api/analyze` | user | Запуск пайплайна на пользовательских данных |
| POST | `/api/firecrawl/scrape` | user | Scrape списка URL |
| POST | `/api/firecrawl/search` | user | Поиск по запросу + scrape |
| POST | `/api/firecrawl/crawl` | user | Crawl сайта |
| GET | `/api/user/profile` | user | Профиль + stats + последние события |
| GET | `/api/user/events` | user | История действий текущего пользователя |
| POST | `/api/user/change-password` | user | Смена пароля |

---

## Тесты

```bash
cd backend
pip install -r requirements-dev.txt
pytest tests/
```

| Файл | Что проверяет |
|---|---|
| `test_offline_fallback.py` | Rule-based режим без LLM |
| `test_analysis_resilience.py` | Устойчивость пайплайна при ошибках |
| `test_firecrawl_service.py` | Firecrawl-адаптер |
| `test_pipeline_quality.py` | Качество сигналов на тестовом наборе |
| `test_trendwatcher_demo_quality.py` | End-to-end качество демо-дайджеста |
| `test_relevance.py` | Precision/recall финтех-фильтра (≥ 0.85 rule, ≥ 0.92 LLM) |
