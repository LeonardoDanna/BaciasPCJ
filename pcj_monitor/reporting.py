from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Iterable

try:
    from docx import Document
except ImportError:
    Document = None

try:
    from docx.shared import Pt
except ImportError:
    Pt = None

from .analyzer import build_daily_summary, sort_key
from .config import MonitorConfig
from .models import RelevantNews


def add_bold_label(paragraph, label: str, value: str) -> None:
    run = paragraph.add_run(label)
    run.bold = True
    paragraph.add_run(value)


def add_highlighted_text(paragraph, text: str, terms: Iterable[str]) -> None:
    filtered_terms = sorted({term.strip() for term in terms if term and term.strip()}, key=len, reverse=True)
    if not filtered_terms:
        paragraph.add_run(text)
        return

    pattern = re.compile("(" + "|".join(re.escape(term) for term in filtered_terms) + ")", re.IGNORECASE)
    last = 0
    for match in pattern.finditer(text):
        start, end = match.span()
        if start > last:
            paragraph.add_run(text[last:start])
        run = paragraph.add_run(text[start:end])
        run.bold = True
        last = end
    if last < len(text):
        paragraph.add_run(text[last:])


def generate_docx_report(
    items: list[RelevantNews],
    generated_at: datetime,
    output_path: Path,
    config: MonitorConfig,
    source_stats: list[dict[str, object]],
) -> None:
    if Document is None:
        raise RuntimeError(
            "A biblioteca 'python-docx' nao esta instalada. Instale com: pip3 install python-docx"
        )

    document = Document()
    if Pt is not None:
        styles = document.styles
        styles["Normal"].font.name = "Arial"
        styles["Normal"].font.size = Pt(10)
        styles["Heading 1"].font.name = "Arial"
        styles["Heading 2"].font.name = "Arial"
        styles["Title"].font.name = "Arial"

    document.add_heading("Relatorio Diario de Noticias Hidricas - Bacias PCJ", level=0)
    meta = document.add_paragraph()
    add_bold_label(meta, "Gerado em: ", generated_at.strftime("%d/%m/%Y %H:%M:%S UTC"))

    document.add_heading("Resumo Consolidado", level=1)
    for line in build_daily_summary(items, config).splitlines():
        paragraph = document.add_paragraph(style="List Bullet")
        add_highlighted_text(paragraph, line, {"Alta", "Media", "Baixa"} | config.keywords_b | config.keywords_a)

    document.add_heading("Execucao", level=1)
    success_count = sum(1 for stat in source_stats if str(stat.get("status", "")).startswith(("feed", "portal", "artigo")))
    exec_paragraph = document.add_paragraph(style="List Bullet")
    add_bold_label(exec_paragraph, "Fontes processadas: ", f"{success_count}/{len(source_stats)}")
    for stat in source_stats:
        paragraph = document.add_paragraph(style="List Bullet")
        add_bold_label(
            paragraph,
            f"{stat['url']}: ",
            f"status={stat.get('status')} | noticias={stat.get('articles_found', 0)}",
        )

    grouped: dict[str, list[RelevantNews]] = defaultdict(list)
    for item in sorted(items, key=lambda news: sort_key(news, config)):
        grouped[item.municipio or "Municipio nao identificado"].append(item)

    for municipality, news in grouped.items():
        document.add_heading(municipality, level=1)
        for item in news:
            document.add_heading(item.titulo, level=2)
            p = document.add_paragraph()
            add_bold_label(p, "Data: ", item.data)
            p = document.add_paragraph()
            add_bold_label(p, "Municipio: ", item.municipio or "Nao identificado")
            p = document.add_paragraph()
            add_bold_label(p, "Fonte: ", item.fonte)
            p = document.add_paragraph()
            add_bold_label(p, "Link: ", item.link)
            p = document.add_paragraph()
            add_bold_label(p, "Criticidade: ", item.classificacao)
            p = document.add_paragraph()
            add_bold_label(p, "Palavras-chave detectadas: ", ", ".join(item.palavras_chave_detectadas))
            p = document.add_paragraph()
            label = p.add_run("Resumo: ")
            label.bold = True
            for line in item.resumo.splitlines():
                paragraph = document.add_paragraph(style="List Bullet")
                add_highlighted_text(paragraph, line, item.palavras_chave_detectadas)
            document.add_paragraph("")

    document.save(output_path)


def build_json_payload(
    items: list[RelevantNews],
    generated_at: datetime,
    config: MonitorConfig,
    source_stats: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "generated_at": generated_at.isoformat(),
        "summary": build_daily_summary(items, config),
        "total_relevant_news": len(items),
        "source_stats": source_stats,
        "news": [asdict(item) for item in items],
    }


def write_json_report(output_path: Path, payload: dict[str, object]) -> None:
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

