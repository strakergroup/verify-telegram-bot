# Changelog

## [Unreleased]

- [Added]: Initial project scaffold -- Pipfile, Dockerfile, docker-compose.yml, .env.example, pyproject.toml (2026-02-16)
- [Added]: Pydantic settings configuration with environment variable support (2026-02-16)
- [Added]: Verify API async client with httpx (languages, balance, projects, file download, create project) (2026-02-16)
- [Added]: Pydantic models for all Verify API responses (Language, Project, SourceFile, TargetFile, etc.) (2026-02-16)
- [Added]: In-memory session store for per-user API key storage (2026-02-16)
- [Added]: /start and /help command handlers (2026-02-16)
- [Added]: /login, /logout, /status authentication handlers with API key validation (2026-02-16)
- [Added]: Paginated inline language keyboard with search, selection toggles, and pagination (2026-02-16)
- [Added]: Full translation ConversationHandler workflow (file upload -> language select -> title -> confirm -> create project) (2026-02-16)
- [Added]: /projects, /project detail, and /balance handlers (2026-02-16)
- [Added]: Main entry point with polling and webhook mode support (2026-02-16)
- [Added]: Unit tests for Verify client, session store, and keyboard builders (25 tests, all passing) (2026-02-16)
