Instagram Monitor Bot

A simple Discord bot I made to monitor Instagram accounts and get notified when their status changes.

You can use it to watch a banned account until it comes back, or monitor an active account and get notified if it becomes unavailable.

The bot is written in Python and uses discord.py, aiohttp, and SQLite.

Features

* Monitor banned accounts for unban
* Monitor active accounts for ban
* Sends Discord alerts when something changes
* Does extra checks before sending an alert to avoid false positives
* Shows follower count when an account comes back
* Saves monitors in SQLite, so they don’t disappear after a restart
* Proxy support
* Proxy testing with /setproxy
* Keeps a small history of previous events
* Slash commands
* Automatically resumes old monitors when the bot starts again

Commands

/unban <username>   Start watching a banned account
/ban <username>     Start watching an active account
/stop <username>    Stop monitoring an account
/list               Show current monitors
/history            Show recent events
/setproxy <proxy>  Set a proxy

Proxy formats

/setproxy accepts these formats:

host:port
host:port:user:pass
user:pass@host:port

How it works

The bot checks monitored accounts every 30 seconds by default.

It tries to get the account information first and, if that doesn’t work, it uses another method as a fallback.

If the bot thinks the account changed status, it doesn’t immediately send the alert. It checks the account two more times with a small delay between each check.

This is mainly to avoid alerts caused by temporary request errors.

For unban monitoring, the bot also tries to grab the follower count. If it can’t get it on the first try, it retries a few times.

Files

instagram_monitor_fixed/
│
├── bot.py
├── monitor.py
├── database.py
├── config.py
├── requirements.txt
└── .env.example

bot.py

Discord bot, commands and the main monitoring loop.

monitor.py

Handles the Instagram checks and tries to figure out the current account status.

database.py

SQLite stuff. Stores monitors, proxy settings and history.

config.py

Loads the configuration and environment variables.

Setup

1. Install Python

Python 3.11+ is recommended.

2. Install the requirements

pip install -r requirements.txt

3. Create .env

Copy .env.example to .env and add your bot token.

DISCORD_TOKEN=your_discord_bot_token
PROXY_HOST=your_proxy_host
PROXY_PORT=your_proxy_port
PROXY_USER=your_proxy_username
PROXY_PASS=your_proxy_password

4. Run it

python bot.py

The database will be created automatically the first time you run the bot.

If you already had monitors running before restarting the bot, it will load them again from the database.

Config

These are the main settings:

DISCORD_TOKEN    Discord bot token
PROXY_HOST       Proxy host
PROXY_PORT       Proxy port
PROXY_USER       Proxy username
PROXY_PASS       Proxy password
CHECK_INTERVAL   Time between checks (default: 30)
REQUEST_TIMEOUT  Request timeout (default: 15)

You can also change the proxy from Discord using:

/setproxy <proxy>

The new proxy is saved so you don’t have to enter it again after restarting.

Database

Everything is stored in one SQLite database:

monitor.db

There are three main tables:

monitors
proxy
history

monitors keeps track of accounts currently being watched.

proxy stores the current proxy settings.

history keeps the recent ban/unban results.

Requirements

discord.py==2.3.2
aiohttp==3.9.5
python-dotenv==1.0.1
Pillow

Discord permissions

The bot needs:

* Send Messages
* Embed Links
* Read Message History
* Use Slash Commands

