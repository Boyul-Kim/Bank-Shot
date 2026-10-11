"""Polite HTTP fetching: robots.txt check, descriptive User-Agent, per-host rate limit, timeouts."""
import threading
import time
from urllib import robotparser
from urllib.parse import urlparse

import requests

USER_AGENT = "AuctionBoard/1.0 (personal fantasy draft prep tool; runs locally; one request per page)"
MIN_GAP_SECONDS = 5.0
TIMEOUT = 20

_last_hit: dict[str, float] = {}
_robots: dict[str, robotparser.RobotFileParser] = {}
_lock = threading.Lock()


class FetchError(Exception):
    pass


def _allowed(url: str) -> bool:
    host = urlparse(url)
    base = f"{host.scheme}://{host.netloc}"
    rp = _robots.get(base)
    if rp is None:
        rp = robotparser.RobotFileParser()
        try:
            resp = requests.get(base + "/robots.txt", headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
            rp.parse(resp.text.splitlines() if resp.status_code == 200 else [])
        except requests.RequestException:
            rp.parse([])  # robots.txt unreachable: treat as no restrictions, the page request will still be rate limited
        _robots[base] = rp
    return rp.can_fetch(USER_AGENT, url)


def fetch(url: str) -> str:
    if not url.startswith("https://"):
        raise FetchError("Source URLs must start with https://")
    if not _allowed(url):
        raise FetchError("The site's robots.txt doesn't allow automated access to this page. Import a CSV instead.")
    host = urlparse(url).netloc
    with _lock:
        wait = MIN_GAP_SECONDS - (time.time() - _last_hit.get(host, 0))
        if wait > 0:
            time.sleep(wait)
        _last_hit[host] = time.time()
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"}, timeout=TIMEOUT)
    except requests.RequestException as e:
        raise FetchError(f"Couldn't reach {host}: {e.__class__.__name__}.") from e
    if resp.status_code != 200:
        raise FetchError(f"{host} answered HTTP {resp.status_code}.")
    return resp.text
