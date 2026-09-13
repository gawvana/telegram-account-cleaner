# ⚡ CLIN — Telegram Account Cleaner
> Production-grade, privacy-first management and hygiene utility for personal Telegram accounts.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![aiogram 3.x](https://img.shields.io/badge/aiogram-3.x-green.svg)](https://docs.aiogram.dev/)
[![Telethon MTProto](https://img.shields.io/badge/telethon-1.38+-blue.svg)](https://docs.telethon.dev/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Mini_App-teal.svg)](https://fastapi.tiangolo.com/)
[![Security: Fernet at-rest](https://img.shields.io/badge/Security-Fernet_at--rest-red.svg)](https://cryptography.io/)

---

## 🌟 Overview & Principles

**CLIN** is an ethical, secure utility designed to help users audit, organize, and clean their own personal Telegram accounts:
* **Zero AI Slop**: Functional-first, high-density Telegram Web + Apple Graphite aesthetic with subtle hacker green accents (`#00E887`). No floating gradient blobs or decorative lag.
* **Versioned Consent Gate**: Mandatory explicit acceptance of Terms & Privacy Policy (`AGREEMENT_VERSION=1`, `PRIVACY_VERSION=1`) before access. Full "Withdraw Consent & Shred Session" capability.
* **TelegramClientAdapter**: Business logic is cleanly decoupled from MTProto/Telethon infrastructure via abstract interfaces (`ITelegramClientAdapter`).
* **Absolute Whitelist Protection**: Whitelisted dialogs are strictly validated on the backend — destructive operations can never touch them.
* **Local Session Encryption (Fernet AES-128)**: Session files are isolated per user (`sessions/users/<user_id>/session.enc`) with dynamic salts. No plaintext passwords or phone numbers in logs or SQLite.
* **Integrated Support Center**: In-app ticketing system (`CLIN-10241`) with categorized threads and automated warnings against sharing credentials.
* **Rejoin Manifest**: Public channel usernames and invite links are captured prior to leaving, allowing instant rejoin at any time.

---

## 📐 Architecture

```text
CLIN/
├── main.py                     # aiogram 3.x bot entrypoint with slash command registration
├── webapp_server.py            # FastAPI backend for Telegram Mini App
├── config.py                   # Strict configuration and rate limiting
├── database.py                 # aiosqlite, versioned schema migrations, audit hash-chain
├── domain/                     # Pure domain logic & models
│   ├── models.py               # Domain DTOs (DialogItem, ScanResult, CleanupPlan)
│   └── heuristics.py           # Advisory scoring (dead channels, spam bots)
├── telegram_client/            # MTProto abstraction layer
│   ├── base.py                 # ITelegramClientAdapter interface
│   ├── telethon_adapter.py     # Concrete Telethon wrapper with domain exception mapping
│   ├── mock_adapter.py         # In-memory mock adapter for instant offline testing
│   ├── manager.py              # Isolated user session manager & path traversal guards
│   └── exceptions.py           # Domain exceptions
├── services/                   # Application services
│   ├── consent_service.py      # Versioned compliance gating & revocation
│   ├── support_service.py      # Support ticket system & knowledge base
│   ├── cleanup_service.py      # Coordinated cleanup with cooperative cancellation
│   ├── preview_service.py      # Dialog scan formatting
│   ├── whitelist_service.py    # Whitelist CRUD & server-side enforcement
│   ├── statistics_service.py   # Hygiene score & operation history
│   └── scheduler_service.py    # Background scheduler (disabled in serverless)
├── bot/                        # aiogram 3.x router, keyboards, and FSM handlers
├── webapp/                     # FastAPI API routers & Mini App static assets
│   ├── api/                    # /login, /scan, /cleanup, /history, /consent, /support
│   └── static/                 # Synchronized static files (index.html, style.css, app.js)
├── public/                     # Edge CDN static files for Vercel
└── tests/                      # Automated test suite (pytest)
```

---

## 🔑 Telegram API Setup Guide

To connect your account, Telegram requires MTProto application credentials (`API_ID` and `API_HASH`).

1. Open the official Telegram developer portal: **[https://my.telegram.org/](https://my.telegram.org/)**
2. Log in with your phone number and confirm via the Telegram app code.
3. Select **API development tools**.
4. If you do not have an application created yet, enter an App title (e.g. `CLIN`) and short name.
5. Copy your **API ID** (an integer) and **API Hash** (a 32-character hexadecimal string).
6. Enter them in CLIN or configure them as server defaults in `.env`.

> ⚠️ **Security Warning**: Never publish or share your API Hash. CLIN never logs your API Hash or sends it to external servers.

---

## ⚙️ Environment Configuration (`.env`)

Copy `.env.example` to `.env`:

```bash
# Telegram Bot
BOT_TOKEN=8929093343:AAGH9bw1I7VN-aSrMZQHBRbQ_0A0tvixIHI
WEBHOOK_SECRET_TOKEN=your-random-webhook-secret-token

# Telegram MTProto (Default Telegram Desktop credentials)
API_ID=2040
API_HASH=b1844dd0f62ee8e35e54135eab32ce24

# Security & Secrets
ENCRYPTION_MASTER_KEY=4P_lwcFkEzHYBLpAPHCZRxRGdKA7GOBGC4dZixj9QcY=
JWT_SECRET=your-secure-jwt-signing-secret

# URLs & Storage
WEBAPP_URL=https://telegram-account-cleaner.vercel.app
DATABASE_PATH=cleaner.db
SESSION_DIR=sessions

# Compliance Versions
AGREEMENT_VERSION=1
PRIVACY_VERSION=1
```

---

## 🧪 Automated Testing

CLIN includes a comprehensive automated test suite covering crypto round-trip, initData replay and clock skew, database migrations, IDOR cross-user protection, Telegram adapter mocks, and whitelist bypass resistance:

```bash
# Run full test suite
pytest -v

# Run with coverage report
pytest --cov=.
```

---

## 🚀 Running Locally

### 1. Launch FastAPI WebApp (Mini App Backend)
```bash
uvicorn webapp_server:app --host 0.0.0.0 --port 8080 --reload
```

### 2. Launch Telegram Bot (aiogram 3.x)
```bash
python main.py
```

---

## 🌐 Production Deployment (Vercel & Webhooks)

1. Deploy the project to Vercel:
```bash
vercel --prod --yes
```
2. Configure webhook for Telegram Bot:
```
https://<your-vercel-domain>/api/setup-webhook?secret=<WEBHOOK_SECRET_TOKEN>
```
3. Open Telegram and launch **`@ClinAcc_Bot`**!
