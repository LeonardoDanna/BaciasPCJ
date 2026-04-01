from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Iterable

from .config import MonitorConfig
from .models import Article, RelevantNews
from .topic_modeling import apply_bertopic_to_news
from .utils import canonical_url, normalize_text, parse_date, summarize_text


def find_matches(text: str, keywords: Iterable[str]) -> list[str]:
    normalized_text = f" {normalize_text(text)} "
    matches: list[str] = []
    for keyword in keywords:
        normalized_keyword = normalize_text(keyword)
        if f" {normalized_keyword} " in normalized_text:
            matches.append(keyword)
    return sorted(set(matches))


def detect_municipality(text: str, config: MonitorConfig) -> str | None:
    matches = find_matches(text, config.municipalities_pcj)
    return matches[0] if matches else None


def classify_relevance(matches_a: list[str], matches_b: list[str], municipality: str | None) -> str | None:
    total_signals = len(matches_a) + len(matches_b) + (1 if municipality else 0)
    if total_signals < 2:
        return None
    if matches_a and matches_b:
        return "Alta"
    if matches_b and municipality:
        return "Média"
    if matches_a or matches_b or municipality:
        return "Baixa"
    return None


def is_water_context(article: Article, matches_a: list[str], matches_b: list[str], config: MonitorConfig) -> bool:
    combined = " ".join([article.title, article.text])
    normalized = normalize_text(combined)
    hydric_hits = [term for term in config.hydro_context_terms if term in normalized]
    return bool(hydric_hits or matches_b or any(normalize_text(term) in normalized for term in matches_a))


def analyze_article(article: Article, config: MonitorConfig) -> RelevantNews | None:
    combined = " ".join([article.title, article.text])
    matches_a = find_matches(combined, config.keywords_a)
    matches_b = find_matches(combined, config.keywords_b)
    municipality = detect_municipality(combined, config)
    classification = classify_relevance(matches_a, matches_b, municipality)
    if not classification:
        return None
    if not is_water_context(article, matches_a, matches_b, config):
        return None
    keywords = sorted(set(matches_a + matches_b + ([municipality] if municipality else [])))
    return RelevantNews(
        data=article.date or "Data não identificada",
        municipio=municipality,
        fonte=article.source,
        titulo=article.title,
        link=article.link,
        resumo=summarize_text(article.text),
        palavras_chave_detectadas=keywords,
        classificacao=classification,
        entidades_locais=matches_a,
        eventos_problemas=matches_b,
    )


def deduplicate(items: Iterable[RelevantNews]) -> list[RelevantNews]:
    deduped: list[RelevantNews] = []
    seen: set[str] = set()
    for item in items:
        fingerprint = normalize_text(f"{item.titulo}|{canonical_url(item.link)}")
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        deduped.append(item)
    return deduped


def apply_topics_to_news(
    news_list: list[RelevantNews],
) -> tuple[list[RelevantNews], dict, object]:
    """
    Aplica BERTopic às notícias para identificar tópicos.
    Retorna a lista atualizada, o resumo dos tópicos e o modelo treinado.
    """
    return apply_bertopic_to_news(news_list)


def sort_key(item: RelevantNews, config: MonitorConfig) -> tuple[int, datetime, str]:
    priority = {"Alta": 0, "Média": 1, "Baixa": 2}.get(item.classificacao, 3)
    dt = parse_date(item.data, config.months_pt) or datetime(1970, 1, 1, tzinfo=timezone.utc)
    return (priority, -int(dt.timestamp()), item.titulo.lower())


def build_daily_summary(items: list[RelevantNews], config: MonitorConfig) -> str:
    if not items:
        return "Nenhum evento hidrológico relevante identificado no período."
    counts = defaultdict(int)
    municipalities = defaultdict(int)
    for item in items:
        counts[item.classificacao] += 1
        municipalities[item.municipio or "Não identificado"] += 1
    top_municipalities = sorted(municipalities.items(), key=lambda x: (-x[1], x[0]))[:5]
    highlights = sorted(items, key=lambda item: sort_key(item, config))[:5]
    lines = [
        f"Resumo diário: {len(items)} notícia(s) relevante(s) identificada(s).",
        f"Criticidade: Alta={counts['Alta']}, Média={counts['Média']}, Baixa={counts['Baixa']}.",
        "Municípios com mais ocorrências: "
        + ", ".join(f"{name} ({count})" for name, count in top_municipalities),
        "Destaques: "
        + " | ".join(f"{item.titulo} [{item.classificacao}]" for item in highlights),
    ]
    return "\n".join(lines)

