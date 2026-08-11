# Instagram-Monitor-Bot
Discord bot that monitors Instagram account status (active/banned) and follower counts via proxy-rotated requests!
# Instagram Monitor Bot

A Discord bot that monitors Instagram accounts and sends real-time alerts when their status changes — either from **banned → active** (unban monitoring) or **active → banned** (ban monitoring). Built with Python, discord.py, and SQLite, with full proxy support and persistence across restarts.

---

## Features

- **Dual monitoring modes** — watch for an account getting unbanned *or* getting banned
- **False positive protection** — confirms status changes with 2 additional checks before firing an alert
- **Follower count reporting** — on unban events, displays the account's recovered follower count (with up to 3 retries to fetch it)
- **Persistent monitoring** — all active monitors survive bot restarts, resuming automatically on startup
- **Proxy support** — routes all Instagram requests through a configurable HTTP proxy to avoid IP blocks
- **Live proxy testing** — validates proxy credentials against ipify before saving
- **Proxy persistence** — proxy settings are saved to both SQLite and `.env`/`config.py` so they survive restarts
- **Check history** — stores and displays the last 10 ban/unban events with timestamps and elapsed time
- **Discord slash commands** — clean `/command` interface via Discord's application command system

---

## Commands

| Command | Description |
|---|---|
| `/unban <username>` | Start monitoring a banned account — alerts when it comes back |
| `/ban <username>` | Start monitoring an active account — alerts when it gets banned |
| `/stop <username>` | Stop monitoring a specific account |
| `/list` | Show all currently monitored accounts, split by mode |
| `/history` | Show the last 10 completed ban/unban events |
| `/setproxy <proxy>` | Set and test a new proxy — supports multiple formats (see below) |

### Proxy Formats for `/setproxy`

```
host:port
host:port:user:pass
user:pass@host:port
```

---

## How It Works

1. The bot polls each monitored Instagram account every **30 seconds** via a configurable proxy.
2. It first attempts Instagram's JSON endpoint (`?__a=1&__d=dis`). If that fails or returns no usable data, it falls back to scraping the HTML profile page.
3. When a status change is detected, the bot runs **2 confirmation checks** (5 seconds apart) before sending an alert — this eliminates false positives from intermittent network errors.
4. On unban detection, if follower count is unavailable, the bot retries up to **3 more times** before sending the alert anyway.
5. Alerts are sent as Discord embeds with follower count and total elapsed monitoring time.

---

## Project Structure

```
instagram_monitor_fixed/
├── bot.py            # Discord bot, slash commands, monitoring task loop
├── monitor.py        # Instagram account status checker (JSON + HTML fallback)
├── database.py       # SQLite helpers for monitors, proxy, and history
├── config.py         # Environment variable loading and defaults
├── requirements.txt  # Python dependencies
└── .env.example      # Template for environment variables
```

---

## Setup

### 1. Prerequisites

- Python 3.11+
- A Discord bot token ([Discord Developer Portal](https://discord.com/developers/applications))
- An HTTP proxy (recommended: [DataImpulse](https://dataimpulse.com) — preconfigured as the default)

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

Copy `.env.example` to `.env` and fill in your values:

```env
DISCORD_TOKEN=your_discord_bot_token

# Proxy (DataImpulse default — replace with your own)
PROXY_HOST=gw.dataimpulse.com
PROXY_PORT=823
PROXY_USER=your_username
PROXY_PASS=your_password
```

### 4. Run the bot

```bash
python bot.py
```

On first run, the bot will:
- Initialize the SQLite database (`monitor.db`)
- Load any saved proxy from the database
- Resume any monitors that were active before the last shutdown
- Sync slash commands to Discord

---

## Configuration

| Variable | Default | Description |
|---|---|---|
| `DISCORD_TOKEN` | *(required)* | Your Discord bot token |
| `PROXY_HOST` | `gw.dataimpulse.com` | Proxy hostname |
| `PROXY_PORT` | `823` | Proxy port |
| `PROXY_USER` | *(empty)* | Proxy username |
| `PROXY_PASS` | *(empty)* | Proxy password |
| `CHECK_INTERVAL` | `30` | Seconds between status checks (in `config.py`) |
| `REQUEST_TIMEOUT` | `15` | HTTP request timeout in seconds (in `config.py`) |

Proxy settings can also be updated at runtime via the `/setproxy` command — changes are written back to `.env` and `config.py` automatically.

---

## Database Schema

The bot uses a local SQLite file (`monitor.db`) with three tables:

**`monitors`** — active monitoring sessions
- `username`, `mode` (ban/unban), `channel_id`, `user_id`, `start_time`, `checks`

**`proxy`** — saved proxy configuration (single row)
- `host`, `port`, `user`, `pass`

**`history`** — completed ban/unban events
- `username`, `mode`, `result`, `followers`, `elapsed`, `timestamp`

---

## Dependencies

| Package | Version | Purpose |
|---|---|---|
| `discord.py` | 2.3.2 | Discord bot framework and slash commands |
| `aiohttp` | 3.9.5 | Async HTTP requests to Instagram |
| `python-dotenv` | 1.0.1 | `.env` file loading |
| `Pillow` | latest | Image support (discord.py optional dependency) |

---

## Discord Bot Permissions

When inviting the bot to your server, it needs the following permissions:

- **Send Messages**
- **Embed Links**
- **Read Message History**
- **Use Slash Commands** (Application Commands scope)

Make sure to enable the **`applications.commands`** OAuth2 scope when generating your invite link.

---

## Notes

- Instagram's unofficial endpoints are used for account status checks. This is outside Instagram's Terms of Service — use responsibly and keep the repository private.
- A proxy is strongly recommended. Without one, Instagram will rate-limit or block requests from your server's IP quickly.
- Slash commands may take up to 1 hour to appear globally after the bot first syncs. For instant testing, restrict the bot to a single server (guild-scoped sync).
