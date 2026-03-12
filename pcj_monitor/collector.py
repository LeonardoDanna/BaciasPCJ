from __future__ import annotations

import logging
import random
import re
import xml.etree.ElementTree as ET
from html import unescape
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

from .config import MonitorConfig
from .models import Article
from .utils import canonical_url, clean_spaces, is_recent, normalize_text, text_from_html


def fetch_url(url: str, config: MonitorConfig) -> tuple[str, str]:
    request = Request(url, headers={"User-Agent": config.user_agent})
    with urlopen(request, timeout=config.default_timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        body = response.read().decode(charset, errors="replace")
        content_type = response.headers.get("Content-Type", "")
    return body, content_type


def looks_like_feed(url: str, content: str, content_type: str) -> bool:
    if "xml" in content_type or "rss" in content_type or "atom" in content_type:
        return True
    lowered = url.lower()
    if lowered.endswith(".xml") or "rss" in lowered or "feed" in lowered:
        return True
    snippet = content.lstrip()[:80].lower()
    return snippet.startswith("<?xml") or "<rss" in snippet or "<feed" in snippet


def extract_text_blocks(soup: BeautifulSoup) -> str:
    selectors = [
        "article",
        "main",
        "[itemprop='articleBody']",
        ".article-content",
        ".post-content",
        ".entry-content",
        ".news-content",
        ".materia-conteudo",
        ".content",
    ]
    for selector in selectors:
        node = soup.select_one(selector)
        if node:
            texts = [p.get_text(" ", strip=True) for p in node.find_all(["p", "h2", "h3", "li"])]
            merged = " ".join(t for t in texts if t)
            if len(merged) > 300:
                return merged
    paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
    return " ".join(p for p in paragraphs if p)


def parse_html_article(url: str, html: str) -> Article:
    source = urlparse(url).netloc.replace("www.", "")
    if BeautifulSoup:
        soup = BeautifulSoup(html, "html.parser")
        title = (
            (soup.find("meta", property="og:title") or {}).get("content")
            or (soup.find("meta", attrs={"name": "twitter:title"}) or {}).get("content")
            or (soup.find("h1").get_text(" ", strip=True) if soup.find("h1") else "")
            or (soup.title.get_text(" ", strip=True) if soup.title else "")
        )
        date = (
            (soup.find("meta", property="article:published_time") or {}).get("content")
            or (soup.find("meta", attrs={"name": "pubdate"}) or {}).get("content")
            or (soup.find("time").get("datetime") if soup.find("time") and soup.find("time").get("datetime") else "")
            or (soup.find("time").get_text(" ", strip=True) if soup.find("time") else "")
        )
        source = (soup.find("meta", property="og:site_name") or {}).get("content") or source
        text = extract_text_blocks(soup)
        return Article(
            title=clean_spaces(unescape(title)),
            date=clean_spaces(date) or None,
            source=clean_spaces(source),
            text=clean_spaces(unescape(text)),
            link=url,
        )

    title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    title = unescape(title_match.group(1)) if title_match else url
    text = text_from_html(html)
    return Article(title=clean_spaces(title), date=None, source=source, text=clean_spaces(text), link=url)


def parse_feed(url: str, content: str) -> list[Article]:
    articles: list[Article] = []
    root = ET.fromstring(content)
    if root.tag.lower().endswith("rss") or root.find("./channel") is not None:
        channel = root.find("./channel")
        if channel is None:
            return articles
        source = channel.findtext("title") or urlparse(url).netloc
        for item in channel.findall("./item"):
            title = item.findtext("title") or ""
            link = item.findtext("link") or url
            date = item.findtext("pubDate") or item.findtext("{http://purl.org/dc/elements/1.1/}date")
            summary = item.findtext("description") or item.findtext("{http://purl.org/rss/1.0/modules/content/}encoded") or ""
            articles.append(
                Article(
                    title=clean_spaces(unescape(title)),
                    date=clean_spaces(date) or None,
                    source=clean_spaces(source),
                    text=clean_spaces(text_from_html(unescape(summary))),
                    link=clean_spaces(link),
                )
            )
        return articles

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    source = root.findtext("atom:title", default=urlparse(url).netloc, namespaces=ns)
    for entry in root.findall("atom:entry", ns):
        link = url
        link_node = entry.find("atom:link", ns)
        if link_node is not None:
            link = link_node.attrib.get("href", url)
        summary = entry.findtext("atom:summary", default="", namespaces=ns)
        content_text = entry.findtext("atom:content", default="", namespaces=ns)
        articles.append(
            Article(
                title=clean_spaces(entry.findtext("atom:title", default="", namespaces=ns)),
                date=clean_spaces(entry.findtext("atom:updated", default="", namespaces=ns)) or None,
                source=clean_spaces(source),
                text=clean_spaces(text_from_html(unescape(content_text or summary))),
                link=clean_spaces(link),
            )
        )
    return articles


def candidate_links_from_html(base_url: str, html: str, limit: int, config: MonitorConfig) -> list[str]:
    links: list[str] = []
    if BeautifulSoup:
        soup = BeautifulSoup(html, "html.parser")
        for anchor in soup.find_all("a", href=True):
            href = urljoin(base_url, anchor["href"])
            parsed = urlparse(href)
            if parsed.scheme not in {"http", "https"}:
                continue
            if urlparse(base_url).netloc not in parsed.netloc:
                continue
            anchor_text = clean_spaces(anchor.get_text(" ", strip=True))
            normalized = normalize_text(href + " " + anchor_text)
            if any(hint in href.lower() for hint in config.article_hints) or any(
                keyword in normalized for keyword in ("agua", "chuva", "seca", "enchente", "pcj", "cantareira")
            ):
                links.append(href)
    else:
        for match in re.finditer(r'href=["\'](.*?)["\']', html, re.I):
            href = urljoin(base_url, match.group(1))
            if urlparse(base_url).netloc in urlparse(href).netloc:
                links.append(href)

    deduped: list[str] = []
    seen: set[str] = set()
    for link in links:
        key = canonical_url(link)
        if key not in seen:
            seen.add(key)
            deduped.append(link)
        if len(deduped) >= limit:
            break
    return deduped


def choose_urls_for_run(urls: list[str], sample_size: int | None, random_seed: int | None) -> list[str]:
    if sample_size is None or sample_size <= 0 or sample_size >= len(urls):
        return list(urls)
    rng = random.Random(random_seed)
    shuffled = list(urls)
    rng.shuffle(shuffled)
    return shuffled[:sample_size]


def collect_articles(
    monitored_urls: list[str],
    per_html_limit: int,
    recent_days: int,
    config: MonitorConfig,
    logger: logging.Logger,
) -> tuple[list[Article], list[dict[str, object]]]:
    collected: list[Article] = []
    source_stats: list[dict[str, object]] = []
    total = len(monitored_urls)
    for index, monitored_url in enumerate(monitored_urls, start=1):
        logger.info("[%s/%s] analisando fonte: %s", index, total, monitored_url)
        source_stat = {"url": monitored_url, "status": "ok", "articles_found": 0}
        try:
            body, content_type = fetch_url(monitored_url, config)
        except Exception as exc:
            logger.warning("Falha ao acessar %s: %s", monitored_url, exc)
            source_stat["status"] = "erro_acesso"
            source_stat["error"] = str(exc)
            source_stats.append(source_stat)
            continue

        try:
            if looks_like_feed(monitored_url, body, content_type):
                before = len(collected)
                for article in parse_feed(monitored_url, body):
                    if is_recent(article.date, recent_days, config.months_pt):
                        collected.append(article)
                source_stat["articles_found"] = len(collected) - before
                source_stat["status"] = "feed"
                logger.info("[%s/%s] feed processado: +%s noticia(s)", index, total, source_stat["articles_found"])
                source_stats.append(source_stat)
                continue

            if any(hint in monitored_url.lower() for hint in config.article_hints):
                article = parse_html_article(monitored_url, body)
                if is_recent(article.date, recent_days, config.months_pt):
                    collected.append(article)
                    source_stat["articles_found"] = 1
                    source_stat["status"] = "artigo_direto"
                    logger.info("[%s/%s] artigo direto processado: +1 noticia", index, total)
                else:
                    source_stat["status"] = "artigo_antigo"
                    logger.info("[%s/%s] artigo direto ignorado por data", index, total)
                source_stats.append(source_stat)
                continue

            before = len(collected)
            for link in candidate_links_from_html(monitored_url, body, per_html_limit, config):
                try:
                    article_html, _ = fetch_url(link, config)
                    article = parse_html_article(link, article_html)
                    if is_recent(article.date, recent_days, config.months_pt):
                        collected.append(article)
                except Exception as exc:
                    logger.warning("Falha ao processar artigo %s: %s", link, exc)
            source_stat["articles_found"] = len(collected) - before
            source_stat["status"] = "portal"
            logger.info("[%s/%s] portal processado: +%s noticia(s)", index, total, source_stat["articles_found"])
        except Exception as exc:
            logger.warning("Falha ao interpretar %s: %s", monitored_url, exc)
            source_stat["status"] = "erro_parser"
            source_stat["error"] = str(exc)
        source_stats.append(source_stat)
    return collected, source_stats

