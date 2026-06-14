# Telegram ↔ Discord Support Bridge Bot

Python bot that connects Telegram users with Discord admin channels. User mappings, rules, and interview progress are stored in SQLite so data survives restarts.

## Features

- **Support button** — Creates or reuses a private Discord channel under the **Support** category for the user
- **Admin Application button** — Creates or reuses a private channel under **Admin**, then runs a 6-step interview
- **Rules button** — Lets users pick English, Malayalam, Hindi, or Manglish; content is read from Discord **Rules** channels and cached in SQLite
- **Two-way sync** — Telegram messages go to the active channel; Discord admin replies go back to Telegram (with @mention support)
- **Manglish UI** — All Telegram bot prompts are in Manglish

## Setup

### 1. Create bots

1. **Telegram:** Talk to [@BotFather](https://t.me/BotFather), create a bot, copy the token.
2. **Discord:** [Discord Developer Portal](https://discord.com/developers/applications) → New Application → Bot → copy token.
3. Enable **Message Content Intent** and **Server Members Intent** for the Discord bot.
4. Invite the bot to your server with permissions: Manage Channels, Send Messages, Read Message History, Attach Files.

### 2. Configure environment

```bash
copy .env.example .env
```

Edit `.env` with your tokens, `DISCORD_GUILD_ID`, and `DISCORD_ADMIN_ROLE_ID`.

### 3. Install and run

```bash
pip install -r requirements.txt
python main.py
```

On first run the bot creates (if missing):

| Category | Channels |
|----------|----------|
| **Support** | `support-{username}-{telegram_id}` per user |
| **Admin** | `admin-{username}-{telegram_id}` per user |
| **Rules** | `english-rules`, `malayalam-rules`, `hindi-rules`, `manglish-rules` |

### 4. Rules content

Post or edit messages in the Rules Discord channels. The bot syncs them to SQLite automatically. Telegram users see the cached text when they pick a language.

## Usage (Telegram)

1. Send `/start` to the bot in a **private chat**.
2. Tap **Support** to open a support channel and start messaging admins.
3. Tap **Admin Application** to apply (6 questions) and chat in the admin channel.
4. Tap **Rules** and choose a language.

## Data persistence

SQLite file: `bridge.db`

| Table | Purpose |
|-------|---------|
| `user_channels` | Telegram user ↔ Discord channel (support/admin) |
| `user_sessions` | Which channel type is active for forwarding |
| `admin_interviews` | 6-step application answers |
| `rules` | Cached rules per language |
| `message_links` | Reply threading between platforms |

## Deployment (Render / Railway)

Set `PORT=8080` (or your platform’s port). The bot exposes `GET /` for health checks.

## Project structure

```
main.py              Entry point
database.py          SQLite layer
config.py            Environment config
strings.py           Manglish UI text
bridge.py            Channel creation & message forwarding
telegram_handlers.py Telegram buttons, interview, sync
discord_bot.py       Discord events & rules sync
```
