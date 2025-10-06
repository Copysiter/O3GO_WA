# 🚀 O3GO WA Management System

Полнофункциональная система управления WhatsApp аккаунтами с современным веб-интерфейсом и мощным API.

## 📋 Описание проекта

**O3GO WA** - это комплексное решение для управления WhatsApp аккаунтами, сообщениями и сессиями, состоящее из:

- 🔧 **Backend (FastAPI)** - высокопроизводительный API с авторизацией и CRUD операциями
- 🎨 **Frontend (Next.js 14)** - современный веб-интерфейс с продвинутыми таблицами данных
- 🗄️ **PostgreSQL** - надежная база данных
- 🐳 **Docker** - контейнеризация для простого развертывания

## ✨ Основные возможности

### 🔐 Система авторизации
- JWT токены
- Роли пользователей (admin, user)
- Защищенные эндпоинты

### 📊 Управление данными
- **Пользователи** - регистрация, редактирование, управление ролями
- **Аккаунты** - WhatsApp аккаунты с типами и статусами
- **Сообщения** - отправка, отслеживание статусов доставки
- **Сессии** - управление активными сессиями

### 🎯 Продвинутые таблицы данных
- 🔍 **Фильтрация** - по всем столбцам с различными операторами
- 📈 **Сортировка** - многоуровневая с drag-and-drop
- 👁️ **Управление видимостью** - скрытие/показ столбцов
- 📄 **Пагинация** - настраиваемое количество записей на странице
- 🔎 **Глобальный поиск** - по всем данным в реальном времени

## 🛠️ Технологический стек

### Backend
- **FastAPI** 0.115.12 - современный веб-фреймворк
- **SQLAlchemy** 2.0.41 - ORM для работы с базой данных
- **asyncpg** - асинхронный драйвер PostgreSQL
- **Pydantic** 2.11.4 - валидация данных
- **python-jose** - JWT токены
- **fastapi-filter** - продвинутая фильтрация API

### Frontend
- **Next.js** 14.2.25 - React фреймворк
- **TypeScript** - типизированный JavaScript
- **Tailwind CSS** - utility-first CSS фреймворк
- **shadcn/ui** - компоненты пользовательского интерфейса
- **TanStack Table** - мощные таблицы данных
- **React Hook Form** - управление формами
- **nuqs** - синхронизация состояния с URL

## 🚀 Быстрый старт

### Предварительные требования
- [Docker](https://docs.docker.com/get-docker/) и [Docker Compose](https://docs.docker.com/compose/install/)
- Git

### 1. Клонирование репозитория
```bash
git clone <your-repo-url>
cd O3GO_WA-main
```

### 2. Настройка окружения
Создайте файл `.env` в корне проекта:

```env
# API Configuration
API_VERSION=1
API_VERSION_PREFIX=/api/v1
EXT_API_VERSION=1
EXT_API_VERSION_PREFIX=/ext/api/v1
EXT_API_KEY=568eD25b494fA9147416DfCd9Bbe71dFdC38F1c555F4c8b925f8c68C9EC17d5b

# Server Configuration
PROJECT_NAME=O3GO WA Management
PROJECT_HOST=0.0.0.0
PROJECT_PORT=8000
BACKEND_CORS_ORIGINS=*

# Database Configuration
POSTGRES_SERVER=db
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=postgres
POSTGRES_DSN=postgresql+asyncpg://postgres:postgres@db:5432/postgres
POSTGRES_LOCAL_DSN=postgresql+asyncpg://postgres:postgres@localhost:5432/postgres

# Security
FIRST_SUPERUSER=admin
FIRST_SUPERUSER_PASSWORD=admin
SECRET_KEY=your-secret-key-here

# Database Management
DATABASE_CREATE_ALL=True
DATABASE_DELETE_ALL=False
```

### 3. Запуск проекта
```bash
# Сборка и запуск всех сервисов
docker-compose up -d --build

# Или используйте Python скрипт (если есть)
python start.py
```

### 4. Проверка запуска
После запуска будут доступны:
- 🌐 **Frontend**: http://localhost:3000
- 🔧 **Backend API**: http://localhost:8000
- 📚 **API Документация**: http://localhost:8000/docs

## 📡 API Эндпоинты

### Авторизация
```bash
# Получение токена
POST /api/v1/auth/access-token
Content-Type: application/x-www-form-urlencoded
Body: username=admin&password=admin

# Обновление токена
POST /api/v1/auth/refresh-token
```

### Пользователи
```bash
GET    /api/v1/users/          # Список пользователей
POST   /api/v1/users/          # Создание пользователя
GET    /api/v1/users/{id}      # Получение пользователя
PUT    /api/v1/users/{id}      # Обновление пользователя
DELETE /api/v1/users/{id}      # Удаление пользователя
```

### Аккаунты
```bash
GET    /api/v1/accounts/       # Список аккаунтов
POST   /api/v1/accounts/       # Создание аккаунта
GET    /api/v1/accounts/{id}   # Получение аккаунта
PUT    /api/v1/accounts/{id}   # Обновление аккаунта
DELETE /api/v1/accounts/{id}   # Удаление аккаунта
```

### Сообщения
```bash
GET    /api/v1/messages/       # Список сообщений
POST   /api/v1/messages/       # Отправка сообщения
GET    /api/v1/messages/{id}   # Получение сообщения
PUT    /api/v1/messages/{id}   # Обновление сообщения
DELETE /api/v1/messages/{id}   # Удаление сообщения
```

### Сессии
```bash
GET    /api/v1/sessions/       # Список сессий
POST   /api/v1/sessions/       # Создание сессии
GET    /api/v1/sessions/{id}   # Получение сессии
PUT    /api/v1/sessions/{id}   # Обновление сессии
DELETE /api/v1/sessions/{id}   # Удаление сессии
```

## 🔍 Фильтрация и сортировка

API поддерживает продвинутую фильтрацию через параметры запроса:

### Операторы фильтрации
- **Текст**: `ilike`, `like`, `eq`, `ne`
- **Числа**: `eq`, `ne`, `gt`, `gte`, `lt`, `lte`
- **Даты**: `eq`, `gte`, `lte`
- **Выбор**: `eq`, `in`

### Примеры запросов
```bash
# Фильтрация по статусу
GET /api/v1/accounts/?status__eq=1

# Поиск по номеру телефона
GET /api/v1/accounts/?number__ilike=%799%

# Фильтрация по дате создания
GET /api/v1/accounts/?created_at__gte=2024-01-01T00:00:00

# Сортировка
GET /api/v1/accounts/?order_by=created_at,-status

# Пагинация
GET /api/v1/accounts/?skip=0&limit=10
```

## 🎨 Frontend возможности

### Таблицы данных
- **Фильтры по столбцам** - текст, числа, даты, выбор из списка
- **Многоуровневая сортировка** - drag-and-drop интерфейс
- **Управление видимостью** - скрытие ненужных столбцов
- **Адаптивная пагинация** - настройка количества записей
- **Глобальный поиск** - мгновенный поиск по всем данным

### Формы
- **Валидация в реальном времени**
- **Автосохранение черновиков**
- **Загрузка файлов**
- **Мультиязычность**

## 🛠️ Разработка

### Локальная разработка Backend
```bash
cd O3GO_WA-main
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate     # Windows

pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Локальная разработка Frontend
```bash
cd web
npm install
npm run dev
```

### Полезные команды
```bash
# Логи сервисов
docker-compose logs -f api
docker-compose logs -f web
docker-compose logs -f db

# Остановка
docker-compose down

# Полная очистка
docker-compose down -v

# Перезапуск отдельного сервиса
docker-compose restart api
```

## 📁 Структура проекта

```
O3GO_WA-main/
├── app/                    # Backend (FastAPI)
│   ├── api/               # API роуты
│   │   ├── v1/           # Версия 1 API
│   │   └── ext/          # Внешние API
│   ├── core/             # Основные настройки
│   ├── crud/             # CRUD операции
│   ├── models/           # SQLAlchemy модели
│   ├── schemas/          # Pydantic схемы
│   └── utils/            # Утилиты
├── web/                   # Frontend (Next.js)
│   ├── app/              # App Router
│   ├── components/       # React компоненты
│   │   ├── table/       # Компоненты таблиц
│   │   └── ui/          # UI компоненты
│   ├── lib/             # Утилиты и хуки
│   └── types/           # TypeScript типы
├── migrations/           # Alembic миграции
├── docker-compose.yml    # Docker Compose конфигурация
├── Dockerfile           # Docker образ
└── requirements.txt     # Python зависимости
```

## 🐛 Решение проблем

### База данных не создается
```bash
# Проверьте переменные окружения
echo $DATABASE_CREATE_ALL

# Пересоздайте контейнеры
docker-compose down -v
docker-compose up -d --build
```

### Ошибки сборки Frontend
```bash
# Очистите кеш
cd web
rm -rf .next node_modules
npm install
npm run build
```

### Проблемы с портами
```bash
# Проверьте занятые порты
netstat -tulpn | grep :3000
netstat -tulpn | grep :8000

# Измените порты в docker-compose.yml
```

## 📈 Мониторинг

### Логи приложения
```bash
# Логи в реальном времени
tail -f app/log/app.log

# Логи через Docker
docker-compose logs -f api
```

### Метрики производительности
- FastAPI автоматически предоставляет метрики через `/metrics`
- Используйте PostgreSQL статистики для мониторинга БД

## 🤝 Вклад в проект

1. Форкните репозиторий
2. Создайте ветку для фичи (`git checkout -b feature/amazing-feature`)
3. Зафиксируйте изменения (`git commit -m 'Add amazing feature'`)
4. Отправьте в ветку (`git push origin feature/amazing-feature`)
5. Откройте Pull Request

## 📄 Лицензия

Этот проект лицензирован под MIT License - см. файл [LICENSE](LICENSE) для деталей.

## 📞 Поддержка

Если у вас есть вопросы или проблемы:
- Создайте [Issue](../../issues)
- Напишите в [Discussions](../../discussions)
- Свяжитесь с командой разработки

---

⭐ **Если проект был полезен, поставьте звездочку!**