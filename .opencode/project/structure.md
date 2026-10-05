---
template: structure
version: 1
status: complete
updated: "2026-10-05"
required_sections:
  - root
  - codebase
optional_sections:
  - testing
  - configuration
  - navigation
---

# Структура репозитория

## Директории верхнего уровня

- `app/` — исходный код Backend API (все слои архитектуры)
- `migrations/` — миграции БД через Alembic
- `upload/` — файлы аккаунтов (архивы .tar.gz и профили .txt)
- `html/` — статические файлы, обслуживаемые Nginx
- `services/` — конфигурация Nginx
- `packages/` — локальные Python-пакеты (atol_logging)
- `.opencode/` — AI-воркспейс (агенты, команды, скилы, контекст проекта)
- `plans/` — планы реализации задач

---

## Организация исходного кода

```
app/
├── main.py                   Точка входа, фабрика FastAPI-приложения
├── lifespan.py               Управление жизненным циклом (init_db, scheduler)
├── deps.py                   FastAPI-зависимости (auth, db, form parsing)
├── api/
│   ├── v1/                   Административное API (JWT auth)
│   │   ├── __init__.py       Регистрация роутеров
│   │   ├── auth.py           Авторизация, токены
│   │   ├── users.py          Пользователи
│   │   ├── accounts.py       Аккаунты (CRUD + файлы)
│   │   ├── sessions.py       Сессии
│   │   ├── messages.py       Сообщения
│   │   ├── androids.py       Android-устройства
│   │   ├── versions.py       Версии приложения
│   │   ├── logs.py           Логи
│   │   ├── stats.py          Read-only summary/live, JWT и локальный SQL 503
│   │   ├── options.py        Опции
│   │   └── base.py           Health-check
│   └── ext/v1/               Внешнее API (API Key auth)
│       ├── account.py        Загрузка/получение/скачивание аккаунтов
│       ├── session.py        Управление сессиями (start/finish/ban)
│       ├── message.py        Создание и статус сообщений
│       ├── account_report.py HTML-отчёты по аккаунтам
│       └── android/          Android-устройства, опции, аккаунты
├── crud/
│   ├── base.py               Обобщённый CRUD-репозиторий (CRUDBase)
│   ├── filter/               Механизм фильтрации (fastapi-filter обёртка)
│   ├── user.py               Репозиторий пользователей и безопасная проекция options
│   ├── account.py            Репозиторий аккаунтов
│   ├── session.py            Репозиторий сессий
│   ├── message.py            Репозиторий сообщений
│   ├── android.py            Репозиторий Android-устройств
│   ├── log.py                Репозиторий логов
│   └── version.py            Репозиторий версий
├── models/                   ORM-модели SQLAlchemy
│   ├── user.py               User (login, password, api_key, roles)
│   ├── account.py            Account (number, status, files, cooldown)
│   ├── session.py            Session (ext_id, status, msg_count)
│   ├── message.py            Message (text, status, info fields)
│   ├── android.py            Android (device info, binding)
│   ├── log.py                Log (event, source, JSONB context)
│   └── version.py            Version (file tracking)
├── schemas/                  Pydantic-схемы валидации, включая DTO stats.py
├── services/
│   ├── log.py                LogService, LogOperation (события и общий аудит ошибок)
│   ├── stats.py              StatsService (период, scope, read-only сохранённая история)
│   └── message/client.py     MessageService (внешний HTTP-клиент)
├── jobs/
│   ├── scheduler.py          APScheduler конфигурация
│   ├── registry.py           Декоратор регистрации задач
│   └── hourly/               Фоновые задачи по расписанию
│       ├── close_inactive_accounts.py
│       └── close_inactive_sessions.py
├── adapters/
│   └── db/                   Адаптер базы данных
│       ├── session.py        AsyncEngine + sessionmaker
│       ├── base_class.py     Base модель
│       └── init_db.py        Инициализация БД при старте
├── core/
│   ├── settings/             Конфигурация (5 групп настроек)
│   ├── logger.py             Структурированное логирование
│   ├── security.py           Хеширование паролей, JWT
│   ├── utc.py                Общий RFC 3339 тип и нормализация UTC для DTO
│   └── utils.py              Утилиты
├── middlewares/              Middleware (логирование)
└── utils/                    Утилиты (geo, text, test)
```

Каждая доменная сущность следует паттерну: модель → схема → CRUD-репозиторий → обработчик(и) API.

`app/services/log.py` содержит весь общий механизм ошибок upload/start/finish/ban: `operation`, `report_error`, безопасную диагностику, освобождение транзакции, защищённое завершение и независимую запись через CRUD. `LogOperation` хранит только состояние отдельного запроса. Upload передаёт тонкий callback в `LogService.upload_details`, сессионные обработчики не передают request-details. Прежний `app/services/session_error.py` удалён; legacy-логирование других account-эндпоинтов сохраняется.

Статический дашборд и общие frontend-компоненты:

```
html/
├── dashboard/
│   ├── index.html            Страница: восемь карточек, шесть графиков, фильтры и live
│   ├── css/style.css         Стили дашборда
│   └── js/
│       ├── api.js            DashboardApi: GET stats/options, отмена, проверка и проекция DTO
│       ├── dashboard.js      Независимые каналы summary/live/users, UTC и lifecycle страницы
│       └── mock_data.js      DashboardMock, загружается только при ?demo=1
└── static/
    ├── auth.js               Синхронные token helpers и защищённый периодический auth probe
    ├── script.js             Общий header/Drawer, текстовая подпись пользователя и logout
    └── lib/                  Существующие локальные jQuery, Kendo и остальные UI-библиотеки
```

---

## Структура тестов

Тесты используют pytest, pytest-asyncio и локальные FastAPI-приложения с httpx ASGITransport. Агрегаты stats, реальные HTTP-маршруты и независимые транзакции account.error/session.error дополнительно проверяются на отдельно заданной PostgreSQL 12; тестовое приложение подключает api_router без app.main/production lifespan.

Основные расположения тестов, включая фазы 1–5 stats и последующую унификацию LogService:
```
tests/
├── test_*.py                            Юнит-тесты сервисов, CRUD и утилит
├── test_session_error_audit.py           Общий LogService-аудит, отмены и fallback; имя сохранено
├── test_stats_settings.py                Отсутствие coverage-настройки, legacy env и общий UTC-тип
├── shared_auth.test.js                   Фактические auth.js/script.js в Node VM, контракт и гонки
├── dashboard_api.test.js                 DashboardApi: transport, DTO, scope/period и отмена
├── dashboard_mock.test.js                Регрессии явного demo-provider
├── dashboard_api_fixtures.cjs             Независимые wire DTO samples для frontend-проверок
├── dashboard_browser.cjs                 Внешний Playwright/Chromium, реальные shared scripts и Kendo
├── api/
│   ├── v1/                              Проверки административного API
│   │   ├── test_stats.py                Сохранённые локальные contract-probes фазы 1
│   │   ├── test_stats_api.py            Реальные stats-маршруты, JWT, scope, SQL 503
│   │   └── test_user_options.py         Безопасная проекция и область options/user
│   └── ext/v1/                          Проверки внешнего API
│       └── test_session_error.py        HTTP-сценарии ошибок и неизменности сессионных операций
└── integration/
    ├── conftest.py                      Opt-in PostgreSQL fixtures: rollback и фиксируемая UUID-схема
    ├── test_stats_fixtures.py           Проверки fixtures ORM-схемы, данных и scope
    ├── test_stats_aggregates.py         Выполнение summary/live на PostgreSQL
    ├── test_stats_edges.py              Tenant, DST, global-first, error gaps и live
    ├── test_stats_explain.py            Read-only транзакция и EXPLAIN тестовых данных
    ├── test_stats_api_postgres.py       Реальные HTTP-маршруты с PostgreSQL
    ├── test_stats_acceptance.py         Независимые контрольные SQL, метрики/buckets, календарь и роли
    ├── test_stats_concurrency.py        Конкурентный snapshot, реальные операции и собственные metadata
    ├── test_log_upload_transactions.py  Шесть реальных upload-сценариев общего аудита
    └── test_session_error_transactions.py Проверки независимых соединений, commit, rollback и FK
```

В `tests/integration/conftest.py` режим stats откатывает внешнюю транзакцию. Режим `stats_session_factory` фиксирует собственную UUID-схему для настоящих независимых commit и после проверок защиты удаляет только её через `DROP SCHEMA ... CASCADE`; рабочая БД и `public` не удаляются. Эти режимы и conftest на фазе 3 не менялись. Интеграционные файлы `test_stats.py` и `test_stats_api.py` получили имена `test_stats_aggregates.py` и `test_stats_api_postgres.py`, чтобы избежать pytest basename collision с API-тестами; старые contract-probes сохранены.

В фазе 5 добавлены `test_stats_acceptance.py` и `test_stats_concurrency.py`; существующий conftest, guards и фиксируемая UUID-схема повторно использованы без изменений. Первый файл сверяет current/previous, каждый bucket, cohort, доставляемость и live с независимыми SQL и проверяет реальные маршруты через api_router/PostgreSQL. Второй проверяет snapshot одного SELECT через конкурентный commit, прямые start на существующем аккаунте → finish → ban → ban одновременно с обычными stats-чтениями и неизменность каталогов только собственной схемы до/после. Это не сверка production metadata и не нагрузочный HTTP/auth-тест.

После унификации существующие helper/сессионные тесты переведены на LogService с сохранением имён файлов. Новый `test_log_upload_transactions.py` повторно использует фиксируемую UUID-схему для шести случаев create/update: rollback до независимого writer, доверенные существующие/новые FK, реально выполненный commit с потерянным подтверждением и post-commit HTTP 201. В update проверяются три ошибки с одним operation UUID; аудит привязан к вызывающему пользователю, чужой аккаунт сохраняется. `test_stats_settings.py` проверяет отсутствие поля settings и игнорирование прежней переменной в окружении процесса, а также действующую UTC-валидацию; обработку всех дополнительных dotenv-полей эти проверки не утверждают.

JavaScript-проверки используют встроенный Node test runner; shared auth/header исполняются непосредственно из исходных файлов в VM. Browser runner проверяет страницу и login widgets с фактическими библиотеками и HTTP/clock fixtures. Playwright и browser-артефакты размещены вне проекта; точные результаты, команды и пути отчётов ведутся в `plans/261003-dashboard-backend/plan.md`, границы проверки — в `constraints.md`.

Исторические результаты фаз 3–5 сохранены в плане. После унификации расширенная выборка содержит 25 Python-файлов stats/общего аудита и смежных регрессий, включая `test_restore_missing_files` и `test_account_hash`; это не весь Python-репозиторий. Повторены полные Node/browser-проверки и валидация 144 wire samples (140 StatsSummary и 4 StatsLive); browser runner ожидает пользовательскую скрытую ссылку меню при работающем прямом `/dashboard/`. Целевые flake8/mypy и оставшиеся baseline-замечания legacy `account.py` описаны в `constraints.md`. Текущий browser-отчёт и 24 screenshots находятся во внешнем `log-unification.qb4b4W`; basename `dashboard-phase4-browser-report.json` исторический и не обозначает фазу запуска.

---

## Конфигурация и окружение

Конфигурация загружается через pydantic-settings из переменных окружения (`.env`). Объединённый класс `GeneralSettings` наследует 5 групп настроек.

Основные группы настроек:
- Приложение: `PROJECT_NAME`, `PROJECT_HOST`, `PROJECT_PORT`, `API_VERSION`, `BACKEND_CORS_ORIGINS`
- База данных: `POSTGRES_DSN`, `DATABASE_POOL_SIZE`, `DATABASE_MAX_OVERFLOW`, `DATABASE_CREATE_ALL`
- Безопасность: `SECRET_KEY`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `FIRST_SUPERUSER`
- Логирование: `LOG_NAME`, `LOG_LEVEL`, `LOG_PATH`, `LOG_ROTATION_*`
- Внешний сервис: `MESSAGE_API_URL`, `MESSAGE_API_TIMEOUT`

`STATS_COVERAGE_STARTS`, связанные типы и валидатор удалены из `app/core/settings/app_settings.py`; пример в `.env.example` также удалён, рабочая `.env` не менялась. `get_summary` не принимает `coverage_starts`; ручные даты начала сбора для статистики не нужны. Общий `UTCDateTime` остаётся в `app/core/utc.py` и используется DTO. Опциональный `STATS_TEST_EXPLAIN_DIR` используется только тестом EXPLAIN для проверенного временного каталога; по умолчанию артефакт размещается в pytest tmp_path, это не настройка приложения.

---

## Навигация по репозиторию

Начинать с `app/api/v1/` или `app/api/ext/v1/` — найти обработчик нужной доменной области. Из обработчика следовать в CRUD-репозиторий (`app/crud/`) и модель (`app/models/`).

Для понимания модели данных — смотреть `app/models/`. Для понимания контрактов API — смотреть `app/schemas/`. Для понимания конфигурации — смотреть `app/core/settings/`. Для понимания фоновых задач — смотреть `app/jobs/`.

Для дашборда начинать с `html/dashboard/index.html`, затем `js/dashboard.js` и `js/api.js`; общая авторизация и header находятся в `html/static/auth.js` и `html/static/script.js`. `mock_data.js` относится только к явному demo-режиму.

Для ошибок upload/start/finish/ban начинать с `app/services/log.py`, затем проследить состояние `LogOperation` в `app/api/ext/v1/account.py` и `session.py`. Для семантики сохранённых счётчиков и `missing_operation_id` смотреть `app/services/stats.py`, для совместимого wire `coverage` с `from: null` — `app/schemas/stats.py`; фронтенд сохраняет предупреждения и `null`, но не представляет legacy `from` как гарантированную дату сбора.

Для статуса приёмки и канонических команд использовать `plans/261003-dashboard-backend/plan.md`. Операторский `plans/261003-dashboard-backend/rollout.md` описывает необходимые metadata, особенности запуска, включение общего LogService-аудита, smoke-проверки сохранённой истории и откат; он подготовлен, но не выполнен. Рабочие metadata/retention, согласованная стоимость, релиз/откат и подтверждение аудита всех workers остаются открытыми; общая реализация — `in_progress`. Прежнего условия ручного подтверждения coverage-дат больше нет.
