---
template: structure
version: 1
status: complete
updated: "2026-08-08"
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
│   ├── user.py               Репозиторий пользователей
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
├── schemas/                  Pydantic-схемы валидации
├── services/
│   ├── log.py                LogService (аудит событий)
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
│   └── utils.py              Утилиты
├── middlewares/              Middleware (логирование)
└── utils/                    Утилиты (geo, text, test)
```

Каждая доменная сущность следует паттерну: модель → схема → CRUD-репозиторий → обработчик(и) API.

---

## Структура тестов

Тесты на текущем этапе не реализованы. Зависимости pytest и pytest-asyncio установлены в requirements.txt.

Ожидаемая структура:
```
tests/
├── conftest.py               Корневые фикстуры (db session, test client, auth)
├── unit/                     Юнит-тесты сервисов и CRUD
└── integration/              Интеграционные тесты API
```

---

## Конфигурация и окружение

Конфигурация загружается через pydantic-settings из переменных окружения (`.env`). Объединённый класс `GeneralSettings` наследует 5 групп настроек.

Основные группы настроек:
- Приложение: `PROJECT_NAME`, `PROJECT_HOST`, `PROJECT_PORT`, `API_VERSION`, `BACKEND_CORS_ORIGINS`
- База данных: `POSTGRES_DSN`, `DATABASE_POOL_SIZE`, `DATABASE_MAX_OVERFLOW`, `DATABASE_CREATE_ALL`
- Безопасность: `SECRET_KEY`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `FIRST_SUPERUSER`
- Логирование: `LOG_NAME`, `LOG_LEVEL`, `LOG_PATH`, `LOG_ROTATION_*`
- Внешний сервис: `MESSAGE_API_URL`, `MESSAGE_API_TIMEOUT`

---

## Навигация по репозиторию

Начинать с `app/api/v1/` или `app/api/ext/v1/` — найти обработчик нужной доменной области. Из обработчика следовать в CRUD-репозиторий (`app/crud/`) и модель (`app/models/`).

Для понимания модели данных — смотреть `app/models/`. Для понимания контрактов API — смотреть `app/schemas/`. Для понимания конфигурации — смотреть `app/core/settings/`. Для понимания фоновых задач — смотреть `app/jobs/`.