from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from .analyzer import analyze_article, apply_topics_to_news, deduplicate, sort_key
from .collector import choose_urls_for_run, collect_articles
from .config import load_monitor_config, load_urls
from .database import save_execution
from .logging_utils import setup_logging
from .reporting import build_json_payload, generate_docx_report, write_csv_report, write_json_report
from .visualization import generate_html_dashboard


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Monitora noticias sobre gestao hidrica nas Bacias PCJ.")
    parser.add_argument("--urls-file", required=True, help="Arquivo .txt ou .json com URLs de portais/RSS.")
    parser.add_argument("--output-dir", default="saida_pcj", help="Diretorio de saida dos relatorios.")
    parser.add_argument("--database-path", default=None, help="Arquivo SQLite para persistir as execucoes. Padrao: <output-dir>/pcj_monitor.db")
    parser.add_argument("--config-file", default=None, help="Arquivo JSON opcional para sobrescrever a configuracao padrao.")
    parser.add_argument("--recent-days", type=int, default=7, help="Janela de recencia em dias.")
    parser.add_argument("--per-html-limit", type=int, default=15, help="Maximo de links a seguir por portal HTML.")
    parser.add_argument("--sample-size", type=int, default=10, help="Quantidade de URLs aleatorias testadas por execucao. Use 0 para rodar todas.")
    parser.add_argument("--random-seed", type=int, default=None, help="Semente opcional para repetir a mesma amostra.")
    return parser.parse_args()


def build_report_paths(output_dir: Path, report_date: str) -> tuple[Path, Path, Path, Path]:
    sequence = 1
    while True:
        suffix = f"{report_date}-{sequence}"
        docx_path = output_dir / f"relatorio_pcj_{suffix}.docx"
        json_path = output_dir / f"relatorio_pcj_{suffix}.json"
        csv_path = output_dir / f"relatorio_pcj_{suffix}.csv"
        html_path = output_dir / f"relatorio_pcj_{suffix}.html"
        if not any(path.exists() for path in (docx_path, json_path, csv_path, html_path)):
            return docx_path, json_path, csv_path, html_path
        sequence += 1


def run() -> int:
    args = parse_args()
    urls_file = Path(args.urls_file)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    database_path = Path(args.database_path) if args.database_path else output_dir / "pcj_monitor.db"

    logger, log_path = setup_logging(output_dir)
    try:
        config = load_monitor_config(args.config_file)
        all_urls = load_urls(urls_file)
        monitored_urls = choose_urls_for_run(all_urls, sample_size=args.sample_size, random_seed=args.random_seed)

        logger.info("Executando teste com %s de %s URL(s) cadastrada(s).", len(monitored_urls), len(all_urls))
        if args.random_seed is not None:
            logger.info("Random seed usada nesta execucao: %s", args.random_seed)

        articles, source_stats = collect_articles(
            monitored_urls=monitored_urls,
            per_html_limit=args.per_html_limit,
            recent_days=args.recent_days,
            config=config,
            logger=logger,
        )

        relevant = deduplicate(filter(None, (analyze_article(article, config) for article in articles)))
        relevant, topic_summary, bertopic_model = apply_topics_to_news(relevant)
        relevant = sorted(relevant, key=lambda item: sort_key(item, config))
        generated_at = datetime.now(timezone.utc)

        report_date = generated_at.strftime("%Y%m%d")
        docx_path, json_path, csv_path, html_path = build_report_paths(output_dir, report_date)

        generate_docx_report(relevant, generated_at, docx_path, config, source_stats, topic_summary)
        payload = build_json_payload(relevant, generated_at, config, source_stats, topic_summary)
        write_json_report(json_path, payload)
        write_csv_report(csv_path, payload)
        generate_html_dashboard(
            news_list=relevant,
            topic_summary=topic_summary,
            source_stats=source_stats,
            generated_at=generated_at,
            output_path=html_path,
            bertopic_model=bertopic_model,
        )
        execution_id = save_execution(
            database_path,
            payload,
            {
                "urls_file": str(urls_file),
                "output_dir": str(output_dir),
                "sample_size": args.sample_size,
                "random_seed": args.random_seed,
                "recent_days": args.recent_days,
                "per_html_limit": args.per_html_limit,
            },
        )
    except Exception:
        logger.exception("Execucao interrompida por erro nao tratado.")
        logger.info("Log da execucao: %s", log_path)
        return 1

    logger.info("Relatorio DOCX: %s", docx_path)
    logger.info("Relatorio JSON: %s", json_path)
    logger.info("Relatorio CSV: %s", csv_path)
    logger.info("Dashboard HTML: %s", html_path)
    logger.info("Banco SQLite: %s", database_path)
    logger.info("Execution ID: %s", execution_id)
    logger.info("Log da execucao: %s", log_path)
    logger.info("%s", payload["summary"])
    return 0
