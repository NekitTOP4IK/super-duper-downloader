import re
from urllib.parse import urlsplit

_URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
_TRAILING = ".,;:!?)]}>"


def extract_urls(text: str) -> list[str]:
    found: dict[str, None] = {}
    for match in _URL_RE.finditer(text):
        url = match.group(0).rstrip(_TRAILING)
        if urlsplit(url).netloc:
            found.setdefault(url, None)
    return list(found)
