# Telegram Submission Notifications — Design

Date: 2026-07-22
Status: Approved

## Problem

Submissions (especially from new users) can fail without the admin noticing.
We want real-time notifications about every submission and its outcome, sent
to a Telegram chat via the existing bot `omj_validator_bot`.

## Design

### Notifier module: `app/notifications.py`

- `async def send_telegram_message(text: str) -> None`
- Uses `httpx.AsyncClient` to POST `https://api.telegram.org/bot{token}/sendMessage`
  with `chat_id`, `text`, short timeout (~10s).
- Fire-and-forget semantics: every exception is caught and logged as a warning.
  A Telegram outage must never affect submission processing.
- No-op (debug log) when `telegram_bot_token` or `telegram_chat_id` is unset.

### Configuration: `app/config.py`

- `telegram_bot_token: Optional[str] = None`
- `telegram_chat_id: Optional[str] = None`

Both optional; feature disabled unless both set. Token lives only in `.env`
(local) and `.env.prod` (server) — never committed.

### Hook point: `app/websocket/handler.py`

`process_submission_background` is the single choke point for both user
submissions and admin re-runs. Three notifications per submission lifecycle:

1. **Start** — when processing begins: user (email/name looked up via user
   repository), task `year/etap/task_number`, submission id, image count.
2. **Completed** — score (e.g. `5/6` using etap max), user, task.
3. **Failed** — clearly marked (❌ FAILED), user, task, error message. Sent
   from both the `AIProviderError` and unexpected-exception branches.

Notifications are sent with `await` from the background task (already async,
off the request path).

### Deployment

- Add `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` to the api service in
  `docker-compose.prod.yml` (optional, empty default) and to `.env.prod`.
- Chat ID bootstrap: admin messages the bot once; we fetch the chat id via
  `getUpdates` and store it in the env files.

## Out of scope

- Telegram channel/group management, message threading, retries/queueing,
  notification preferences UI.
