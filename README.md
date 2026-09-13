# 🧹 MAXIMUM TELEGRAM ACCOUNT CLEANER — PRO EDITION v2.0

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![aiogram 3.x](https://img.shields.io/badge/aiogram-3.x-green.svg)](https://docs.aiogram.dev/)
[![Telethon MTProto](https://img.shields.io/badge/telethon-1.38+-blue.svg)](https://docs.telethon.dev/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Mini_App-teal.svg)](https://fastapi.tiangolo.com/)
[![Security: Fernet at-rest](https://img.shields.io/badge/Security-Fernet_at--rest-red.svg)](https://cryptography.io/)

Production-grade инструмент для владельцев собственных Telegram-аккаунтов, позволяющий выполнять глубокую, безопасную, этичную и **обратимо-осознанную** очистку подписок, чатов и ботов через официальный Telegram MTProto API.

---

## 🌟 Ключевые возможности v2.0

1. **Telegram Mini App (WebApp)** — современный визуальный интерфейс прямо в Telegram:
   - Dashboard с кольцевым индикатором **Hygiene Score** и счётчиками по категориям.
   - Предпросмотр диалогов с живым поиском, фильтрами и мультивыбором (чекбоксами).
   - Интерактивный слайдер/hold-кнопка для необратимых действий (защита от случайных тапов).
   - Server-Sent Events (SSE) для отображения живого прогресс-бара и кнопка мгновенной остановки.
2. **Безопасный ввод кода и 2FA через Mini App** — код авторизации и пароль вводятся через защищённую HTML-форму по HTTPS и **никогда не попадают в историю переписки чата** с ботом.
3. **Шифрование сессий at rest (Fernet + PBKDF2)** — файлы Telethon-сессий хранятся на сервере исключительно в зашифрованном виде с уникальной солью для каждого пользователя.
4. **Умные рекомендательные эвристики (`heuristics.py`)**:
   - Обнаружение «мёртвых» каналов (без постов > 60 дней).
   - Обнаружение подозрительных ботов и спам-паттернов.
   - Диалоги без пользовательских сообщений (zero interaction).
   - *Важно:* эвристики носят **исключительно рекомендательный характер** и никогда не запускают удаление автоматически!
5. **Backup & Rejoin Manifest** — перед выходом из публичных каналов и групп бот сохраняет их `@username` и публичные invite-ссылки в Rejoin Manifest, позволяя пользователю восстановить подписки в любой момент.
6. **Неизменяемый журнал действий (Audit Log Hash-Chain)** — каждое действие связывается криптографической цепочкой хэшей SHA-256 (аналог блокчейн-журнала).
7. **Автоочистка по расписанию (APScheduler)**:
   - Ежедневно / Еженедельно / Ежемесячно.
   - **По умолчанию — строгий Dry-Run режим**: формирует отчёт без внесения изменений.
   - Автоматическое удаление доступно только после отдельного явного согласия.
8. **Account Hygiene Score** — прозрачная формула оценки чистоты аккаунта без давления и тёмных паттернов.
9. **Полная изоляция пользователей** — отдельные сессии, ключи, белые списки и `asyncio.Lock` на уровне каждого аккаунта.

---

## ⚖️ Этика, безопасность и Telegram ToS

* **Инструмент личной гигиены:** проект предназначен **только** для управления собственным аккаунтом. Не используйте его для автоматизации чужих учетных записей или спам-активности.
* **Строгое соблюдение Telegram ToS:** приложение работает через официальный MTProto-протокол (Telethon), строго соблюдает лимиты запросов и FloodWait, не использует недокументированные хаки и эксплойты.
* **Честность относительно OSINT:** удаление диалогов через API не гарантирует уничтожения копий данных у третьих лиц (скриншоты переписок, пересланные сообщения, сторонние дампы баз данных или кэш поисковиков). Инструмент очищает данные, доступные и подконтрольные вашей учетной записи.

---

## 📁 Архитектура проекта

```text
telegram-account-cleaner/
│
├── main.py                     # Запуск aiogram 3.x бота (long-polling)
├── webapp_server.py            # Запуск FastAPI (бэкенд для Mini App)
├── config.py                   # Pydantic настройки и переменные окружения
├── database.py                 # aiosqlite, схемы БД и audit log hash-chain
├── requirements.txt
├── .env.example
├── .gitignore
├── docker-compose.yml          # Запуск бота и webapp в Docker
├── Dockerfile                  # Многоступенчатая сборка контейнера
├── Makefile                    # Шорткаты для сборки, тестов и запуска
├── README.md
│
├── bot/                        # aiogram 3.x бот
│   ├── handlers.py             # Обработчики команд, кнопок и FSM
│   ├── keyboards.py            # Inline-клавиатуры и WebApp-кнопки
│   ├── states.py               # FSM состояния (подтверждение, 2FA)
│   └── filters.py              # Проверка контекста пользователя
│
├── telegram_client/            # MTProto слой Telethon
│   ├── manager.py              # Менеджер сессий, per-user lock, дешифрование
│   ├── auth.py                 # Логин: телефон, код, 2FA
│   ├── scanner.py              # Сканирование диалогов, проверка прав
│   ├── cleaner.py              # Удаление, отписка, FloodWait, backoff
│   ├── heuristics.py           # Рекомендательные метки (dead channel, bot)
│   ├── models.py               # Pydantic-модели диалогов и планов
│   └── exceptions.py           # Иерархия исключений
│
├── services/                   # Бизнес-логика (общая для бота и webapp)
│   ├── cleanup_service.py      # Запуск, отмена (Event), прогресс
│   ├── preview_service.py      # Формирование предпросмотра
│   ├── whitelist_service.py    # Управление белым списком и правилами
│   ├── statistics_service.py   # Аналитика пользователя и анонимная статистика
│   ├── scheduler_service.py    # Планировщик задач (APScheduler)
│   ├── backup_service.py       # Экспорт/импорт, Rejoin Manifest
│   ├── crypto_service.py       # Шифрование Fernet + соль PBKDF2
│   └── hygiene_score_service.py# Индекс чистоты аккаунта
│
├── webapp/                     # Telegram Mini App
│   ├── api/                    # Эндпоинты FastAPI
│   │   ├── auth.py             # Валидация HMAC-SHA256 Telegram initData
│   │   ├── login.py            # Безопасный логин без утечки в чат
│   │   ├── scan.py             # Сканирование и предпросмотр
│   │   ├── cleanup.py          # Запуск/остановка очистки + SSE стрим
│   │   ├── history.py          # История и выгрузка CSV
│   │   └── settings.py         # Настройки, Whitelist, Rejoin Manifest
│   ├── static/                 # Фронтенд (HTML5, CSS3, JS + WebApp SDK)
│   │   ├── index.html
│   │   ├── app.js
│   │   └── style.css
│   └── schemas.py              # Pydantic схемы запросов
│
├── i18n/                       # Локализация
│   ├── ru.json                 # Русский
│   └── en.json                 # Английский
│
├── utils/                      # Утилиты
│   ├── logger.py               # Логгер с фильтрацией секретов (Redacting)
│   ├── progress.py             # Троттлинг обновлений сообщений
│   ├── helpers.py              # Маскирование телефонов, форматирование
│   └── i18n.py                 # Хелпер интернационализации
│
└── tests/                      # Автоматические тесты
    ├── test_crypto.py          # Проверка Fernet шифрования round-trip
    ├── test_auth_init_data.py  # Проверка валидации HMAC Telegram initData
    ├── test_heuristics.py      # Проверка эвристик на синтетических данных
    ├── test_whitelist.py       # Проверка защиты белого списка
    └── test_scheduler.py       # Проверка гарантии Dry-Run планировщика
```

---

## 🚀 Установка и быстрый старт

### 1. Требования

* Python 3.11+
* Telegram Bot Token (от [@BotFather](https://t.me/BotFather))
* Telegram API ID & API Hash (получить на [my.telegram.org](https://my.telegram.org))
* Публичный HTTPS-домен для WebApp (для локальной разработки подойдёт Cloudflare Tunnel, ngrok или localtunnel)

### 2. Клонирование и установка зависимостей

```bash
git clone <repo_url> clina
cd clina

python -m venv venv
# Linux / macOS:
source venv/bin/activate
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

### 3. Генерация мастер-ключа шифрования и настройка `.env`

Сгенерируйте Fernet мастер-ключ:
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Скопируйте `.env.example` в `.env` и заполните:
```env
BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ
API_ID=1234567
API_HASH=abcdef0123456789abcdef0123456789

DATABASE_PATH=cleaner.db
SESSION_DIR=sessions
LOG_LEVEL=INFO

WEBAPP_URL=https://your-domain.example
WEBAPP_HOST=0.0.0.0
WEBAPP_PORT=8080

ENCRYPTION_MASTER_KEY=<ваш_сгенерированный_fernet_ключ>
JWT_SECRET=super_secret_jwt_key_here

SCHEDULER_ENABLED=true
SCHEDULER_TIMEZONE=UTC
DEFAULT_LANGUAGE=ru
```

### 4. Настройка Mini App у @BotFather

1. Откройте [@BotFather](https://t.me/BotFather) в Telegram.
2. Отправьте `/mybots` → выберите вашего бота → **Bot Settings** → **Menu Button** → **Configure menu button**.
3. Укажите ваш публичный HTTPS-адрес: `https://your-domain.example`.
4. Введите название кнопки: `Очиститель` или `Cleaner`.

---

## 💻 Локальный запуск

Для полноценной работы запускаются два процесса (бот и сервер Mini App):

```bash
# Терминал 1: Запуск FastAPI WebApp бэкенда
uvicorn webapp_server:app --host 0.0.0.0 --port 8080

# Терминал 2: Запуск Telegram-бота
python main.py
```

---

## 🐳 Запуск через Docker & Docker Compose

```bash
# Сборка и запуск в фоне
docker-compose up -d --build

# Просмотр логов
docker-compose logs -f

# Остановка
docker-compose down
```

---

## 🧪 Запуск тестов

Проект оснащён полным набором unit-тестов, проверяющих безопасность, криптографию, валидацию подписи Telegram и сохранность данных:

```bash
pytest tests/ -v
```

---

## 🛡️ Безопасность и приватность

* **Маскирование в логах:** класс `RedactingFormatter` фильтрует токены ботов, номера телефонов, коды авторизации и 2FA-пароли при выводе в консоль и файлы логов.
* **Изоляция сессий:** сессия каждого пользователя расшифровывается в память только на время выполнения запроса и хранится на диске в зашифрованном виде.
* **Защита от случайных удалений:** для запуска MAX CLEAN требуется ввести подтверждение в чате или удерживать кнопку подтверждения в Mini App в течение 3 секунд с тактильной отдачей Haptic Feedback.
* **Белый список в приоритете:** элементы из Whitelist исключаются из обработки на самом раннем этапе и гарантированно пропускаются.
