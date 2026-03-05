# Telegram Verify Bot

A Telegram bot that provides a chat-based interface to the Straker Verify API, enabling users to create translation projects by uploading files and selecting target languages directly from Telegram.

## Features

- **Authentication** -- Users login with their Verify API key via `/login`
- **File Translation** -- Multi-step workflow: upload files, select languages, set title, confirm
- **Project Tracking** -- View recent projects and their status via `/projects`
- **Token Balance** -- Check account balance via `/balance`
- **Language Search** -- Paginated inline keyboard with search for 100+ languages

## Prerequisites

- Python 3.12+
- [pipenv](https://pipenv.pypa.io/)
- A Telegram Bot Token (from [@BotFather](https://t.me/botfather))
- A Straker Verify API key

## Setup

### 1. Clone and install

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
ENVIRONMENT=local
```

### 3. Register commands with BotFather

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
cancel - Cancel the current operation
```

### 4. Run the bot

```bash
pipenv run python -m src.main
```

### 5. Run with Docker

```bash
docker-compose up --build
```

## Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message with getting started instructions |
| `/help` | Show all available commands |
| `/login` | Authenticate with your Verify API key |
| `/logout` | Remove your stored API key |
| `/status` | Show authentication status and token balance |
| `/translate` | Start a new translation project |
| `/projects` | List your recent projects |
| `/project <id>` | Show details for a specific project |
| `/balance` | Check your token balance |
| `/cancel` | Cancel the current operation |

## Translation Workflow

1. **Login** -- `/login` then send your Verify API key
2. **Start** -- `/translate` to begin
3. **Upload** -- Send file(s) as documents, then `/done`
4. **Languages** -- Tap to select target languages from the inline keyboard
5. **Title** -- Enter a project title
6. **Confirm** -- Review summary and tap Confirm to create the project

## Testing

```bash
pipenv run pytest tests/ -v
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | Yes | -- | Bot token from BotFather |
| `VERIFY_API_URL` | No | `https://api-verify.straker.ai` | Verify API base URL |
| `ENVIRONMENT` | No | `local` | `local`, `uat`, or `production` |
| `LOG_LEVEL` | No | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `BOT_MODE` | No | `polling` | `polling` or `webhook` |
| `WEBHOOK_URL` | If webhook | -- | Public HTTPS URL for webhook |
| `WEBHOOK_SECRET` | If webhook | -- | Secret token for webhook verification |

## Project Structure

```
src/
  main.py           # Entry point, handler registration
  config.py          # Pydantic settings
  bot/
    handlers/
      start.py       # /start, /help
      auth.py        # /login, /logout, /status
      translate.py   # Translation conversation workflow
      projects.py    # /projects, /project <id>
      balance.py     # /balance
    keyboards.py     # Inline keyboard builders
    states.py        # Conversation state enums
  verify/
    client.py        # Async Verify API wrapper
    models.py        # Pydantic response models
  session/
    store.py         # In-memory session manager
tests/
  conftest.py
  test_verify_client.py
  test_session_store.py
  test_keyboards.py
```
