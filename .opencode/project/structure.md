---
template: structure
version: 1
status: complete
updated: "2026-10-12"
required_sections:
  - root
  - codebase
optional_sections:
  - testing
  - configuration
  - navigation
---

# Структура репозитория

`status: complete` означает полноту документации. Навигация к текущей локальной приёмке и незавершённым операторским пунктам приведена в конце файла.

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
│   ├── v1/                   Административное API (JWT, файловые исключения)
│   │   ├── __init__.py       Регистрация роутеров
│   │   ├── auth.py           Авторизация, токены
│   │   ├── users.py          Пользователи
│   │   ├── accounts.py       Account/file-аудит, CRUD, single/bulk delete и файлы
│   │   ├── sessions.py       Сессии
│   │   ├── messages.py       Сообщения
│   │   ├── androids.py       Android-устройства
│   │   ├── versions.py       Версии приложения
│   │   ├── logs.py           Чтение журнала, прежний owner-scope через account
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
│   ├── account.py            AccountCRUD, включая delete_returning_id без commit
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
│   ├── log.py                LogService/LogOperation, queue_event/flush_events и ошибки
│   ├── stats.py              Log-only summary 17/7 и live по текущему владельцу
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

`app/services/log.py` содержит общий account/file-аудит двух API и прежний аудит start/finish/ban: `operation`, `operation_context`, `queue_event`, `flush_events`, `report_error`, безопасную диагностику, release и независимую запись через CRUD. `LogOperation` хранит только состояние запроса с action/source, nullable actor и настройками `error_event`/`persist_error`. `queue_event` не выполняет I/O: immutable JSON-снимок фиксирует отдельный target и `db_outcome` в момент наблюдения файла; последующий commit его не переписывает. `flush_events`/`report_error` защищённо обрабатывают весь буфер после освобождения бизнес-транзакции, сохраняя cancellation, release latch и fallback; их bool означает release, а не успех аудита.

Внешний upload в `app/api/ext/v1/account.py` передаёт allowlist-метаданные через `LogService.upload_details`, связывает file/account события одним UUID и сохраняет архивный факт независимо от последующих profile/DB-этапов. Profile-only действия/ошибки не создают новых DB-событий; архивная ошибка не дублируется общим `account.error`. Сессионные обработчики не передают request-details. Прежний `app/services/session_error.py` удалён при унификации 2026-10-05; hash-обработчики и остальное legacy-логирование внешнего account API не перерабатывались новым планом.

Административный `app/api/v1/accounts.py` добавляет ошибки после входа в обработчик, включая GET error-only без success-событий чтения и без commit ради журнала. Single/bulk delete используют `AccountCRUD.delete_returning_id` из `app/crud/account.py`: узкий `DELETE RETURNING` синхронизирует identity map, а commit остаётся у обработчика. `account.delete` записывается атомарно с удалением с NULL account/session/message FK; контекст содержит snapshot цели. Файловые факты с отдельными immutable targets буферизуются до release. Новые NULL-FK delete/file записи переживают удаление аккаунта; прежние CASCADE и owner-scope `app/api/v1/logs.py` через связанный account сохраняются.

Q1 сохраняет `account.update` для внешнего update-upload, обоих hash-маршрутов и административного PUT; присутствие `status` в PUT по-прежнему выбирает `account.status`. Q2 сохраняет standalone `POST /api/v1/accounts/upload` и `POST /api/v1/accounts/remove` без обязательного JWT и с новым actor=`user_id=NULL`, независимо от непроверенных credentials. Архивный widget и его form/успешные response-контракты сохранены.

`app/services/stats.py` агрегирует summary одним read-only CTE SELECT только по `log`: вся историческая область задаётся `log.user_id` до агрегации/MIN, anonymous-записи учитываются только в admin-all. Первые подтверждения сообщений и ошибки ищутся во всей сохранённой истории выбранной области до применения нижней границы периода. Live использует текущего владельца аккаунта отдельно от периода. `app/schemas/stats.py` определяет 17 обязательных nullable-метрик и семь coverage-групп с `from: null`; cohort и отдельного показателя доставляемости в действующем summary DTO нет. Log-only основа уже существовала в baseline новой задачи.

Статический дашборд и общие frontend-компоненты:

```
html/
├── dashboard/
│   ├── index.html            Страница: 12 карточек, шесть графиков, фильтры и live
│   ├── css/style.css         Стили дашборда
│   └── js/
│       ├── api.js            DashboardApi: GET stats/options, отмена, проверка и проекция DTO
│       ├── dashboard.js      Независимые каналы summary/live/users, UTC и lifecycle страницы
│       └── mock_data.js      DashboardMock, загружается только при ?demo=1
├── logs/js/grid.js           Журнал, 19 вариантов event-фильтра
└── static/
    ├── auth.js               Синхронные token helpers и защищённый периодический auth probe
    ├── script.js             Header/Drawer с видимой ссылкой dashboard, текст имени и logout
    ├── filters.js            Общая сериализация фильтров, включая произвольный строковый event
    └── lib/                  Существующие локальные jQuery, Kendo и остальные UI-библиотеки
```

`api.js` требует все 17 метрик и семь coverage-групп; `dashboard.js` отображает серверный `closed`, независимые summary/live/users и четыре отдельно маскируемые error-группы. График сообщений сохраняет четыре серии SENT/DELIVERED/UNDELIVERED/FAILED, порядок, оформление, tooltip и действие клика. `html/logs/js/grid.js` содержит три прежние группы, девять прежних событий и семь новых вариантов; `log.event` по-прежнему допускает произвольные строки при чтении и сериализации, dropdown не является whitelist.

Ссылка `/dashboard/` в общем меню сейчас видима. Она, log-only основа и пользовательские auth/CSS/live-изменения уже присутствовали в baseline `plans/261011-account-file-audit-dashboard/`; расширение аудита и дашборда их не вводило. Shared auth/header, архивная форма и существующие стили сохранены; актуальные детали baseline и границы frontend-проверки находятся в `baseline.md` и `phase4.md` этого плана.

---

## Структура тестов

Тесты используют pytest, pytest-asyncio и локальные FastAPI-приложения с httpx ASGITransport. Агрегаты stats, реальные HTTP-маршруты, независимые транзакции account/file/session-аудита и transactional account.delete дополнительно проверяются на отдельно заданной PostgreSQL 12; тестовое приложение подключает api_router без app.main/production lifespan.

Основные расположения тестов, включая прежние stats/LogService-регрессии и текущий account/file-аудит:
```
tests/
├── test_*.py                            Юнит-тесты сервисов, CRUD и утилит
├── test_session_error_audit.py           Общий LogService-аудит, отмены и fallback; имя сохранено
├── test_log_file_audit.py                Явные source/event, nullable actor, immutable очередь и release
├── test_account_file_audit_contract.py   Независимые legacy-счётчики и зафиксированный целевой контракт
├── account_file_audit_baseline.json      Immutable baseline сообщений и planned_contract 17/7, 12 карточек
├── test_stats_contract.py                Действующие DTO 17/7, обязательность/NULL/extra/frozen
├── test_stats_service.py                 Период, scope, SQL-форма и сборка stats
├── test_stats_settings.py                Отсутствие coverage-настройки, legacy env и общий UTC-тип
├── shared_auth.test.js                   Фактические auth.js/script.js в Node VM, контракт и гонки
├── dashboard_api.test.js                 DashboardApi: transport, DTO, scope/period и отмена
├── dashboard_mock.test.js                Регрессии явного demo-provider
├── log_event_options.test.js             19 вариантов event, произвольные строки и сериализация фильтров
├── dashboard_api_fixtures.cjs             Независимые wire DTO samples для frontend-проверок
├── dashboard_browser.cjs                 Внешний Playwright/Chromium, реальные shared scripts и Kendo
├── api/
│   ├── v1/                              Проверки административного API
│   │   ├── test_account_audit_events.py  Success/error, GET error-only, delete/files, profiles и Q2
│   │   ├── test_stats.py                Сохранённые локальные contract-probes фазы 1
│   │   ├── test_stats_api.py            Реальные stats-маршруты, JWT, scope, SQL 503
│   │   └── test_user_options.py         Безопасная проекция и область options/user
│   └── ext/v1/                          Проверки внешнего API
│       ├── test_account_upload.py       Архивные факты/ошибки, profile-only исключение и HTTP 201
│       ├── test_account_hash.py         Сохранённый account.update обоих hash-маршрутов по Q1
│       └── test_session_error.py        HTTP-сценарии ошибок и неизменности сессионных операций
└── integration/
    ├── conftest.py                      Opt-in PostgreSQL fixtures: rollback и фиксируемая UUID-схема
    ├── test_stats_fixtures.py           Проверки fixtures ORM-схемы, данных и scope
    ├── test_stats_log_only.py           Только log в summary, actor-scope, sparse rows и DTO без cohort
    ├── test_stats_account_file_events.py 64 сценария: message-baseline и смешанная история 17/7
    ├── test_stats_aggregates.py         Выполнение summary/live на PostgreSQL
    ├── test_stats_edges.py              Tenant, DST, global-first, error gaps и live
    ├── test_stats_explain.py            Read-only транзакция и EXPLAIN тестовых данных
    ├── test_stats_api_postgres.py       Реальные HTTP-маршруты с PostgreSQL
    ├── test_stats_acceptance.py         Независимые контрольные SQL, метрики/buckets, календарь и роли
    ├── test_stats_concurrency.py        Конкурентный snapshot, реальные операции и собственные metadata
    ├── test_log_upload_transactions.py  14 реальных upload-сценариев account/file-аудита
    ├── test_admin_account_audit_transactions.py Delete/rollback/CASCADE, targets и anonymous HTTP
    └── test_session_error_transactions.py Проверки независимых соединений, commit, rollback и FK
```

В `tests/integration/conftest.py` режим stats откатывает внешнюю транзакцию. Режим `stats_session_factory` фиксирует собственную UUID-схему для настоящих независимых commit и после проверок защиты удаляет только её через `DROP SCHEMA ... CASCADE`; рабочая БД и `public` не удаляются. Эти режимы и conftest не менялись ни на фазе 3 прежнего dashboard-плана, ни в новом account/file-плане. Интеграционные файлы `test_stats.py` и `test_stats_api.py` ранее получили имена `test_stats_aggregates.py` и `test_stats_api_postgres.py`, чтобы избежать pytest basename collision с API-тестами; старые contract-probes сохранены.

### Текущая приёмка account/file-аудита

`test_log_file_audit.py` проверяет source/action/event, nullable actor, immutable snapshots, защищённую обработку всего буфера, release latch, cancellation/fallback и profile-only диагностику. `test_account_file_audit_contract.py` читает неизменяемый `account_file_audit_baseline.json`: legacy-счётчики и message chart зафиксированы отдельно от planned_contract; это не подмена проверок действующего DTO, находящихся в `test_stats_contract.py` и API/SQL-тестах.

`tests/api/v1/test_account_audit_events.py` проверяет административные create/PUT, ошибки обработчиков GET без success/commit, single/bulk delete, отсутствие profile-only DB-событий и Q2: standalone архивы без обязательного JWT с NULL actor даже при непроверенных credentials. `tests/integration/test_admin_account_audit_transactions.py` проверяет реальные DELETE/commit/rollback/CASCADE, NULL доменные FK, per-target snapshots, unknown commit, отмены и anonymous HTTP. `tests/integration/test_log_upload_transactions.py` расширен с шести исторических до 14 PostgreSQL-сценариев; внешний upload/hash и прежний session-аудит сохраняют отдельные регрессии.

`tests/integration/test_stats_account_file_events.py` содержит 64 сценария: три сохранённых message-baseline и 61 смешанной истории. Проверяются 17 метрик/семь групп, source api/ext_api, NULL actor, legacy context={}, совпадающие operation IDs и независимое маскирование четырёх error-групп в current/previous/buckets. `test_stats_log_only.py` проверяет actor-scope по log.user_id, sparse rows, повторное связывание периодов/scopes и отсутствие cohort/delivery DTO. Текущие `test_stats_acceptance.py`, `test_stats_explain.py` и `test_stats_concurrency.py` проверяют независимые SQL-контроли, read-only statement, snapshot, session-операции и каталоги собственной тестовой схемы; production metadata/SLA этим не подтверждаются.

JavaScript-набор использует встроенный Node test runner. `log_event_options.test.js` исполняет фактические `grid.js`/`filters.js` в VM и проверяет 19 вариантов, прежний порядок, произвольные строки, auth и сериализацию. Dashboard/shared auth-тесты дополняются независимыми `dashboard_api_fixtures.cjs`; browser runner использует копию legacy message-baseline, расширенную до 17/7, без изменения буквальных значений четырёх серий.

Каноническая совместная приёмка находится в `plans/261011-account-file-audit-dashboard/phase5.md`: 1661 Python-тест в 31 файле, 190 Node, 157 Chromium-сценариев и 244 DTO samples (240 StatsSummary + 4 StatsLive). Успешны flake8 25 файлов, mypy пяти runtime-модулей с `--follow-imports=skip --ignore-missing-imports` и `node --check` девяти JS/CJS-файлов. Это целевые наборы: полный legacy `app/api/ext/v1/account.py` сохраняет 34 flake8 и два mypy замечания baseline, подтверждённые в `phase2.md` нового плана, и не входит в успешный полный статический набор. При синхронизации документации тесты заново не запускались.

Текущий browser-отчёт и его 28 screenshots находятся во внешнем `/var/folders/71/5hvxcjj52vz0_t_49hcz6shm0000gn/T/opencode/account-file-audit-phase5.5v1UfT`; basename `dashboard-phase4-browser-report.json` исторический. Внешние Python 3.11.14, Playwright 1.63.0 и Chromium Headless Shell 153.0.8010.12 не добавлялись в runtime-зависимости проекта. Проверены фактические HTML/jQuery/Kendo/scripts с HTTP/clock fixtures только в Chromium; BFCache/storage события синтетические, `seriesClick` вызывается через Kendo dispatcher, pointer hit-testing SVG и Firefox/WebKit не проверялись. Команды, изоляция Python/PostgreSQL и завершённое удаление собственного тестового контейнера описаны в `phase5.md`.

### Исторические проверки dashboard-плана и унификации 2026-10-05

В фазе 5 `plans/261003-dashboard-backend/plan.md` добавлены `test_stats_acceptance.py` и `test_stats_concurrency.py`; существующий conftest, guards и фиксируемая UUID-схема повторно использованы без изменений. Первый файл тогда сверял current/previous, каждый bucket, cohort, доставляемость и live с независимыми SQL и проверял реальные маршруты через api_router/PostgreSQL. Второй проверял snapshot одного SELECT через конкурентный commit, прямые start на существующем аккаунте → finish → ban → ban одновременно с обычными stats-чтениями и неизменность каталогов только собственной схемы до/после. Это история прежней приёмки, не описание действующего cohort-контракта, не сверка production metadata и не нагрузочный HTTP/auth-тест.

При унификации 2026-10-05 существующие helper/сессионные тесты переведены на LogService с сохранением имён файлов. Новый на тот момент `test_log_upload_transactions.py` повторно использовал фиксируемую UUID-схему для шести случаев create/update: rollback до независимого writer, доверенные существующие/новые FK, реально выполненный commit с потерянным подтверждением и post-commit HTTP 201. В update проверялись три ошибки с одним operation UUID; аудит был привязан к вызывающему пользователю, чужой аккаунт сохранялся. `test_stats_settings.py` переведён на проверку отсутствия поля settings и игнорирования прежней переменной в окружении процесса, а также действующей UTC-валидации; обработку всех дополнительных dotenv-полей эти проверки не утверждают.

Исторические JavaScript-проверки использовали встроенный Node test runner; shared auth/header исполнялись непосредственно из исходных файлов в VM. Browser runner проверял страницу и login widgets с фактическими библиотеками и HTTP/clock fixtures. Playwright и browser-артефакты размещались вне проекта; точные результаты, команды и пути прежних отчётов сохранены в `plans/261003-dashboard-backend/plan.md`, границы проверки — также в `constraints.md`.

Исторические результаты фаз 3–5 сохранены в `plans/261003-dashboard-backend/plan.md`; результаты унификации — в его разделе «Выполненное поручение пользователя: общий LogService и сохранённая история (2026-10-05)». Тогда прошли 991 проверка в 25 Python-файлах stats/общего аудита и смежных регрессий, включая `test_restore_missing_files` и `test_account_hash`, 161 Node-тест, 116/116 browser-сценариев и валидация 144 wire samples (140 StatsSummary и 4 StatsLive) действовавшими DTO. Это не весь Python-репозиторий и не результаты текущей задачи. Browser runner тогда ожидал пользовательскую скрытую ссылку меню при работающем прямом `/dashboard/`; сейчас ссылка видима. Тогдашние целевые flake8 девяти файлов/mypy шести модулей и baseline-замечания legacy `account.py` сохранены в прежнем плане и `constraints.md`. Исторический browser-отчёт `log-unification.qb4b4W/dashboard-phase4-browser-report.json` и 24 screenshots относятся к той унификации.

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

Для account/file-аудита начинать с `app/services/log.py`: `operation_context` отделяет success-контекст, `queue_event` фиксирует факты, `flush_events`/`report_error` завершают аудит после release. Затем проследить `LogOperation` в `app/api/ext/v1/account.py`, `app/api/v1/accounts.py` и прежнем `app/api/ext/v1/session.py`. Для transactional delete перейти в `app/crud/account.py` к `delete_returning_id`, для регрессионных проверок — в `tests/test_log_file_audit.py`, `tests/api/v1/test_account_audit_events.py` и `tests/integration/test_admin_account_audit_transactions.py`.

Для 17 метрик, SQL `closed=finished+session_bans`, actor-scope всей истории и четырёх независимо маскируемых error-групп смотреть `app/services/stats.py`; три account-error группы допускают api/ext_api, session.error — только ext_api, дедупликация идёт по event/source/log.user_id/operation_id. Для семи wire coverage-групп с `from: null` — `app/schemas/stats.py`, для независимых ожиданий — `tests/integration/test_stats_account_file_events.py` и `test_stats_log_only.py`. Только `missing_operation_id` маскирует соответствующую error-группу всего затронутого периода и его buckets; frontend сохраняет предупреждения и `null`, а legacy `from` не представляет как дату полного сбора. Для 19 event-подсказок и строкового контракта перейти в `html/logs/js/grid.js`, `html/static/filters.js` и `tests/log_event_options.test.js`.

Текущий статус и контракты ведутся в `plans/261011-account-file-audit-dashboard/plan.md`, `contract.md` и `admin-audit.md`; пофазные свидетельства — в `phase2.md`, `phase3.md`, `phase4.md`, окончательные команды и результаты — в `phase5.md` того же каталога. Код и локальная приёмка завершены, проектное описание синхронизировано 2026-10-12. `plans/261011-account-file-audit-dashboard/rollout.md` подготовлен, но не выполнен: backend → frontend при выпуске, совместимый frontend → backend при откате без удаления истории. Операторский пункт остаётся открытым, deployment не выполнен; рабочие metadata/retention, репрезентативный объём/SLA, окружение, релиз/откат и подтверждение аудита всех workers не закрыты локальной приёмкой.

`plans/261003-dashboard-backend/plan.md` и `plans/261003-dashboard-backend/rollout.md` сохранены как исторические источники прежних результатов и открытых production-условий. Их cohort/ownership, четыре coverage-группы и скрытое меню не являются текущим контрактом. Условия ручного подтверждения coverage-дат больше нет; `status: complete` этой спецификации означает завершённость документации, а не deployment.
