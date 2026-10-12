---
template: conventions
version: 1
status: complete
updated: "2026-10-12"
required_sections:
  - principles
  - boundaries
optional_sections:
  - style
  - naming
  - testing
  - documentation
  - forbidden
---

# Конвенции проекта

`status: complete` обозначает полноту документации, а не завершённый релиз. Обновление проектных спецификаций одобрено пользователем 2026-10-12; операторские условия rollout остаются открытыми.

## Инженерные принципы

Проект придерживается принципа разделения ответственности между слоями: API принимает и валидирует, CRUD работает с данными, сервисы координируют поперечные задачи. Простота предпочтительнее универсальности — обобщённый CRUD-репозиторий покрывает 90% операций без необходимости написания кастомных запросов.

Асинхронность является нормой для всех I/O операций. Явное управление транзакциями: операции выполняются с `commit=False`, коммит вызывается явно в обработчике после всех изменений.

---

## Стиль кода

Python-код следует PEP 8 с контролем через pylint и flake8. Статическая проверка типов через mypy.

Все публичные интерфейсы (методы CRUD, обработчики API) типизированы через аннотации типов. Docstring используются для документирования эндпоинтов API с описанием функциональности, безопасности и зависимостей.

---

## Соглашения по именованию

- Файлы: snake_case (`account.py`, `auth.py`, `close_inactive_sessions.py`)
- Классы ORM-моделей: PascalCase, единственное число (`User`, `Account`, `Session`, `Message`)
- Классы схем: PascalCase с интентом (`AccountCreate`, `AccountUpdate`, `AccountFilter`, `AccountList`)
- Репозитории: snake_case, модуль именован по сущности (`app/crud/account.py`)
- CRUD-экземпляры: snake_case, имя сущности (`account = AccountCRUD()`)
- Статусы: IntEnum с описательными именами (`AccountStatus.AVAILABLE`, `MessageStatus.SENT`)
- Переменные окружения: UPPER_SNAKE_CASE (`POSTGRES_DSN`, `SECRET_KEY`, `LOG_LEVEL`)

---

## Границы ответственности

Обработчики API принимают запрос, проверяют аутентификацию, валидируют данные, применяют бизнес-логику и делегируют CRUD-операции. На текущем этапе бизнес-логика (проверки уникальности, каскадные обновления, управление файлами) находится в обработчиках, а не вынесена в сервисный слой.

CRUD-слой является основным слоем SQL-доступа к доменным данным. Базовый класс `CRUDBase` предоставляет стандартные CRUD-методы с поддержкой фильтрации, пагинации, массовых операций. Конкретные репозитории привязывают модель и класс фильтра. `UserCRUD.get_options` использует SELECT только text/value, без секретных колонок User; область задаётся сервером по аутентифицированному пользователю. Member получает только себя независимо от клиентских параметров, admin — также неактивных владельцев. Пустые name/login имеют fallback `Пользователь {id}`, порядок — lower(label), id.

Узкий `AccountCRUD.delete_returning_id` выполняет `DELETE RETURNING` без commit и синхронизирует identity map. Отсутствующий RETURNING не считается успешным удалением. Обработчик сохраняет response/target-снимки до удаления и управляет общей транзакцией DELETE и `account.delete`.

Сервисы реализуют поперечную функциональность: LogService записывает аудит-события, MessageService взаимодействует с внешним API.

Общий account/file-аудит внешнего и административного API и `session.error` для внешних start/finish/ban принадлежат `LogService` в `app/services/log.py`. `operation(action, user_id, source)` создаёт отдельный dataclass `LogOperation` только со состоянием запроса: UUID, nullable actor, source, stage, исход commit, выбор/код ошибки, доверенные/новые FK, очередь фактов и состояние release. Методы `operation_context`, `queue_event`, `flush_events`, `report_error` и диагностика остаются в сервисе, а не в объекте состояния или endpoint. Default source сессионных callers — `ext_api`, административные задают `api`. Прежний `app/services/session_error.py` удалён. Upload передаёт тонкий details callback через `LogService.upload_details`, сессионные операции не передают request-details.

`operation_context` отделяет разрешённые метаданные успеха, не утверждая будущий commit. `queue_event` без I/O/release замораживает JSON-снимок identity/event/source/stage/error/details/target и `db_outcome` в момент наблюдения. Позднейшие изменения target, состояния операции или исключения не переписывают факт; исходное исключение сохраняется отдельно для диагностических notes. Account FK задаётся явно и не наследуется при flush; известный новый FK до подтверждённого business commit исключается. `transaction_released` относится к моменту финализации. В частности, файловый факт admin-delete остаётся `not_committed`, даже если бизнес-транзакция позднее успешно завершилась.

`flush_events` и `report_error` сначала подтверждают освобождение бизнес-транзакции через rollback и при необходимости close, затем используют существующий `record_independent`: запись проходит через CRUD в собственной сессии, явный commit выполняет LogService. Их bool означает release, а не успех аудита. Защищённая финализация обрабатывает весь буфер до передачи внешней cancellation, включая повторные отмены; обычный отказ одного writer не теряет следующие факты. Неизвестный audit commit не повторяется. При неподтверждённом release latch блокирует последующие writers той же операции и оставляет fallback для неподтверждённых фактов. Business outcome переводится из `not_committed` в `unknown` до ожидания commit и в `committed` только после успешного возврата; независимый аудит не ссылается на неподтверждённые новые строки.

Namespace различает бизнес-события `account.create/update/status/delete`, общую ошибку `account.error` и архивные `account.file.upload/delete` с соответствующими `.error`. Файловая ошибка не дублируется общим `account.error`; последующий отдельный SQL/response/audit-сбой сохраняет свою категорию. `account.error` включает не только SQL-ошибки. Старые записи не переклассифицируются по stage. `account.upload` служит action внешнего запроса, а не новым DB-event; `account.edit`, `account.db.error` и `account.hash.update` не вводятся. По Q1 update-ветка upload, административный PUT без `status` и оба прежних hash-маршрута сохраняют `account.update`; PUT с присутствующим `status` выбирает `account.status`, даже если значение не изменилось. Внешний hash-helper не переработан.

Profile-only действия и ошибки не создают новых DB-событий: используются `persist_error=False` либо queued `event=None`, сохраняющие техническую диагностику и cancellation. Намеренный пропуск DB-аудита не является `audit_unavailable`; отказ диагностики получает отдельный `diagnostics_unavailable` fallback. Профильные `/profile/upload` и `/profile/remove` не подключены к новому аудиту. По Q2 standalone `/api/v1/accounts/upload` и `/remove` сохраняют отсутствие обязательного JWT, form/response-контракты и всегда `user_id=NULL`, даже при непроверенных credentials. Actor нельзя выводить из body, имени файла, owner target или непроверенного Authorization.

Административные create/PUT сохраняют успешные имена событий. GET списка, одной записи, summary и missing-files аудируют только ошибки внутри обработчика; ошибки зависимостей до входа в него вне этого охвата. Успешные чтения не создают success-события и не делают commit ради журнала. `account.delete` записывается атомарно с DELETE, с NULL `account_id/session_id/message_id` и разрешённым target-снимком. Архивные факты single/bulk удаления пишутся независимо после release, хотя сам файловый I/O предшествует DB-delete. Снимок каждой цели фиксируется отдельно, operation UUID общий на запрос; повторные ID пропускаются до I/O, missing single даёт 404, missing bulk — skip. Нефатальный unlink-сбой не откатывает bulk. Только реальный unlink даёт file.delete: отсутствие при автоматической очистке пропускается, при явном remove сохраняет 404, включая race exists/unlink.

Общий корень контекста ошибки содержит `operation_id/action/user_id/stage/db_outcome/error` и сведения о release; event/source задаются отдельно. Диагностика хранит безопасные тип/код, HTTP status, SQLSTATE/errno и координаты traceback: строки до 160 символов, обход до 12 исключений-причин и до 12 кадров только с basename/функцией/строкой. Исходные сообщения исключений, SQL/параметры и произвольные OS paths в общую диагностику не копируются. Callers передают только allowlist метаданных: upload допускает `number`, `info_1..info_8`, файловые/storage/cleanup сведения, admin — скалярный target и file-метаданные. Они находятся в `details`; hash-значения, credentials/headers, содержимое файлов и произвольные request/ORM-объекты исключены. `operation_context` дополнительно фильтрует известные приватные ключи. Сессионный аудит request-details не содержит.

Отказы аудита сохраняют первичную ошибку; защищённое завершение выполняется до очистки зависимостей, внешняя отмена передаётся вызывающему коду. При неподтверждённом аудите минимальный stderr fallback обязателен независимо от logger, включая неожиданный отказ finalizer/защищённой задачи и post-commit upload с HTTP 201; отказ stderr отмечается в исходном исключении. Все факты одного запроса сохраняют один operation UUID. Не-HTTP ошибки дают техническое событие `ERROR`, HTTP 404 — `NOT_FOUND`, остальные 4xx — `FAILURE`; это правило общего LogService-аудита, а не глобальная переклассификация auth/message. Бизнес-commit, переходы, attempts и успешный внешний upload-ответ при обычных post-commit cleanup/success-logger ошибках сохраняются. Best-effort очередь в памяти не обещает crash-durability или exactly-once; новые NULL-FK delete/file-факты не изменяют прежние CASCADE/retention.

Для stats согласован `StatsService` в существующем слое `app/services/`, без отдельного пакета запросов и CRUD статистики. API делегирует сервису период, область данных, агрегаты и coverage; сервис использует существующий CRUD пользователя для scope. Только внутри StatsService разрешены read-only аналитические SELECT через SQLAlchemy; мутации, `FOR UPDATE` и commit запрещены. Summary выполняет один CTE SELECT только по `log` с actor-предикатом `log.user_id` до агрегации/MIN; live — отдельный CTE SELECT по текущему владельцу `account`. Для scoped/admin-all используются две фиксированные SQL-формы, значения передаются bind-параметрами. Реальные маршруты зарегистрированы через api_router; SQLAlchemyError, включая ошибки auth-зависимостей, обрабатываются локальным _StatsRoute с безопасным 503 и диагностикой вне event loop, без глобального middleware. Log-only/actor-основа уже существовала в baseline задачи account/file-аудита.

DTO статистики в `app/schemas/stats.py` используют `frozen=True` и `extra="forbid"`. Строковые timestamps требуют строгого RFC 3339 с timezone и нормализуются в UTC общим типом из `app/core/utc.py`, ID ограничены положительным PostgreSQL integer (`1..2147483647`), trend — 32 точками. В totals/previous/каждой точке обязательны 17 nullable-счётчиков со строгими неотрицательными int: `opened`, `finished`, `session_bans`, `account_bans`, `sent`, `delivered`, `undelivered`, `failed`, `account_errors`, `session_errors`, `auto_finished`, `accounts_uploaded`, `accounts_created`, `accounts_updated`, `account_file_delete_errors`, `account_file_upload_errors`, `closed`. Пропуск поля не равен NULL, NULL не равен нулю. Текущий stats DTO не содержит cohort, `message_created` и доставляемость.

`accounts_uploaded/accounts_created/accounts_updated` считают точные события `account.file.upload/account.create/account.update` без дополнительных source/FK/operation_id/action/context-version ограничений; legacy `context={}` и hash-события допустимы. Это события, а не уникальные аккаунты или файловая воронка. `closed` вычисляется серверным SQL как `finished + session_bans` в каждом периоде/bucket; `auto_finished` уже входит в finished и второй раз не прибавляется. Прежние lifecycle FK/status-предикаты и message-first сохранены. `account.delete` и успешный `account.file.delete` дополнительных метрик не создают.

Три error-группы `account.error/account.file.upload.error/account.file.delete.error` принимают `source IN ('api', 'ext_api')`, `session.error` — только `ext_api`. Дедупликация идёт по event/source/log.user_id/operation_id, включая NULL actor; MIN ищется по всей сохранённой истории выбранной области до применения нижней границы периода (global-first). Сумма категорий не равна числу уникальных неуспешных запросов. Legacy `account.error` не разбирается по stage для переноса в файловые группы. NULL-actor события учитываются только в admin-all. Member logs API сохраняет фильтр по текущему владельцу связанного account: NULL-FK строка ему не видна в журнале, хотя actor-summary может её учитывать.

`STATS_COVERAGE_STARTS`, её типы/валидатор и пример в `.env.example` удалены по прежнему прямому поручению пользователя; `get_summary` не принимает `coverage_starts`. Ноль означает отсутствие сохранённых событий, `recorded` — подсчитываемость, не полноту сбора. Семь wire-групп `lifecycle/message_events/account_errors/session_errors/account_events/account_file_upload_errors/account_file_delete_errors` сохраняют `from: null`. Только отсутствующий, JSON null или пустой operation_id даёт `partial` с `missing_operation_id` и маскирует соответствующую одну из четырёх error-групп целиком для затронутого current/previous периода и всех его buckets. Source-предикаты gap и численного подсчёта одинаковы; остальные группы и другой период не маскируются. Даты сбора, прежние причины по датам и backfill не вводятся; нулевой диапазон даёт нули и пустой ряд, UTC/месяц и независимый live сохранены.

Модели определяют структуру таблиц и отношения. Схемы определяют контракт API. Адаптеры изолируют инфраструктуру (БД).

`DashboardApi` в `html/dashboard/js/api.js` отвечает за фиксированные GET stats/options, валидацию всех 17 метрик/семи coverage-групп и явную проекцию DTO snake_case → camelCase. `dashboard.js` отвечает за состояние UI и независимые каналы summary/live/users. `null` не заменяется нулём, SQL-агрегаты, включая closed, не пересчитываются на клиенте. Cohort/доставляемость отсутствуют в текущем stats UI/DTO. Период и подписи интервалов используют UTC и серверные границы buckets. Старый ответ 11/4 отвергается как protocol error; подготовленный rollout требует backend раньше UI, откат — совместимый UI раньше backend с учётом кеша и открытых вкладок.

Дашборд содержит 12 исторических карточек и шесть графиков; live-показатели отделены от периода. График сообщений сохраняет SENT/DELIVERED/UNDELIVERED/FAILED, порядок/цвета/типы серий, tooltip и действие клика; failed остаётся в API и графике без собственной карточки. Фильтр журнала содержит 19 вариантов event, включая семь account/file/session-error добавлений; произвольный строковый event по-прежнему передаётся для фильтрации, новые варианты не являются whitelist чтения.

Дашборд явно описывает сохранённую историю: ноль означает отсутствие записанных событий, а не гарантию отсутствия прошлой активности. Предупреждения о качестве и NULL сохраняются. Адаптер принимает legacy `coverage.from`, но UI не представляет его как подтверждённую дату сбора. Ссылка на дашборд сейчас видима в общем меню admin/member, прямой `/dashboard/` доступен. Прежнее `dashboardNavigation1=''` относится к историческому состоянию; видимая навигация, пользовательские auth/CSS/live-изменения и переходы после входа уже были в baseline и не введены задачей account/file-аудита.

Запросы дашборда читают свежий token, поддерживают отмену и отбрасывают устаревшие ответы через revision/credentials/scope/period guards. Выбранный владелец live не зависит от валидности исторического диапазона и успеха summary. `DashboardMock` используется только при `?demo=1`, без stats/options-запросов и без неявного fallback при ошибке API.

Общие `getToken`/`setToken` остаются синхронными, `window.isAuth` — объектом token либо `null`; контракт четырёх полей и совместимость auth timestamps сохранены. Проверка входа сверяет свежий storage и revision до любых действий по успеху или ошибке, а logout очищает auth через `setToken(null)`. Пользовательские подписи не интерполируются в Kendo header: статическая разметка заполняется через `.text()`. Полный контракт общей авторизации описан в `architecture.md`.

---

## Правила тестирования

- Новая бизнес-логика покрывается юнит-тестами с моками зависимостей
- Новые API-эндпоинты покрываются интеграционными тестами
- Исправления багов сопровождаются регрессионным тестом
- Тесты не зависят от внешних сервисов — внешние вызовы мокаются

### Текущая совместная локальная приёмка

- Канонические команды, 31 Python-файл и границы проверки находятся в `plans/261011-account-file-audit-dashboard/phase5.md`. Итоговый завершённый прогон дал **1661 Python**, **190 Node**, **157 Chromium** и **244 wire samples** (240 StatsSummary и 4 StatsLive), без суммирования фазовых результатов. При этой синхронизации документации приложение и тесты заново не запускались.
- `tests/test_log_file_audit.py`, `tests/test_account_file_audit_contract.py`, `tests/api/v1/test_account_audit_events.py` и `tests/integration/test_admin_account_audit_transactions.py` проверяют immutable facts/targets, release/latch, cancellation, transactional delete/CASCADE, profile-only исключение, Q1/Q2 и anonymous HTTP/SQL. `test_log_upload_transactions.py` расширен до 14 PostgreSQL-сценариев. SQL-проверки `test_stats_account_file_events.py`, `test_stats_log_only.py` и независимые controls `test_stats_acceptance.py` охватывают 17 метрик/семь групп, actor/source scope, NULL actor, global-first и независимое маскирование четырёх error-групп; прежние read-only/snapshot/UTC/message/live регрессии сохранены.
- Текущий Node-набор: `node --test --test-reporter=spec tests/shared_auth.test.js tests/dashboard_api.test.js tests/dashboard_mock.test.js tests/log_event_options.test.js`. Независимые fixtures валидированы настоящими DTO 17/7. Browser использует фактические HTML/scripts/jQuery/Kendo с HTTP/clock fixtures, проверяет 12 карточек/шесть графиков, message-baseline, anonymous/NULL и прежние guards. Проверен только Chromium; BFCache/storage синтетические, seriesClick — через Kendo dispatcher, а не pointer hit-testing SVG. Внешние Playwright/Python-инструменты не являются новыми зависимостями проекта.
- Целевой flake8 25 файлов и mypy пяти runtime-модулей прошли; mypy использует `--follow-imports=skip --ignore-missing-imports`. Node syntax check девяти JS/CJS-файлов также прошёл. Полный legacy `app/api/ext/v1/account.py` сохраняет 34 flake8 и две mypy ошибки, сопоставленные с HEAD в фазе 2; он не включён в успешный полный статический набор. Успешность всего Python-репозитория или импортного графа не заявляется.
- Python-приёмка использовала отдельную PostgreSQL 12.22 с прежними guards и двумя режимами UUID-схем, временный CWD и фиктивный app DSN на порту 1, без рабочей `.env`/production lifespan. Тестовый контейнер удалён, его сохранённый endpoint недействующий. Локальные результаты и синтетический EXPLAIN не закрывают рабочие metadata/retention, согласованный объём/стоимость, окружение, аудит всех workers и rollout. `plans/261011-account-file-audit-dashboard/rollout.md` подготовлен без deployment; одобрение документации получено, операторский пункт остаётся открытым. Новых миграций, индексов и зависимостей задача не вводит.

### Исторические проверки предыдущего плана

Следующие записи сохраняют результаты и ограничения `plans/261003-dashboard-backend/plan.md` на 2026-10-05. Упоминания cohort, доставляемости, прежнего количества метрик и wire samples относятся к тогдашнему контракту. Итог после прежней унификации составлял 991 Python-проверку в 25 файлах, 161 Node-тест, 116 browser-сценариев и 144 wire samples; эти результаты не заменяют текущую приёмку и не закрывают прежние production-пункты.

- HTTP-проверки основы stats в `tests/api/v1/test_stats.py` используют локальные contract-probes FastAPI; они подтверждают контракт DTO, периода, scope и существующей авторизации, но не готовность production-эндпоинтов. Fixtures фазы 1 выполняются на отдельной PostgreSQL 12 с откатом внешней транзакции. Фаза 1 завершена по уточнённому объёму; проверка рабочей БД с согласия пользователя остаётся открытой в фазе 3.
- Реальные stats-маршруты проверяются отдельно в `tests/api/v1/test_stats_api.py` и `tests/integration/test_stats_api_postgres.py`, options — также в `tests/api/v1/test_user_options.py`. Локальное FastAPI-приложение подключает api_router без app.main/production lifespan. `tests/test_stats_settings.py` проверяет отсутствие coverage-настройки, игнорирование прежней переменной в окружении процесса и сохранённую UTC-валидацию; это не проверка обработки всех лишних полей dotenv. SQL, tenant-изоляция, DST, поздние callbacks, error operation_id, численные значения сохранённой истории и live проверяются в `tests/integration/test_stats_aggregates.py` и `test_stats_edges.py`. Уникальные basename интеграционных файлов предотвращают коллизии с прежними API-тестами.
- `tests/integration/test_stats_explain.py` проверяет фактические агрегаты в `SET TRANSACTION READ ONLY`, по одному аналитическому statement без commit, и EXPLAIN после ANALYZE только тестовых таблиц. Замеры синтетического набора не задают production SLA; проверка рабочей БД остаётся открытой. Артефакт по умолчанию записывается в pytest tmp_path, опциональный STATS_TEST_EXPLAIN_DIR проверяется как временный тестовый каталог.
- Общий LogService-аудит проверяется в сохранённом по имени `tests/test_session_error_audit.py`; сессионные HTTP/транзакционные проверки в `tests/api/ext/v1/test_session_error.py` и `tests/integration/test_session_error_transactions.py` перенесены на общий сервис. Новый `tests/integration/test_log_upload_transactions.py` содержит шесть реальных PostgreSQL-сценариев: rollback перед независимым writer, существующие/новые FK, фактически выполненный commit с потерянным подтверждением, post-commit HTTP 201 и три ошибки одного update-upload с общим UUID, привязка к вызывающему пользователю. Для настоящих соединений и commit используется существующий режим фиксируемой UUID-схемы с защищённым `DROP SCHEMA ... CASCADE` только этой схемы; второй режим stats откатывает внешнюю транзакцию. Исторические результаты фаз 1–5 сохранены в `plans/261003-dashboard-backend/plan.md`.
- Приёмка фазы 5 в `tests/integration/test_stats_acceptance.py` использует небольшие независимые контрольные SQL: `MIN` первых подтверждений и ошибок вычисляется по всей сохранённой истории до применения границ периода. Сверяются все двенадцать метрик current/previous и каждого bucket, сумма buckets, cohort, доставляемость и live для self/admin-selected/admin-all, включая перенос владельца, устаревшие FK аудита и поздние callbacks. Реальный api_router с PostgreSQL проверяет календарный предел от 31 января до 28/29 февраля, отказ 422 при превышении на микросекунду, пустой/открытый диапазон, DST, timezone соединения и одинаковый 403 для чужого существующего/несуществующего владельца.
- `tests/integration/test_stats_concurrency.py` повторно использует защищённую фиксируемую UUID-схему; `conftest.py` и его guards в фазе 5 не менялись. Для scoped/admin-all тестовая advisory CTE оборачивает неизменённый service SELECT с типизированными bind-параметрами; `pg_locks` подтверждает ожидание до и после реального commit writer. Завершившийся statement сохраняет прежний snapshot, а следующий запрос без обёртки видит новые данные в той же READ COMMITTED-транзакции. Порядок вычисления отдельных CTE этим не доказывается.
- В том же файле прямые вызовы настоящих start на существующем аккаунте → finish → ban → ban выполняют реальные SQL/CRUD и commit; writer приостановлен перед commit, пока summary/live без обёртки читают прежнее состояние. Проверяются ответы, статусы, lifecycle-аудит и исходный расход attempts, включая повторный ban. Сравнение каталогов таблиц, колонок/defaults, индексов и ограничений до/после относится только к собственной тестовой схеме, а не к соответствию production. Эти сценарии не являются HTTP/auth-конкурентной или нагрузочной приёмкой.
- Frontend-регрессии запускаются через `node --test tests/shared_auth.test.js tests/dashboard_api.test.js tests/dashboard_mock.test.js`. `shared_auth.test.js` исполняет фактические общие scripts в Node VM; проверяет синхронный контракт, storage, ранний отказ до DOM-ready, гонки, logout, ошибки и таймер. Wire-fixtures в `tests/dashboard_api_fixtures.cjs` независимы от `DashboardApi`/`DashboardMock`; после изменения семантики сохранённой истории заново проверены 144 samples действующими DTO: 140 StatsSummary и 4 StatsLive.
- `tests/dashboard_browser.cjs` использует фактические HTML, shared auth/header, jQuery и Kendo, подменяя HTTP-ответы и часы. Регрессии включают рабочие login widgets после раннего redirect, буквальный вывод HTML/Kendo payload для admin/member, устаревшие ответы, profile update, timeout и подтверждённый logout. Playwright установлен вне проекта; артефакты допускаются только в проверенном системном временном каталоге. Границы browser-проверки описаны в `constraints.md`.
- Исторические канонические количества, команды, явный список Python-файлов и полные результаты ведутся в `plans/261003-dashboard-backend/plan.md`. После унификации прошла расширенная выборка 25 Python-файлов stats/общего аудита и смежных регрессий, включая `test_restore_missing_files` и `test_account_hash`, а также полные Node/browser-проверки. Целевые flake8 девяти файлов и mypy шести runtime-модулей прошли; весь legacy `app/api/ext/v1/account.py` в успешный flake8-набор не включён. Его 34 flake8 и два mypy замечания совпадают с baseline HEAD; подробности и флаги ограниченной проверки импортов приведены в `constraints.md` и плане. Исторические результаты фаз 3–5 сохраняются отдельно; успешность всего Python-репозитория или всех статических проверок не заявляется. Рабочие metadata, согласованная стоимость на репрезентативном объёме и rollout остаются открытыми.

---

## Правила документации

- Изменения архитектуры отражаются в `.opencode/project/architecture.md`
- Новые интеграции документируются в `.opencode/project/integrations.md`
- Новые переменные окружения добавляются в `.env.example`
- Эндпоинты API документируются через docstring с описанием функциональности и примеров

---

## Запрещённые практики

- Прямые SQL-запросы вне CRUD-слоя (за исключением существующей сложной логики внешнего API с FOR UPDATE и одобренных read-only аналитических SELECT только внутри StatsService без мутаций и commit)
- Проглатывание исключений без логирования (`except: pass`)
- Синхронные I/O операции в асинхронном контексте
- Ручные ALTER TABLE без миграции Alembic
- Циклические зависимости между модулями
- Импорт верхних слоёв из нижних (CRUD не импортирует обработчики)
- Хардкод путей к файлам и URL внешних сервисов (использовать settings)
