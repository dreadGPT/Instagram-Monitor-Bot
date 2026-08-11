import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# DataImpulse default (can be overridden via /setproxy)
PROXY_HOST = os.getenv("PROXY_HOST", "gw.dataimpulse.com")
PROXY_PORT = os.getenv("PROXY_PORT", "823")
PROXY_USER = os.getenv("PROXY_USER", "")
PROXY_PASS = os.getenv("PROXY_PASS", "")

CHECK_INTERVAL = 30   # seconds
REQUEST_TIMEOUT = 15  # seconds
