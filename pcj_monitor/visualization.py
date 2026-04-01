from __future__ import annotations

import unicodedata
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from .models import RelevantNews

# ─────────────────────────────────────────────
#  Termos hídricos usados para score de contexto
# ─────────────────────────────────────────────
_HYDRO_TERMS = {
    "água", "agua", "hídrico", "hidrico", "reservatório", "reservatorio",
    "barragem", "rio", "represa", "manancial", "abastecimento", "saneamento",
    "chuva", "enchente", "alagamento", "seca", "estiagem", "poluição",
    "contaminação", "vazão", "vazamento", "afluente", "bacia", "hidrologia",
}


def _normalize(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


# ─────────────────────────────────────────────
#  Score de Relevância PCJ
# ─────────────────────────────────────────────

def compute_pcj_score(news: RelevantNews) -> tuple[int, list[str]]:
    """
    Calcula um score de relevância PCJ (0–20+) e lista alertas de possível
    falso positivo.

    Critérios:
      - Entidade PCJ detectada (keywords_a): +3 por entidade
      - Evento/problema hídrico (keywords_b): +2 por evento
      - Município PCJ identificado: +2
      - Bônus de classificação Alta/Média/Baixa: +3/+2/+1
      - Termos hídricos no resumo: +1 por termo único (máx. 5)
    """
    cls_bonus = {"Alta": 3, "Média": 2, "Baixa": 1}.get(news.classificacao, 0)
    entidades = [e for e in news.entidades_locais if e.strip()]
    eventos = [e for e in news.eventos_problemas if e.strip()]
    municipio_bonus = 2 if news.municipio else 0

    resumo_norm = _normalize(news.resumo)
    hydro_hits = sum(1 for t in _HYDRO_TERMS if _normalize(t) in resumo_norm)

    score = len(entidades) * 3 + len(eventos) * 2 + municipio_bonus + cls_bonus + min(hydro_hits, 5)

    flags: list[str] = []
    # Falso positivo: apenas município + 1 evento genérico ("chuva"), sem entidade PCJ
    if not entidades and len(eventos) <= 1 and news.classificacao in ("Média", "Baixa"):
        flags.append("Possível falso positivo: sem entidades PCJ específicas")
    if eventos == ["chuva"] and not entidades:
        flags.append("Alerta: match apenas por 'chuva' sem contexto hídrico PCJ")
    if eventos == ["vazamento"] and not entidades:
        flags.append("Alerta: match apenas por 'vazamento' — verificar contexto")

    return score, flags


# ─────────────────────────────────────────────
#  Geração do Dashboard HTML
# ─────────────────────────────────────────────

def generate_html_dashboard(
    news_list: List[RelevantNews],
    topic_summary: dict,
    source_stats: List[dict],
    generated_at: datetime,
    output_path: Path,
    bertopic_model: Optional[object] = None,
) -> None:
    """
    Gera um dashboard HTML auto-contido com gráficos Plotly e estatísticas.
    Se Plotly não estiver disponível, a função retorna sem erro.
    """
    try:
        import plotly.graph_objects as go
        import plotly.express as px
        from plotly.subplots import make_subplots
    except ImportError:
        return

    if not news_list:
        return

    # ── Dados base ────────────────────────────────────────────────
    scores_and_flags = [compute_pcj_score(n) for n in news_list]
    scores = [s for s, _ in scores_and_flags]
    flags_per_news = [f for _, f in scores_and_flags]

    cls_counts = Counter(n.classificacao for n in news_list)
    municipio_counts = Counter(n.municipio or "Não identificado" for n in news_list)

    # Frequência de palavras-chave individuais
    kw_counter: Counter = Counter()
    for n in news_list:
        for kw in n.palavras_chave_detectadas:
            if kw.strip():
                kw_counter[kw.strip()] += 1

    # Fontes com mais notícias relevantes
    fonte_counts = Counter(n.fonte for n in news_list)

    # ── 1. Distribuição de Criticidade (pizza) ─────────────────────
    colors_cls = {"Alta": "#e74c3c", "Média": "#f39c12", "Baixa": "#3498db"}
    fig_cls = go.Figure(
        go.Pie(
            labels=list(cls_counts.keys()),
            values=list(cls_counts.values()),
            marker_colors=[colors_cls.get(k, "#95a5a6") for k in cls_counts.keys()],
            hole=0.4,
            textinfo="label+percent+value",
        )
    )
    fig_cls.update_layout(
        title="Distribuição de Criticidade",
        showlegend=True,
        height=400,
        margin=dict(t=50, b=20, l=20, r=20),
    )

    # ── 2. Municípios mais citados (barras horizontais) ─────────────
    top_municipios = municipio_counts.most_common(15)
    mun_names = [m for m, _ in top_municipios]
    mun_vals = [c for _, c in top_municipios]
    fig_mun = go.Figure(
        go.Bar(
            x=mun_vals,
            y=mun_names,
            orientation="h",
            marker_color="#2ecc71",
            text=mun_vals,
            textposition="outside",
        )
    )
    fig_mun.update_layout(
        title="Municípios PCJ Mais Citados",
        xaxis_title="Número de notícias",
        height=max(350, len(top_municipios) * 28),
        margin=dict(t=50, b=30, l=160, r=60),
        yaxis=dict(autorange="reversed"),
    )

    # ── 3. Palavras-chave mais frequentes ──────────────────────────
    top_kw = kw_counter.most_common(20)
    kw_labels = [k for k, _ in top_kw]
    kw_vals = [v for _, v in top_kw]
    # Colore keywords_a (entidades) diferente de keywords_b (eventos)
    fig_kw = go.Figure(
        go.Bar(
            x=kw_labels,
            y=kw_vals,
            marker_color="#9b59b6",
            text=kw_vals,
            textposition="outside",
        )
    )
    fig_kw.update_layout(
        title="Palavras-chave Detectadas — Frequência",
        yaxis_title="Ocorrências",
        height=400,
        margin=dict(t=50, b=100, l=40, r=20),
        xaxis_tickangle=-35,
    )

    # ── 4. Fontes com mais notícias ────────────────────────────────
    top_fontes = fonte_counts.most_common(15)
    fonte_names = [f for f, _ in top_fontes]
    fonte_vals = [c for _, c in top_fontes]
    fig_fontes = go.Figure(
        go.Bar(
            x=fonte_vals,
            y=fonte_names,
            orientation="h",
            marker_color="#1abc9c",
            text=fonte_vals,
            textposition="outside",
        )
    )
    fig_fontes.update_layout(
        title="Fontes de Notícias — Relevantes por Fonte",
        xaxis_title="Notícias relevantes",
        height=max(350, len(top_fontes) * 28),
        margin=dict(t=50, b=30, l=200, r=60),
        yaxis=dict(autorange="reversed"),
    )

    # ── 5. Score de Relevância PCJ por notícia ─────────────────────
    sorted_idx = sorted(range(len(news_list)), key=lambda i: scores[i], reverse=True)
    s_titles = [news_list[i].titulo[:60] + ("…" if len(news_list[i].titulo) > 60 else "") for i in sorted_idx]
    s_scores = [scores[i] for i in sorted_idx]
    s_cls = [news_list[i].classificacao for i in sorted_idx]
    s_flags = ["; ".join(flags_per_news[i]) if flags_per_news[i] else "OK" for i in sorted_idx]
    s_colors = [colors_cls.get(c, "#95a5a6") for c in s_cls]

    fig_score = go.Figure(
        go.Bar(
            x=s_scores,
            y=s_titles,
            orientation="h",
            marker_color=s_colors,
            text=[f"{sc} pts" for sc in s_scores],
            textposition="outside",
            customdata=s_flags,
            hovertemplate="<b>%{y}</b><br>Score: %{x}<br>Status: %{customdata}<extra></extra>",
        )
    )
    fig_score.update_layout(
        title="Score de Relevância PCJ por Notícia (vermelho=Alta, laranja=Média, azul=Baixa)",
        xaxis_title="Score PCJ",
        height=max(400, len(news_list) * 28),
        margin=dict(t=60, b=30, l=400, r=80),
        yaxis=dict(autorange="reversed"),
    )

    # ── 6. Tópicos BERTopic ────────────────────────────────────────
    bertopic_html_parts: list[str] = []

    if topic_summary.get("total_topics", 0) > 0:
        topic_ids = [t["topic_id"] for t in topic_summary["topics"]]
        topic_counts = [t["count"] for t in topic_summary["topics"]]
        topic_names = [t["name"] for t in topic_summary["topics"]]

        fig_topics = go.Figure(
            go.Bar(
                x=topic_ids,
                y=topic_counts,
                text=topic_names,
                textposition="outside",
                marker_color="#e67e22",
                hovertemplate="<b>Tópico %{x}</b><br>%{text}<br>Documentos: %{y}<extra></extra>",
            )
        )
        fig_topics.update_layout(
            title="Distribuição de Tópicos BERTopic",
            xaxis_title="ID do Tópico",
            yaxis_title="Número de documentos",
            height=400,
            margin=dict(t=50, b=40, l=40, r=20),
        )
        bertopic_html_parts.append(
            _section("Distribuição de Tópicos BERTopic", fig_topics.to_html(full_html=False, include_plotlyjs=False))
        )

        # Visualizações nativas BERTopic (se modelo disponível)
        if bertopic_model is not None:
            try:
                fig_bar = bertopic_model.visualize_barchart(top_n_topics=min(8, len(topic_ids)))
                bertopic_html_parts.append(
                    _section("Palavras-chave por Tópico (BERTopic)", fig_bar.to_html(full_html=False, include_plotlyjs=False))
                )
            except Exception:
                pass

            try:
                if len(topic_ids) >= 2:
                    fig_heatmap = bertopic_model.visualize_heatmap()
                    bertopic_html_parts.append(
                        _section("Similaridade entre Tópicos", fig_heatmap.to_html(full_html=False, include_plotlyjs=False))
                    )
            except Exception:
                pass

    # Distribuição de tópicos por notícia (incluindo -1 outliers)
    topic_per_news = Counter(n.topico for n in news_list)
    fig_topic_dist = go.Figure(
        go.Bar(
            x=[f"Tópico {k}" if k != -1 else "Outlier (-1)" for k in sorted(topic_per_news.keys())],
            y=[topic_per_news[k] for k in sorted(topic_per_news.keys())],
            marker_color=["#95a5a6" if k == -1 else "#e67e22" for k in sorted(topic_per_news.keys())],
        )
    )
    fig_topic_dist.update_layout(
        title="Notícias por Tópico BERTopic (cinza = outliers sem tópico definido)",
        yaxis_title="Notícias",
        height=350,
        margin=dict(t=50, b=40, l=40, r=20),
    )
    bertopic_html_parts.append(
        _section("Notícias por Tópico", fig_topic_dist.to_html(full_html=False, include_plotlyjs=False))
    )

    # ── 7. Tabela de falsos positivos ─────────────────────────────
    fp_rows = [
        (news_list[i].titulo, news_list[i].classificacao, scores[i], "; ".join(flags_per_news[i]))
        for i in range(len(news_list))
        if flags_per_news[i]
    ]

    # ── Montar HTML final ─────────────────────────────────────────
    stats_cards = _stats_cards(news_list, cls_counts, scores)
    fp_table = _fp_table(fp_rows)
    keywords_table = _keywords_table(topic_summary)

    sections = [
        _section("Criticidade das Notícias", fig_cls.to_html(full_html=False, include_plotlyjs=False)),
        _section("Municípios PCJ Mais Citados", fig_mun.to_html(full_html=False, include_plotlyjs=False)),
        _section("Palavras-chave Detectadas", fig_kw.to_html(full_html=False, include_plotlyjs=False)),
        _section("Fontes com Mais Notícias Relevantes", fig_fontes.to_html(full_html=False, include_plotlyjs=False)),
        _section("Score de Relevância PCJ por Notícia", fig_score.to_html(full_html=False, include_plotlyjs=False)),
    ] + bertopic_html_parts + [fp_table, keywords_table]

    html = _html_template(
        generated_at=generated_at,
        stats_cards=stats_cards,
        sections=sections,
    )
    output_path.write_text(html, encoding="utf-8")


# ─────────────────────────────────────────────
#  Helpers de template HTML
# ─────────────────────────────────────────────

def _stats_cards(news_list: List[RelevantNews], cls_counts: Counter, scores: list[int]) -> str:
    total = len(news_list)
    avg_score = round(sum(scores) / total, 1) if scores else 0
    n_municipios = len({n.municipio for n in news_list if n.municipio})
    n_fontes = len({n.fonte for n in news_list})
    cards = [
        ("Total de Notícias", str(total), "#3498db"),
        ("Alta Criticidade", str(cls_counts.get("Alta", 0)), "#e74c3c"),
        ("Média Criticidade", str(cls_counts.get("Média", 0)), "#f39c12"),
        ("Baixa Criticidade", str(cls_counts.get("Baixa", 0)), "#2ecc71"),
        ("Score Médio PCJ", str(avg_score), "#9b59b6"),
        ("Municípios PCJ", str(n_municipios), "#1abc9c"),
        ("Fontes Monitoradas", str(n_fontes), "#e67e22"),
    ]
    items = "".join(
        f'<div class="card" style="border-top:4px solid {color}">'
        f'<div class="card-value">{val}</div>'
        f'<div class="card-label">{label}</div>'
        f"</div>"
        for label, val, color in cards
    )
    return f'<div class="cards">{items}</div>'


def _section(title: str, content: str) -> str:
    return (
        f'<section class="chart-section">'
        f"<h2>{title}</h2>"
        f'<div class="chart-body">{content}</div>'
        f"</section>"
    )


def _fp_table(rows: list[tuple]) -> str:
    if not rows:
        return _section(
            "Verificação de Contexto PCJ — Alertas de Falso Positivo",
            '<p class="ok-msg">✓ Nenhum alerta de falso positivo detectado.</p>',
        )
    header = "<tr><th>Título</th><th>Classificação</th><th>Score</th><th>Alerta</th></tr>"
    body = "".join(
        f"<tr><td>{title[:80]}</td><td>{cls}</td><td>{score}</td><td class='alert-cell'>{alert}</td></tr>"
        for title, cls, score, alert in rows
    )
    return _section(
        "Verificação de Contexto PCJ — Alertas de Falso Positivo",
        f'<p>Notícias que podem não ter relação real com a gestão hídrica PCJ:</p>'
        f'<div class="table-wrap"><table class="data-table"><thead>{header}</thead><tbody>{body}</tbody></table></div>',
    )


def _keywords_table(topic_summary: dict) -> str:
    if not topic_summary.get("topics"):
        return ""
    rows = "".join(
        f"<tr><td>Tópico {t['topic_id']}</td><td>{t['name']}</td><td>{t['count']}</td>"
        f"<td>{', '.join(t['representation'][:8])}</td></tr>"
        for t in topic_summary["topics"]
    )
    header = "<tr><th>ID</th><th>Nome</th><th>Docs</th><th>Palavras Principais</th></tr>"
    return _section(
        "Detalhamento dos Tópicos BERTopic",
        f'<div class="table-wrap"><table class="data-table"><thead>{header}</thead><tbody>{rows}</tbody></table></div>',
    )


def _html_template(generated_at: datetime, stats_cards: str, sections: list[str]) -> str:
    ts = generated_at.strftime("%d/%m/%Y %H:%M:%S UTC")
    sections_html = "\n".join(sections)
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Dashboard PCJ — Análise de Notícias Hídricas</title>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js" charset="utf-8"></script>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:'Segoe UI',Arial,sans-serif;background:#f4f6f9;color:#2c3e50}}
  header{{background:linear-gradient(135deg,#1a5276,#2980b9);color:#fff;padding:24px 32px}}
  header h1{{font-size:1.6rem;font-weight:700;margin-bottom:4px}}
  header p{{font-size:.85rem;opacity:.85}}
  .cards{{display:flex;flex-wrap:wrap;gap:14px;padding:24px 32px}}
  .card{{background:#fff;border-radius:8px;padding:18px 22px;min-width:140px;flex:1;
         box-shadow:0 2px 8px rgba(0,0,0,.08)}}
  .card-value{{font-size:2rem;font-weight:700;line-height:1}}
  .card-label{{font-size:.78rem;color:#7f8c8d;margin-top:6px;text-transform:uppercase;letter-spacing:.05em}}
  main{{padding:0 32px 40px}}
  .chart-section{{background:#fff;border-radius:10px;margin-bottom:24px;
                  box-shadow:0 2px 8px rgba(0,0,0,.08);overflow:hidden}}
  .chart-section h2{{font-size:1rem;font-weight:600;padding:16px 20px;
                     border-bottom:1px solid #eaecef;background:#fafbfc}}
  .chart-body{{padding:12px 8px}}
  .table-wrap{{overflow-x:auto;padding:0 12px 12px}}
  .data-table{{width:100%;border-collapse:collapse;font-size:.82rem}}
  .data-table th{{background:#2980b9;color:#fff;padding:8px 12px;text-align:left}}
  .data-table td{{padding:7px 12px;border-bottom:1px solid #eaecef}}
  .data-table tr:hover td{{background:#f0f7ff}}
  .alert-cell{{color:#c0392b;font-size:.78rem}}
  .ok-msg{{padding:16px 20px;color:#27ae60;font-weight:600}}
  footer{{text-align:center;padding:20px;font-size:.75rem;color:#95a5a6}}
</style>
</head>
<body>
<header>
  <h1>Dashboard de Notícias Hídricas — Bacias PCJ</h1>
  <p>Gerado em {ts} &nbsp;|&nbsp; Análise BERTopic + Relevância PCJ</p>
</header>
{stats_cards}
<main>
{sections_html}
</main>
<footer>Monitor PCJ &mdash; Análise automatizada com BERTopic &amp; Plotly</footer>
</body>
</html>"""
