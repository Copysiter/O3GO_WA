# 📘 README — O3GO\_WA-main

## 🚀 Описание проекта

Проект состоит из:

* **Backend (FastAPI)** — API сервис (авторизация, работа с пользователями, аккаунтами, сообщениями и сессиями).
* **Frontend (Next.js/React)** — веб-интерфейс для взаимодействия с API.
* **PostgreSQL** — база данных.

Все сервисы запускаются в Docker через `docker-compose`.

---

## 🛠 Требования

Перед запуском убедитесь, что установлены:

* [Docker](https://docs.docker.com/get-docker/)
* [Docker Compose](https://docs.docker.com/compose/install/)
* Git (если будете клонировать репозиторий)
* Python 3.11+ (опционально, только если хотите запускать скрипт `start.py`)

---

## ⚙️ Настройка

### 1. Клонируйте проект

```bash
git clone https://github.com/your-repo/O3GO_WA-main.git
cd O3GO_WA-main
```

### 2. Создайте файл окружения `.env`

Пример содержимого:

```ini
API_VERSION=1
API_VERSION_PREFIX=/api/v1
EXT_API_VERSION=1
EXT_API_VERSION_PREFIX=/ext/api/v1
EXT_API_KEY=568eD25b494fA9147416DfCd9Bbe71dFdC38F1c555F4c8b925f8c68C9EC17d5b

PROJECT_NAME=FastAPI
PROJECT_HOST=0.0.0.0
PROJECT_PORT=8000
BACKEND_CORS_ORIGINS=*

POSTGRES_SERVER=db
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=postgres
POSTGRES_DSN=postgresql+asyncpg://postgres:postgres@db:5432/postgres
POSTGRES_LOCAL_DSN=postgresql+asyncpg://postgres:postgres@localhost:5432/postgres

FIRST_SUPERUSER=admin
FIRST_SUPERUSER_PASSWORD=admin
SECRET_KEY=123456
```

---

## ▶️ Запуск проекта

### Вариант 1. Через Python-скрипт

```bash
python start.py
```

Скрипт автоматически соберёт и запустит Docker-контейнеры.

### Вариант 2. Вручную через Docker Compose

```bash
docker-compose down -v   # остановить и очистить старые контейнеры
docker-compose up -d --build
```

---

## 🌐 Доступные сервисы

После запуска:

* **Backend API (FastAPI):** 👉 [http://localhost:8000](http://localhost:8000)
* **Документация Swagger:** 👉 [http://localhost:8000/docs](http://localhost:8000/docs)
* **Frontend (Next.js):** 👉 [http://localhost:3000](http://localhost:3000)

---

## 👤 Работа с пользователями и API

### 1. Получение токена (логин суперпользователя)

```bash
curl -X POST "http://localhost:8000/api/v1/auth/access-token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=admin"
```

Ответ:

```json
{
  "access_token": "...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "login": "admin",
    "is_superuser": true
  }
}
```

### 2. Получение списка аккаунтов

```bash
curl -X GET "http://localhost:8000/api/v1/accounts/" \
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```

### 3. Создание аккаунта

```bash
curl -X POST "http://localhost:8000/api/v1/accounts/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -d '{
    "dst_number": "7999999999",
    "type": 1,
    "status": 2,
    "reg_count": 5,
    "info_1": "test info 1",
    "info_2": "test info 2",
    "info_3": "test info 3"
  }'
```

---

## 🛠 Полезные команды

### Логи сервиса

```bash
docker-compose logs -f api     # бэкенд
docker-compose logs -f web     # фронтенд
docker-compose logs -f db      # база данных
```

### Остановка проекта

```bash
docker-compose down
```

### Полная очистка (контейнеры + БД)

```bash
docker-compose down -v
```

---

## ⚡ Возможные проблемы

1. **Ошибка с React/Next.js при сборке (`ERESOLVE unable to resolve dependency tree`)**

   * Либо используйте:

     ```dockerfile
     RUN npm install --legacy-peer-deps
     ```
   * Либо в `webka/package.json` замените React на `18.2.0`.

2. **База не создаётся**

   * Проверьте `.env`, должны быть `DATABASE_CREATE_ALL=True` и `DATABASE_DELETE_ALL=True` (при первом запуске).

3. **Нет доступа к API**

   * Проверьте, что сервисы запущены:

     ```bash
     docker ps
     ```

---

## ✅ Итог

После этих шагов у вас будут запущены:

* **PostgreSQL** с преднастроенной схемой.
* **FastAPI** с автосозданным суперпользователем (`admin/admin`).
* **Frontend (Next.js)** с доступом к API.
