# Telegram Verify Bot

A multi-channel bot (Telegram + WhatsApp) that provides a chat-based interface to the Straker Verify API and ECFMG Order API. Users can create translation projects, order ECFMG certified translations, and receive status notifications — all from their messaging app.

## Features

- **Telegram Bot** -- Full interactive bot with inline keyboards
- **WhatsApp Bot** -- WhatsApp Cloud API integration with the same core workflows
- **File Translation** -- Upload files, select languages, confirm, and track projects
- **ECFMG Certified Translation** -- Order certified translations (PDF only) with quote and payment link
- **Status Notifications** -- Receive project completion callbacks via Telegram or WhatsApp
- **Authentication** -- Per-user API key sessions with secure key deletion

## Prerequisites

- Python 3.12+
- [Pipenv](https://pipenv.pypa.io/)
- A Telegram Bot Token (from [@BotFather](https://t.me/botfather))
- A Straker Verify API key (for translation features)
- For WhatsApp: WhatsApp Cloud API credentials
- For local development: [ngrok](https://ngrok.com/) or similar tunnel (webhook-based)

## Setup

### 1. Install dependencies

```bash
cd deploy/apps/telegram-verify-bot
pipenv install --dev
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and set at minimum:

```
TELEGRAM_BOT_TOKEN=<your-bot-token-from-botfather>
VERIFY_API_URL=https://api-verify.straker.ai
ORDER_BASE_URL=https://uat-order.strakertranslations.com
WEBHOOK_BASE_URL=<your-ngrok-url>
ENVIRONMENT=local
```

### 3. Start a tunnel (local development)

The bot uses webhook mode, so Telegram needs a public URL to reach your machine:

```bash
ngrok http 8443
```

Set the resulting URL as `WEBHOOK_BASE_URL` in `.env`.

### 4. Register commands with BotFather

Send `/setcommands` to [@BotFather](https://t.me/botfather) and paste:

```
start - Welcome message and getting started
help - Show available commands
login - Authenticate with your Verify API key
logout - Remove your stored API key
status - Show your authentication status
translate - Start a new translation project
projects - List your recent projects
balance - Check your token balance
ecfmg - Order an ECFMG certified translation
cancel - Cancel the current operation
```

### 5. Run the bot

```bash
pipenv run python -m src.main
```

### 6. Run with Docker

```bash
docker-compose up --build
```

## Bot Commands

| Command | Auth Required | Description |
|---------|:---:|-------------|
| `/start` | No | Welcome message with getting started instructions |
| `/help` | No | Show all available commands |
| `/login` | No | Authenticate with your Verify API key |
| `/logout` | Yes | Remove your stored API key |
| `/status` | Yes | Show authentication status and token balance |
| `/translate` | Yes | Start a new translation project |
| `/projects` | Yes | List your recent projects |
| `/project <id>` | Yes | Show details for a specific project |
| `/download <id>` | Yes | Download translated files |
| `/balance` | Yes | Check your token balance |
| `/ecfmg` | No | Order an ECFMG certified translation |
| `/cancel` | No | Cancel the current operation |

## Workflows

### Translation (Verify API)

1. `/login` -- send your Verify API key
2. `/translate` -- begin the workflow
3. Send file(s) as documents, then `/done`
4. Select target languages from the inline keyboard
5. Enter a project title
6. Review summary and confirm

### ECFMG Certified Translation (Order API)

1. `/ecfmg` -- begin the workflow (no login required)
2. Enter first name, last name, email, phone
3. Select source language and country
4. Upload document (**PDF only**)
5. Accept terms and conditions
6. Optionally add notes
7. Review summary and confirm
8. Receive quote with payment link

## WhatsApp Integration

The bot also supports WhatsApp via the WhatsApp Cloud API. WhatsApp endpoints are enabled when `WHATSAPP_ACCESS_TOKEN` and `WHATSAPP_PHONE_NUMBER_ID` are set in `.env`.

WhatsApp supports the same core workflows (translate, ECFMG, projects, download) through a text-based command interface.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/whatsapp/webhook` | POST | Incoming WhatsApp messages |
| `/whatsapp/webhook` | GET | Webhook verification (Meta handshake) |

## Environment Variables

| Variable | Required | Default | Description |
|----------|:---:|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | Yes | -- | Bot token from BotFather |
| `VERIFY_API_URL` | No | `https://api-verify.straker.ai` | Verify API base URL |
| `ORDER_BASE_URL` | No | `https://order.strakertranslations.com` | ECFMG Order API base URL |
| `ENVIRONMENT` | No | `local` | `local`, `uat`, or `production` |
| `LOG_LEVEL` | No | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `PORT` | No | `8443` | Server listen port |
| `WEBHOOK_BASE_URL` | Yes | -- | Public HTTPS URL (e.g. ngrok) for Telegram webhook |
| `WEBHOOK_SECRET` | No | -- | Secret token for Telegram webhook validation |
| `WHATSAPP_ACCESS_TOKEN` | No | -- | WhatsApp Cloud API access token |
| `WHATSAPP_PHONE_NUMBER_ID` | No | -- | WhatsApp Phone Number ID |
| `WHATSAPP_VERIFY_TOKEN` | No | -- | WhatsApp webhook verification token |
| `WHATSAPP_APP_SECRET` | No | -- | WhatsApp app secret for signature validation |
| `VERIFY_DB_HOST` | No | -- | MySQL host for callback notification targets |
| `VERIFY_DB_PORT` | No | `3306` | MySQL port |
| `VERIFY_DB_USER` | No | -- | MySQL user |
| `VERIFY_DB_PASSWORD` | No | -- | MySQL password |
| `VERIFY_DB_NAME` | No | `verify` | MySQL database name |

See `.env.example` for a ready-to-copy template.

## Testing

```bash
pipenv run pytest tests/ -v

# With coverage
pipenv run coverage run -m pytest
pipenv run coverage report
```

## Project Structure

```
src/
  main.py                  Entry point, handler registration, FastAPI app
  config.py                Pydantic settings
  bot/
    handlers/
      start.py             /start, /help
      auth.py              /login, /logout, /status
      translate.py         Translation conversation workflow
      ecfmg.py             ECFMG certified translation workflow
      projects.py          /projects, /project <id>
      balance.py           /balance
      download.py          /download <id>
    keyboards.py           Inline keyboard builders
    states.py              Conversation state enums
  whatsapp_bot/
    router.py              WhatsApp message routing
    session_store.py       WhatsApp session management
    states.py              WhatsApp conversation states
    handlers/
      auth.py              WhatsApp login/logout
      translate.py         WhatsApp translation workflow
      ecfmg.py             WhatsApp ECFMG workflow
      projects.py          WhatsApp project listing
      download.py          WhatsApp file download
      menu.py              WhatsApp help/menu
  whatsapp/
    client.py              WhatsApp Cloud API HTTP client
    models.py              WhatsApp webhook payload models
    signature.py           Request signature validation
  verify/
    client.py              Async Verify API wrapper
    models.py              Verify API response models
  order/
    client.py              Async ECFMG Order API wrapper
    models.py              Order API response models
  session/
    store.py               In-memory session manager
  callback/
    handler.py             Project completion callback notifications
  db/
    connection.py          MySQL database connection (notification targets)
tests/
  conftest.py
  test_verify_client.py
  test_session_store.py
  test_keyboards.py
  test_order_client.py
  test_ecfmg.py
  test_wa_router.py
  test_wa_session_store.py
  test_whatsapp_client.py
  test_whatsapp_signature.py
  test_callback.py
  test_db.py
```

## License

Proprietary -- Straker Translations.
