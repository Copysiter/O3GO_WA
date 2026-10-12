---
template: stack
version: 1
status: complete
updated: "2026-10-12"
required_sections:
  - runtime
  - frameworks
  - storage
optional_sections:
  - communication
  - security
  - testing
  - infrastructure
  - solutions
---

# Технологический стек

`status: complete` означает полноту документации; состояние локальной приёмки и открытые операторские условия приведены отдельно ниже.

## Runtime

Python 3.11 с полной поддержкой async/await.

Статический административный frontend использует JavaScript в браузере; дашборд подключается обычными scripts без отдельной сборки.

---

## Основные фреймворки

FastAPI — HTTP-фреймворк, обеспечивающий dependency injection, автогенерацию OpenAPI-документации и валидацию через Pydantic.

Pydantic 2 — валидация входных и выходных данных, сериализация ответов, конфигурация приложения через BaseSettings.

fastapi-filter — продвинутая фильтрация API-запросов с поддержкой операторов (eq, ne, in, like, ilike, gt, gte, lt, lte), сортировки и вложенных фильтров.

APScheduler — планировщик фоновых задач с поддержкой асинхронного выполнения и декораторной регистрации.

jQuery 1.12.4 и Kendo UI 2022.2.510 — существующие локальные библиотеки в `html/static/lib/`. Дашборд использует их AJAX, DateTimePicker, DropDownList, Chart и Window; общие header/навигация/logout — ToolBar, Drawer и Confirm. Новые frontend-пакеты не добавлялись ни в фазе 4 прежнего dashboard-плана, ни при расширении account/file-аудита; версии runtime-технологий сохранены.

---

## Данные и персистентность

PostgreSQL 12 — основное реляционное хранилище доменных данных.

SQLAlchemy 2.0 в асинхронном режиме через asyncpg — ORM и управление сессиями с connection pooling.

Alembic — управление миграциями схемы БД с поддержкой async-режима.

---

## Коммуникация

REST — основной протокол взаимодействия для обеих поверхностей API. Административное API использует стандартные HTTP-методы (GET, POST, PUT, DELETE). Внешнее API использует преимущественно GET-запросы с query-параметрами для совместимости с внешними системами.

HTTP (асинхронный) — взаимодействие с внешним Message API через httpx.

---

## Аутентификация и безопасность

JWT (python-jose, HS256) — аутентификация административного API. Access token (10 дней) передаётся в заголовке Authorization, refresh token (30 дней) — в cookie `refresh-token`.

Подтверждённое исключение Q2: standalone `POST /api/v1/accounts/upload` и `POST /api/v1/accounts/remove` остаются без обязательного JWT. Их новый аудит использует `source=api`, `user_id=NULL` даже при непроверенном Authorization; actor не выводится из имени файла или клиентских параметров. Архивный widget, поля формы и успешные ответы сохранены.

API Key — аутентификация внешнего API. Ключ хранится в модели User (`ext_api_key`), передаётся в заголовке `X-Api-Key` или query-параметре `x_api_key`.

HTTP Basic — опциональная аутентификация через логин/пароль, доступна через зависимость `get_basic_auth_user`.

passlib + bcrypt — хеширование паролей пользователей.

Общий frontend (`html/static/auth.js`) хранит в localStorage token с полями `access_token`, `token_type`, `ts`, `user` и предоставляет синхронные helpers/`window.isAuth`. Проверка входа читает свежий storage, защищает обе ветки ответа от гонок и различает окончательный auth-отказ и временный сбой. `html/static/script.js` выводит имя пользователя как текст внутри статической разметки Kendo. Backend авторизации и его контракт в фазе 4 прежнего dashboard-плана не менялись; детали совместимости приведены в `architecture.md` и `constraints.md`. Общая авторизация/header, видимая ссылка `/dashboard/` и пользовательские auth/CSS/live-правки уже присутствовали в baseline новой задачи и не являются результатом расширения account/file-аудита.

---

## Инструменты тестирования

pytest — основной тестовый фреймворк (зависимость установлена).

pytest-asyncio — поддержка асинхронных тестов.

В `tests/` имеются юнит-тесты и HTTP-проверки с httpx ASGITransport. Stats summary/live, реальные зарегистрированные маршруты, options, общий account/session-аудит и файловые факты двух API проверяются также на изолированной PostgreSQL 12 с явным тестовым DSN. Прежние локальные contract-probes фазы 1 сохранены отдельно; HTTP-проверки подключают api_router без app.main/production lifespan. Fixtures поддерживают два режима: внешнюю транзакцию с rollback и фиксируемую UUID-схему для реальных независимых соединений и commit, с защищённым удалением только этой схемы после теста. Существующие conftest и guards повторно использованы без изменений в новом плане.

### Текущая совместная приёмка account/file-аудита

Канонические команды, явный список файлов и результаты завершённого запуска находятся в `plans/261011-account-file-audit-dashboard/phase5.md`. Это совместная приёмка текущего кода, а не сумма фазовых результатов:

| Проверка | Результат и границы |
|---|---|
| pytest / pytest-asyncio с PostgreSQL 12.22. | 1661 passed в целевой выборке 31 Python-файла, без failed/skipped; весь Python-репозиторий не проверялся. |
| Встроенный Node test runner. | 190 passed: shared auth/header, DashboardApi, DashboardMock и logs event-фильтр. |
| Внешний Playwright / Chromium. | 157 сценариев прошли, 0 failed; итоговый отчёт содержит 28 screenshots. |
| Независимые wire-fixtures → действующие Pydantic DTO. | 244 samples: 240 StatsSummary и 4 StatsLive, включая контракт 17/7 и серверный closed. |
| Flake8 с `--isolated`. | Успешно проверены 25 целевых Python-файлов. |
| Mypy с `--follow-imports=skip --ignore-missing-imports`. | Успешно проверены пять runtime-модулей; весь импортный граф не проверялся. |
| Синтаксис и whitespace. | В приёмке прошли `node --check` девяти JS/CJS-файлов и `git diff --check`. |

Пять runtime-модулей mypy — `app/services/log.py`, `app/services/stats.py`, `app/schemas/stats.py`, `app/api/v1/accounts.py`, `app/crud/account.py`. Полный legacy `app/api/ext/v1/account.py` сохраняет baseline из 34 flake8 и двух mypy замечаний (aiofiles stubs и повторный `download_archive`): сравнение с HEAD зафиксировано в `plans/261011-account-file-audit-dashboard/phase2.md`, файл не включён в успешный полный flake8/mypy-набор фазы 5.

Python 3.11.14, Playwright 1.63.0 и Chromium Headless Shell 153.0.8010.12 использовались как внешние тестовые инструменты из временного `account-file-audit-phase1.pUGxPX`; новых runtime-зависимостей или версий в проект не добавлено. Python-проверки выполнялись из изолированного временного CWD с синтетическими settings и фиктивным app DSN на порту 1, без рабочей `.env` и production lifespan. Собственный PostgreSQL-контейнер фазы 5 остановлен и удалён после проверки пустой public и отсутствия тестовых схем; сохранённый launcher относится к завершённому запуску.

Node VM исполняет фактические auth/header и `html/logs/js/grid.js`/`html/static/filters.js`; `tests/dashboard_api_fixtures.cjs` предоставляет независимые wire-образцы. `tests/dashboard_browser.cjs` использует фактические HTML/scripts, jQuery/Kendo, HTTP/clock fixtures и блокировку неожиданной сети. Текущий отчёт — `/var/folders/71/5hvxcjj52vz0_t_49hcz6shm0000gn/T/opencode/account-file-audit-phase5.5v1UfT/dashboard-phase4-browser-report.json`; исторический basename не меняет принадлежности 157 сценариев и 28 screenshots к фазе 5. Проверен только Chromium с подменённым HTTP: BFCache/storage события синтетические, `seriesClick` вызывается через Kendo dispatcher, pointer hit-testing SVG и Firefox/WebKit не проверялись.

Агрегаты проверены в `SET TRANSACTION READ ONLY`, с контролем одного аналитического statement без commit, независимыми SQL, snapshot-конкурентностью и EXPLAIN после ANALYZE только тестовых таблиц. Итоговые 64 сценария `tests/integration/test_stats_account_file_events.py` охватывают сохранённый message-baseline и смешанную account/file-историю. Синтетический объём, локальные HTTP/SQL/browser-проверки не подтверждают production metadata/retention, SLA, deployment или охват всех обслуживающих workers. При этой синхронизации документации suite заново не запускался.

### Исторические проверки dashboard-плана и унификации 2026-10-05

Следующие результаты относятся к `plans/261003-dashboard-backend/plan.md`, в том числе к разделу «Выполненное поручение пользователя: общий LogService и сохранённая история (2026-10-05)». Упоминания прежних cohort/доставляемости и скрытого меню описывают тот этап, а не текущий контракт.

Read-only характер агрегатов проверяется через `SET TRANSACTION READ ONLY`, перехват SQL и commit; планы фактических scoped/admin-all SELECT сняты через `EXPLAIN (ANALYZE, BUFFERS)` после ANALYZE только тестовых таблиц. Исторические результаты pytest, EXPLAIN и успешных итоговых flake8/mypy фазы 3 приведены в `plans/261003-dashboard-backend/plan.md`. Проверки подтверждают код stats API, но не состояние рабочей БД, production SLA, deployment или работу аудита на всех обслуживающих workers.

В явно одобренной фазе 5 прежнего плана локальная приёмка выполнена на изолированной PostgreSQL 12.22. Тогда добавлены независимые SQL-контроли всех метрик, периодов, cohort/доставляемости/live и календарные HTTP-проверки через реальный api_router. Конкурентные тесты использовали существующую фиксируемую UUID-схему без изменения conftest: тестовая advisory CTE с типизированными binds оборачивала неизменённый service SELECT, а `pg_locks` подтверждал ожидание через реальный commit; следующий SELECT без обёртки видел новые данные в той же READ COMMITTED-транзакции. Отдельно прямые реальные сессионные обработчики проверялись одновременно с обычными stats-чтениями, а каталоги собственной схемы сравнивались до/после. Границы этих проверок описаны в прежнем плане и `constraints.md`.

Историческая приёмка фазы 5 включала Python baseline, новые приёмочные тесты и их совместный запуск, целевые flake8/mypy. После унификации LogService 2026-10-05 основной исполнитель повторил расширенную выборку 25 Python-файлов stats/общего аудита и смежных регрессий: 991 passed; в неё вошли шесть новых на тот момент реальных PostgreSQL upload-сценариев из `tests/integration/test_log_upload_transactions.py`, `test_restore_missing_files` и `test_account_hash`. Это целевая выборка, а не весь Python-репозиторий. Тогдашние flake8 девяти файлов и mypy шести runtime-модулей с `--follow-imports=skip --ignore-missing-imports` прошли. Полный legacy `account.py` сохранял baseline из 34 flake8 и двух mypy замечаний; область проверки и команды сохранены в прежнем плане и `constraints.md`.

EXPLAIN фазы 5 прежнего плана повторён на прежнем синтетическом наборе с ANALYZE только тестовых таблиц; репрезентативность production-объёма и критерии стоимости остаются открытыми, сопоставимый performance benchmark не заявляется. При унификации `tests/test_stats_settings.py` переведён на проверку отсутствия coverage-настройки, игнорирования прежней переменной в окружении процесса и общего UTC-типа; проверки прежнего JSON-словаря дат удалены вместе с настройкой.

После унификации 2026-10-05 встроенный Node test runner проверил `DashboardApi`, demo-provider и фактические shared auth/header scripts в VM; `node --check` использовался для синтаксиса. Прошли 161 Node-тест: 30 адаптера, 16 mock и 115 shared auth/header. Независимые samples из `tests/dashboard_api_fixtures.cjs` заново проверены действовавшими тогда Pydantic DTO: 144 образца, включая 140 StatsSummary и 4 StatsLive. Прежние результаты фаз 4–5 и отсутствие нового Python-запуска при завершении фазы 4 сохранены в `plans/261003-dashboard-backend/plan.md` как исторические.

При унификации 2026-10-05 `tests/dashboard_browser.cjs` запускался через внешний Playwright в Chromium с реальными jQuery/Kendo, HTML и scripts, HTTP/clock fixtures и блокировкой неожиданной сети. Прошли 116/116 сценариев на Chromium 153.0.8010.12, jQuery 1.12.4 и Kendo 2022.2.510. Тогда исправлено устаревшее ожидание видимой ссылки меню: сохранён существовавший на тот момент пользовательский `dashboardNavigation1=''`, прямой дашборд работал. Playwright 1.63.0 переустановлен только во внешнем временном `log-unification.qb4b4W/node_modules`, прежний browser/headless build 1243 повторно использован; зависимости проекта не менялись. Исторические отчёт `log-unification.qb4b4W/dashboard-phase4-browser-report.json` и 24 screenshots, команды и ограничения сохранены в `plans/261003-dashboard-backend/plan.md`; текущая навигация видима.

---

## Инфраструктура и инструменты

Docker и Docker Compose — контейнеризация и локальная среда разработки. Три сервиса: db (PostgreSQL 12), api (FastAPI + Uvicorn), web (Nginx для статических файлов).

Uvicorn — ASGI-сервер для запуска FastAPI-приложения.

orjson — высокопроизводительная сериализация JSON (default_response_class).

pylint, flake8, mypy — статический анализ и линтинг кода.

Историческая приёмка фазы 5 до унификации не меняла runtime-код, рабочую `.env`, БД, миграции и индексы. Последующее поручение пользователя от 2026-10-05 удалило `STATS_COVERAGE_STARTS`, связанные типы/валидатор и пример `.env.example`, централизовало аудит в LogService и уточнило тексты дашборда. `get_summary` больше не принимает `coverage_starts`; общий UTC-тип сохранён. Пользовательское изменение порта 5433 в `docker-compose.yml` не является результатом унификации.

Исторический `plans/261003-dashboard-backend/rollout.md` был обновлён под унификацию LogService и сохранённую историю, но не выполнен; его прежние ownership/cohort, четыре coverage-группы и скрытая ссылка не описывают действующий контракт. Незакрытые рабочие metadata/retention, согласованная стоимость на репрезентативном объёме, окружение, релиз/откат и подтверждение аудита всех обслуживающих upload/start/finish/ban workers сохраняются. Требование ручных coverage-дат отменено.

Текущие план и runbook находятся в `plans/261011-account-file-audit-dashboard/plan.md` и `plans/261011-account-file-audit-dashboard/rollout.md`. Локальные код и приёмка завершены, проектное описание синхронизировано с ними 2026-10-12. Операторский пункт остаётся открытым, общий статус плана — `in-progress`: production metadata/retention, репрезентативный объём/SLA, окружение, комплект релиза/отката и охват аудита внешнего upload, административного account API и start/finish/ban на всех workers не подтверждены. Runbook подготовлен, deployment не выполнен; выпуск описан в порядке backend → frontend, откат — совместимый frontend → backend с сохранением истории. `status: complete` этой спецификации не закрывает эти условия.

---

## Ключевые технологические решения

- Две поверхности API (admin + ext) в одном приложении выбраны ради единой кодовой базы, общих моделей и CRUD-слоя; JWT и API Key задают основные механизмы доступа, а standalone архивы сохраняют исключение Q2, описанное выше.
- Обобщённый CRUD-репозиторий `CRUDBase` выбран ради устранения дублирования SQL-операций и единообразной поддержки фильтрации, пагинации и массовых операций
- fastapi-filter вместо ручного парсинга query-параметров ради декларативной фильтрации с поддержкой вложенных фильтров и сортировки
- Асинхронный режим для всех I/O операций (БД, HTTP, файлы) ради пропускной способности при высокой нагрузке
- APScheduler вместо внешнего task queue ради простоты развёртывания — фоновые задачи выполняются в том же процессе
- LogService объединяет account/file-аудит двух API и прежний session.error-аудит. LogOperation остаётся dataclass состояния с action, source (`api` или `ext_api`, по умолчанию `ext_api`), `error_event`/`persist_error` и nullable actor. Action/UUID связывают запрос, event обозначает отдельный результат; `account.upload` — action внешней загрузки, а не новое DB-событие. `queue_event` сохраняет immutable JSON-снимки файловых фактов, включая отдельный target и `db_outcome` на момент наблюдения; `flush_events`/`report_error` защищённо обрабатывают буфер после освобождения бизнес-транзакции через независимые commit. Их bool подтверждает release, а не запись аудита; сохраняются release latch, первичная ошибка, внешняя cancellation и fallback. Очередь in-memory и best-effort; брокер, outbox и новые runtime-зависимости не вводились. Прежний отдельный SessionErrorAudit удалён при унификации 2026-10-05.
- Upload-specific metadata задаётся allowlist внутри `details`, сессионные операции не копируют request-details. Profile-only действия и их ошибки не создают новых DB-событий, сохраняя техническую диагностику; ошибки загрузки/удаления архивов имеют точные `account.file.upload.error`/`account.file.delete.error` без дублирования общим `account.error`. Q1 сохраняет `account.update` во внешнем update-upload, обоих hash-маршрутах и административном PUT; PUT с переданным `status` по-прежнему выбирает `account.status`.
- Административный `account.delete` записывается в одной транзакции с `AccountCRUD.delete_returning_id` (`DELETE RETURNING`, без собственного commit), с NULL account/session/message FK и snapshot цели в контексте. Отдельные файловые факты single/bulk записываются после release и сохраняют свои targets; новые NULL-FK события переживают удаление аккаунта без изменения старых CASCADE. Ошибки после входа в административный обработчик получают независимый аудит; успешные GET не создают событий и не делают commit ради журнала.
- Stats summary выполняет один read-only CTE SELECT только по `log`; вся историческая область определяется `log.user_id` до агрегации/MIN. Первые подтверждения сообщений и ошибки ищутся по всей сохранённой истории выбранной области до применения нижней границы периода. Anonymous-записи входят только в admin-all. Live отдельно читает текущие аккаунты по владельцу; действующий summary DTO не содержит cohort и отдельного показателя доставляемости. Log-only основа существовала до новой задачи. Все 17 метрик обязательны и nullable в totals/previous/trend; `closed=finished+session_bans` вычисляется на сервере без повторного добавления `auto_finished`.
- Wire `coverage` содержит семь групп с `from: null`: `lifecycle`, `message_events`, `account_errors`, `session_errors`, `account_events`, `account_file_upload_errors`, `account_file_delete_errors`. Три account-error группы учитывают api/ext_api, session.error — только ext_api; дедупликация идёт по event/source/log.user_id/operation_id. Только `missing_operation_id` даёт `partial` и независимо маскирует соответствующую из четырёх error-групп всего затронутого current/previous периода и его buckets. Success-счётчики используют точные события `account.file.upload`, `account.create`, `account.update` без новых требований к source/FK/context; legacy account.error не переклассифицируется. Ручных дат/backfill нет: ноль означает отсутствие записанных событий, `recorded` — подсчитываемость, а не полноту сбора.
- Дашборд проецирует серверные 17/7 в 12 карточек и шесть графиков, сохраняя `null` и предупреждения. Четыре серии сообщений SENT/DELIVERED/UNDELIVERED/FAILED и их поведение сохранены. Logs dropdown содержит 19 вариантов, при этом log.event остаётся произвольной строкой; это набор подсказок, а не whitelist чтения. Явный demo работает только при `?demo=1`.
