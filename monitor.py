import asyncio
import re
import aiohttp

JSON_URL = "https://www.instagram.com/{username}/?__a=1&__d=dis"
HTML_URL = "https://www.instagram.com/{username}/"

HEADERS = {
    "User-Agent"      : "Mozilla/5.0 (Linux; Android 11; Mobile)",
    "Accept-Language" : "en-US,en;q=0.9",
    "X-IG-App-ID"     : "936619743392459",
}


def parse_human_number(txt: str):
    t = txt.lower().replace(",", "").strip()
    mult = 1
    if t.endswith("k"):   mult, t = 1_000, t[:-1]
    elif t.endswith("m"): mult, t = 1_000_000, t[:-1]
    elif t.endswith("b"): mult, t = 1_000_000_000, t[:-1]
    try:    return int(float(t) * mult)
    except: return None


async def _raw_check(username: str, proxy_url: str, timeout: int) -> tuple[bool, int | None]:
    """
    Exact same logic as dost's check_account.
    Returns (is_active, followers)
    """
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:

        # ── 1) JSON endpoint ──────────────────────────────────────────────
        try:
            async with session.get(
                JSON_URL.format(username=username),
                headers=HEADERS,
                proxy=proxy_url,
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as r:
                if r.status == 404:
                    return False, None
                if r.status < 400 and r.content_type == "application/json":
                    data = await r.json()
                    user = data.get("graphql", {}).get("user")
                    if user and user.get("username"):
                        return True, user.get("edge_followed_by", {}).get("count")
        except Exception as e:
            print(f"⚠️ JSON check error for {username}: {e}")

        # ── 2) HTML fallback ──────────────────────────────────────────────
        try:
            async with session.get(
                HTML_URL.format(username=username),
                headers=HEADERS,
                proxy=proxy_url,
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as r:
                html = await r.text()
                if "Sorry, this page isn't available" in html:
                    return False, None
                m = re.search(r'"edge_followed_by":\{"count":(\d+)', html)
                if m:
                    return True, int(m.group(1))
                m2 = re.search(r'property="og:description" content="([^"]+)"', html)
                if m2:
                    return True, parse_human_number(m2.group(1).split(" ", 1)[0])
        except Exception as e:
            print(f"⚠️ HTML check error for {username}: {e}")

    # Nothing conclusive — treat as still banned (don't fire)
    return False, None


async def check_instagram_account(username: str, proxy_url: str, timeout: int = 15, mode: str = "mobile") -> dict:
    """
    Wrapper that converts _raw_check output to dict format used by bot.py
    """
    try:
        active, followers = await _raw_check(username, proxy_url, timeout)
        status = "active" if active else "banned"
        return {"status": status, "username": username, "followers": followers, "http_code": None}
    except asyncio.TimeoutError:
        return {"status": "error", "username": username, "error": "Timeout", "http_code": None}
    except Exception as e:
        return {"status": "error", "username": username, "error": str(e), "http_code": None}
