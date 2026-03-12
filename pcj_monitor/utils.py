from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from urllib.parse import urlparse


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self._chunks.append(text)

    def get_text(self) -> str:
        return " ".join(self._chunks)


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = re.sub(r"[^\w\s/-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def clean_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def text_from_html(html: str) -> str:
    parser = TextExtractor()
    parser.feed(html)
    return parser.get_text()


def canonical_url(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")


def parse_date(raw: str | None, months_pt: dict[str, int]) -> datetime | None:
    if not raw:
        return None
    raw = raw.strip()
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        pass
    try:
        dt = parsedate_to_datetime(raw)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError, IndexError):
        pass

    normalized = normalize_text(raw).replace(" de ", " ")
    match = re.search(r"(\d{1,2})\s+([a-zç]+)\s+(\d{4})", normalized)
    if match:
        day = int(match.group(1))
        month = months_pt.get(match.group(2))
        year = int(match.group(3))
        if month:
            return datetime(year, month, day, tzinfo=timezone.utc)

    match = re.search(r"(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})", raw)
    if match:
        day, month, year = map(int, match.groups())
        if year < 100:
            year += 2000
        return datetime(year, month, day, tzinfo=timezone.utc)
    return None


def is_recent(date_str: str | None, days: int, months_pt: dict[str, int]) -> bool:
    dt = parse_date(date_str, months_pt)
    if not dt:
        return True
    now = datetime.now(timezone.utc)
    return dt >= now - timedelta(days=days)


def summarize_text(text: str, max_sentences: int = 3) -> str:
    cleaned = clean_spaces(text)
    if not cleaned:
        return "Resumo não disponível."
    sentences = re.split(r"(?<=[.!?])\s+", cleaned)
    picked: list[str] = []
    for sentence in sentences:
        sentence = clean_spaces(sentence)
        if len(sentence) < 50:
            continue
        picked.append(sentence)
        if len(picked) == max_sentences:
            break
    if not picked:
        picked = [cleaned[:360].rstrip() + ("..." if len(cleaned) > 360 else "")]
    return "\n".join(picked)

