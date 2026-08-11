import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import time
import aiohttp

from config import (
    DISCORD_TOKEN, CHECK_INTERVAL, REQUEST_TIMEOUT,
    PROXY_HOST, PROXY_PORT, PROXY_USER, PROXY_PASS,
)
from monitor import check_instagram_account
from database import (
    init_db,
    save_monitor, remove_monitor, update_checks, load_all_monitors,
    save_proxy, load_proxy,
    save_history,
)

# ── Bot Setup ─────────────────────────────────────────────────────────────────

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# Current proxy (loaded from DB or .env on startup)
current_proxy = {
    "host": PROXY_HOST,
    "port": PROXY_PORT,
    "user": PROXY_USER,
    "pass": PROXY_PASS,
}

def get_proxy_url() -> str:
    p = current_proxy
    if p["user"] and p["pass"]:
        return f"http://{p['user']}:{p['pass']}@{p['host']}:{p['port']}"
    return f"http://{p['host']}:{p['port']}"


def _update_env_file(host: str, port: str, user: str, passwd: str):
    """Update PROXY_* values in .env file so they persist across restarts."""
    import pathlib
    env_path = pathlib.Path(".env")

    # If .env doesn't exist, create from .env.example or create fresh
    if not env_path.exists():
        example = pathlib.Path(".env.example")
        if example.exists():
            env_path.write_text(example.read_text())
        else:
            env_path.write_text("")

    lines = env_path.read_text().splitlines()
    keys_to_update = {
        "PROXY_HOST": host,
        "PROXY_PORT": port,
        "PROXY_USER": user,
        "PROXY_PASS": passwd,
    }
    updated_keys = set()
    new_lines = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#") or "=" not in stripped:
            new_lines.append(line)
            continue
        key = stripped.split("=", 1)[0].strip()
        if key in keys_to_update:
            new_lines.append(f"{key}={keys_to_update[key]}")
            updated_keys.add(key)
        else:
            new_lines.append(line)

    # Append any keys that weren't already in .env
    for key, val in keys_to_update.items():
        if key not in updated_keys:
            new_lines.append(f"{key}={val}")

    env_path.write_text("\n".join(new_lines) + "\n")
    print(f"📝 .env updated with new proxy: {host}:{port}")


def _update_config_file(host: str, port: str, user: str, passwd: str):
    """Rewrite PROXY_* defaults in config.py so the values persist across restarts."""
    import re, pathlib
    cfg = pathlib.Path("config.py")
    if not cfg.exists():
        return
    text = cfg.read_text()
    replacements = {
        r'PROXY_HOST\s*=\s*os\.getenv\("PROXY_HOST",\s*"[^"]*"\)':
            f'PROXY_HOST = os.getenv("PROXY_HOST", "{host}")',
        r'PROXY_PORT\s*=\s*os\.getenv\("PROXY_PORT",\s*"[^"]*"\)':
            f'PROXY_PORT = os.getenv("PROXY_PORT", "{port}")',
        r'PROXY_USER\s*=\s*os\.getenv\("PROXY_USER",\s*"[^"]*"\)':
            f'PROXY_USER = os.getenv("PROXY_USER", "{user}")',
        r'PROXY_PASS\s*=\s*os\.getenv\("PROXY_PASS",\s*"[^"]*"\)':
            f'PROXY_PASS = os.getenv("PROXY_PASS", "{passwd}")',
    }
    for pattern, replacement in replacements.items():
        text = re.sub(pattern, replacement, text)
    cfg.write_text(text)
    print(f"📝 config.py updated with new proxy: {host}:{port}")


# ── Task Storage ──────────────────────────────────────────────────────────────
# { username: { task, channel_id, user_id, start_time, checks, mode } }
monitoring_tasks: dict = {}


# ── Helpers ───────────────────────────────────────────────────────────────────

def format_elapsed(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h}h {m}m {s}s"


def fmt_followers(n) -> str:
    try:
        n = int(n)
        if n >= 1_000_000: return f"{n/1_000_000:.1f}M"
        if n >= 1_000:     return f"{n/1_000:.1f}K"
        return f"{n:,}"
    except:
        return "N/A"


def build_alert_embed(mode: str, username: str, followers: int | None, elapsed: int) -> discord.Embed:
    url = f"https://www.instagram.com/{username}/"
    follower_str = fmt_followers(followers) if followers is not None else "N/A"
    elapsed_str = format_elapsed(elapsed)

    if mode == "unban":
        embed = discord.Embed(
            description=f"[Account Recovered | @{username} 🏆✅]({url}) | 👥 Followers: {follower_str} | ⏱ Time Elapsed: {elapsed_str}",
            color=0x00ff00,
        )
    else:
        embed = discord.Embed(
            description=f"[Account Banned Successfully — @{username} ❌]({url}) | ⏱ Time Elapsed: {elapsed_str}",
            color=0xff0000,
        )
    return embed


# ── Events ────────────────────────────────────────────────────────────────────

@bot.event
async def on_ready():
    # Init DB
    init_db()

    # Load saved proxy
    saved_proxy = load_proxy()
    if saved_proxy:
        current_proxy["host"] = saved_proxy["host"]
        current_proxy["port"] = saved_proxy["port"]
        current_proxy["user"] = saved_proxy["user"]
        current_proxy["pass"] = saved_proxy["pass"]
        print(f"🌐 Proxy loaded from DB: {saved_proxy['host']}:{saved_proxy['port']}")

    # Resume saved monitors
    saved = load_all_monitors()
    for row in saved:
        uname = row["username"]
        if uname not in monitoring_tasks:
            task = asyncio.create_task(
                monitor_loop(uname, row["channel_id"], row["user_id"], row["mode"], row["start_time"], row["checks"])
            )
            monitoring_tasks[uname] = {
                "task": task,
                "channel_id": row["channel_id"],
                "user_id": row["user_id"],
                "start_time": row["start_time"],
                "checks": row["checks"],
                "mode": row["mode"],
            }
            print(f"▶️  Resumed [{row['mode'].upper()}] monitoring: @{uname}")

    await bot.tree.sync()
    print(f"✅ Bot ready: {bot.user} | Resumed {len(saved)} monitor(s)")
    await bot.change_presence(
        activity=discord.Activity(type=discord.ActivityType.watching, name="Instagram accounts")
    )


# ── /unban ────────────────────────────────────────────────────────────────────

@bot.tree.command(name="unban", description="Monitor a banned Instagram account until it gets unbanned")
@app_commands.describe(username="Instagram username (without @)")
async def unban_command(interaction: discord.Interaction, username: str):
    username = username.lstrip("@").strip().lower()

    if username in monitoring_tasks:
        await interaction.response.send_message(
            f"⚠️ **@{username}** is already being monitored!", ephemeral=True
        )
        return

    await interaction.response.defer()

    result = await check_instagram_account(username, get_proxy_url(), REQUEST_TIMEOUT)
    status = result.get("status")

    if status == "active":
        followers = result.get("followers")
        elapsed = 0
        embed = build_alert_embed("unban", username, followers, elapsed)
        await interaction.followup.send(embed=embed)
        return

    start_time = time.time()
    save_monitor(username, "unban", interaction.channel_id, interaction.user.id, start_time)

    task = asyncio.create_task(
        monitor_loop(username, interaction.channel_id, interaction.user.id, "unban", start_time, 0)
    )
    monitoring_tasks[username] = {
        "task": task,
        "channel_id": interaction.channel_id,
        "user_id": interaction.user.id,
        "start_time": start_time,
        "checks": 0,
        "mode": "unban",
    }

    embed = discord.Embed(
        description=f"Monitoring **@{username}** — will notify when unbanned.",
        color=0x00ff00,
    )
    embed.set_author(name="Monitoring Started")
    await interaction.followup.send(embed=embed)


# ── /ban ──────────────────────────────────────────────────────────────────────

@bot.tree.command(name="ban", description="Monitor an active Instagram account until it gets banned")
@app_commands.describe(username="Instagram username (without @)")
async def ban_command(interaction: discord.Interaction, username: str):
    username = username.lstrip("@").strip().lower()

    if username in monitoring_tasks:
        await interaction.response.send_message(
            f"⚠️ **@{username}** is already being monitored!", ephemeral=True
        )
        return

    await interaction.response.defer()

    result = await check_instagram_account(username, get_proxy_url(), REQUEST_TIMEOUT)
    status = result.get("status")

    if status == "banned":
        elapsed = 0
        embed = build_alert_embed("ban", username, None, elapsed)
        await interaction.followup.send(embed=embed)
        return

    start_time = time.time()
    save_monitor(username, "ban", interaction.channel_id, interaction.user.id, start_time)

    task = asyncio.create_task(
        monitor_loop(username, interaction.channel_id, interaction.user.id, "ban", start_time, 0)
    )
    monitoring_tasks[username] = {
        "task": task,
        "channel_id": interaction.channel_id,
        "user_id": interaction.user.id,
        "start_time": start_time,
        "checks": 0,
        "mode": "ban",
    }

    embed = discord.Embed(
        description=f"Monitoring **@{username}** — will notify when banned.",
        color=0xff0000,
    )
    embed.set_author(name="Monitoring Started")
    await interaction.followup.send(embed=embed)


# ── /stop ─────────────────────────────────────────────────────────────────────

@bot.tree.command(name="stop", description="Stop monitoring an Instagram account")
@app_commands.describe(username="Instagram username to stop")
async def stop_command(interaction: discord.Interaction, username: str):
    username = username.lstrip("@").strip().lower()

    if username not in monitoring_tasks:
        await interaction.response.send_message(
            f"❌ **@{username}** is not being monitored.", ephemeral=True
        )
        return

    monitoring_tasks[username]["task"].cancel()
    data = monitoring_tasks.pop(username)
    remove_monitor(username)

    elapsed = int(time.time() - data["start_time"])
    color = 0x00ff00 if data["mode"] == "unban" else 0xff0000

    embed = discord.Embed(
        description=(
            f"Stopped monitoring **@{username}**\n"
            f"⏱️ Time: `{format_elapsed(elapsed)}` | 🔁 Checks: `{data['checks']}`"
        ),
        color=color,
    )
    embed.set_author(name="⛔ Monitoring Stopped")
    await interaction.response.send_message(embed=embed)


# ── /list ─────────────────────────────────────────────────────────────────────

@bot.tree.command(name="list", description="Show all accounts being monitored")
async def list_command(interaction: discord.Interaction):
    if not monitoring_tasks:
        await interaction.response.send_message("📭 No accounts are being monitored.", ephemeral=True)
        return

    unban_list = [(u, d) for u, d in monitoring_tasks.items() if d["mode"] == "unban"]
    ban_list   = [(u, d) for u, d in monitoring_tasks.items() if d["mode"] == "ban"]

    embeds = []

    if unban_list:
        lines = []
        for u, d in unban_list:
            elapsed = int(time.time() - d["start_time"])
            lines.append(f"{u}  •  ⏱️ {format_elapsed(elapsed)}")
        embed = discord.Embed(
            description="\n".join(lines) + f"\n\n**Total Monitoring: {len(unban_list)}**",
            color=0x00ff00,
        )
        embed.set_author(name="✅ Unban Monitor List")
        embeds.append(embed)

    if ban_list:
        lines = []
        for u, d in ban_list:
            elapsed = int(time.time() - d["start_time"])
            lines.append(f"{u}  •  ⏱️ {format_elapsed(elapsed)}")
        embed = discord.Embed(
            description="\n".join(lines) + f"\n\n**Total Monitoring: {len(ban_list)}**",
            color=0xff0000,
        )
        embed.set_author(name="🚫 Ban Monitor List")
        embeds.append(embed)

    await interaction.response.send_message(embeds=embeds)


# ── /history ──────────────────────────────────────────────────────────────────

@bot.tree.command(name="history", description="Show last 10 ban/unban events")
async def history_command(interaction: discord.Interaction):
    import sqlite3
    from database import DB_PATH
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM history ORDER BY timestamp DESC LIMIT 10"
    ).fetchall()
    conn.close()

    if not rows:
        await interaction.response.send_message("📭 No history yet.", ephemeral=True)
        return

    lines = []
    for r in rows:
        ts = time.strftime("%d/%m %H:%M", time.gmtime(r["timestamp"]))
        emoji = "🏆✅" if r["mode"] == "unban" else "❌☠️"
        lines.append(f"`{ts}` {emoji} **@{r['username']}** — {format_elapsed(r['elapsed'])}")

    embed = discord.Embed(
        title="📜 Monitor History",
        description="\n".join(lines),
        color=0x7289da,
    )
    await interaction.response.send_message(embed=embed)


# ── /setproxy ─────────────────────────────────────────────────────────────────

def _parse_proxy(proxy: str):
    """
    Supported formats:
      1. host:port
      2. host:port:user:pass
      3. user:pass@host:port          ← DataImpulse style
    Returns (host, port, user, passwd) or raises ValueError.
    """
    proxy = proxy.strip()

    # Format 3: user:pass@host:port
    if "@" in proxy:
        creds, hostport = proxy.rsplit("@", 1)
        if ":" not in creds or ":" not in hostport:
            raise ValueError("bad format")
        user, passwd = creds.split(":", 1)
        host, port = hostport.rsplit(":", 1)
        return host, port, user, passwd

    # Format 1 & 2: colon-separated
    parts = proxy.split(":")
    if len(parts) == 4:
        host, port, user, passwd = parts
        return host, port, user, passwd
    elif len(parts) == 2:
        host, port = parts
        return host, port, "", ""

    raise ValueError("bad format")


@bot.tree.command(
    name="setproxy",
    description="Set and test proxy — supports host:port:user:pass OR user:pass@host:port"
)
@app_commands.describe(proxy="Proxy — e.g. user:pass@host:port  or  host:port:user:pass  or  host:port")
async def setproxy_command(interaction: discord.Interaction, proxy: str):
    await interaction.response.defer()

    try:
        host, port, user, passwd = _parse_proxy(proxy)
    except ValueError:
        await interaction.followup.send(
            "❌ Invalid format. Supported formats:\n"
            "• `host:port:user:pass`\n"
            "• `user:pass@host:port`\n"
            "• `host:port`",
            ephemeral=True,
        )
        return

    test_url = f"http://{user}:{passwd}@{host}:{port}" if user else f"http://{host}:{port}"

    # Test proxy using ipify (no rate limits, no Instagram blocks)
    proxy_works = False
    proxy_ip = None
    error_msg = "Unknown error"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.ipify.org?format=json",
                proxy=test_url,
                timeout=aiohttp.ClientTimeout(total=10),
                ssl=False,
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    proxy_ip = data.get("ip", "unknown")
                    proxy_works = True
                else:
                    error_msg = f"HTTP {resp.status}"
    except Exception as e:
        error_msg = str(e)

    if proxy_works:
        current_proxy["host"] = host
        current_proxy["port"] = port
        current_proxy["user"] = user
        current_proxy["pass"] = passwd
        save_proxy(host, port, user, passwd)
        # Persist to both .env and config.py so proxy survives restarts
        _update_env_file(host, port, user, passwd)
        _update_config_file(host, port, user, passwd)

        embed = discord.Embed(
            description=f"✅ **Proxy set successfully!**\n```{host}:{port}```",
            color=0x00ff00,
        )
        embed.set_author(name="Proxy Set Successfully")
    else:
        embed = discord.Embed(
            description=f"❌ **Proxy failed!**\n```{host}:{port}```\nReason: `{error_msg}`",
            color=0xff0000,
        )
        embed.set_author(name="Proxy Test Failed")

    await interaction.followup.send(embed=embed)


# ── Monitor Loop ──────────────────────────────────────────────────────────────

async def monitor_loop(
    username: str, channel_id: int, user_id: int,
    mode: str, start_time: float, initial_checks: int
):
    channel = bot.get_channel(channel_id)
    local_checks = initial_checks

    while True:
        try:
            result = await check_instagram_account(username, get_proxy_url(), REQUEST_TIMEOUT)
            local_checks += 1

            # Sync checks to memory + DB every 10 checks
            if username in monitoring_tasks:
                monitoring_tasks[username]["checks"] = local_checks
                if local_checks % 10 == 0:
                    update_checks(username, local_checks)

            status = result.get("status")
            triggered = (mode == "unban" and status == "active") or \
                        (mode == "ban"   and status == "banned")

            if triggered:
                # Confirm with 2 more checks before firing (avoid false positives)
                confirmed = True
                for confirm_attempt in range(2):
                    await asyncio.sleep(5)
                    confirm_result = await check_instagram_account(username, get_proxy_url(), REQUEST_TIMEOUT)
                    confirm_status = confirm_result.get("status")
                    print(f"[{username}] Confirm {confirm_attempt+1}/2 → {confirm_status}")
                    if confirm_status != status:
                        confirmed = False
                        print(f"[{username}] False positive — status changed back to {confirm_status}, resuming monitor")
                        break

                if not confirmed:
                    await asyncio.sleep(CHECK_INTERVAL)
                    continue

                elapsed = int(time.time() - start_time)
                followers = result.get("followers")

                # Retry up to 3 times if followers not received (unban only)
                if mode == "unban" and followers is None:
                    for attempt in range(3):
                        await asyncio.sleep(5)
                        retry = await check_instagram_account(username, get_proxy_url(), REQUEST_TIMEOUT)
                        followers = retry.get("followers")
                        print(f"[{username}] Followers retry {attempt+1}/3 → {followers}")
                        if followers is not None:
                            break

                alert_embed = build_alert_embed(mode, username, followers, elapsed)

                # Save to history
                result_label = "unbanned" if mode == "unban" else "banned"
                save_history(username, mode, result_label, followers, elapsed)

                # Remove from DB + memory
                remove_monitor(username)
                if username in monitoring_tasks:
                    del monitoring_tasks[username]

                if channel:
                    await channel.send(embed=alert_embed)
                break

            elif status == "error":
                print(f"[{mode.upper()}][{username}] {result.get('error')} (HTTP {result.get('http_code')})")

            await asyncio.sleep(CHECK_INTERVAL)

        except asyncio.CancelledError:
            update_checks(username, local_checks)
            print(f"[{username}] Monitoring cancelled.")
            break
        except Exception as e:
            print(f"[{username}] Unexpected: {e}")
            await asyncio.sleep(CHECK_INTERVAL)


# ── Run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("❌ Set DISCORD_TOKEN in .env!")
        exit(1)
    bot.run(DISCORD_TOKEN)