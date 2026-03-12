from __future__ import annotations

import json
import sqlite3
from pathlib import Path


SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS executions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        generated_at TEXT NOT NULL,
        summary TEXT NOT NULL,
        total_relevant_news INTEGER NOT NULL,
        urls_file TEXT,
        output_dir TEXT,
        sample_size INTEGER,
        random_seed INTEGER,
        recent_days INTEGER,
        per_html_limit INTEGER,
        payload_json TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS news (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        execution_id INTEGER NOT NULL,
        data TEXT,
        municipio TEXT,
        fonte TEXT NOT NULL,
        titulo TEXT NOT NULL,
        link TEXT NOT NULL,
        resumo TEXT,
        classificacao TEXT,
        palavras_chave_detectadas TEXT,
        entidades_locais TEXT,
        eventos_problemas TEXT,
        FOREIGN KEY (execution_id) REFERENCES executions(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS source_stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        execution_id INTEGER NOT NULL,
        url TEXT NOT NULL,
        status TEXT,
        articles_found INTEGER DEFAULT 0,
        error TEXT,
        FOREIGN KEY (execution_id) REFERENCES executions(id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_news_execution_id ON news (execution_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_news_link ON news (link)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_source_stats_execution_id ON source_stats (execution_id)
    """,
)


def initialize_database(database_path: Path) -> None:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database_path) as connection:
        for statement in SCHEMA_STATEMENTS:
            connection.execute(statement)
        connection.commit()


def save_execution(
    database_path: Path,
    payload: dict[str, object],
    run_metadata: dict[str, object],
) -> int:
    initialize_database(database_path)
    with sqlite3.connect(database_path) as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO executions (
                generated_at,
                summary,
                total_relevant_news,
                urls_file,
                output_dir,
                sample_size,
                random_seed,
                recent_days,
                per_html_limit,
                payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(payload["generated_at"]),
                str(payload["summary"]),
                int(payload["total_relevant_news"]),
                run_metadata.get("urls_file"),
                run_metadata.get("output_dir"),
                run_metadata.get("sample_size"),
                run_metadata.get("random_seed"),
                run_metadata.get("recent_days"),
                run_metadata.get("per_html_limit"),
                json.dumps(payload, ensure_ascii=False),
            ),
        )
        execution_id = int(cursor.lastrowid)

        for item in payload.get("news", []):
            cursor.execute(
                """
                INSERT INTO news (
                    execution_id,
                    data,
                    municipio,
                    fonte,
                    titulo,
                    link,
                    resumo,
                    classificacao,
                    palavras_chave_detectadas,
                    entidades_locais,
                    eventos_problemas
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    execution_id,
                    item.get("data"),
                    item.get("municipio"),
                    item.get("fonte"),
                    item.get("titulo"),
                    item.get("link"),
                    item.get("resumo"),
                    item.get("classificacao"),
                    json.dumps(item.get("palavras_chave_detectadas", []), ensure_ascii=False),
                    json.dumps(item.get("entidades_locais", []), ensure_ascii=False),
                    json.dumps(item.get("eventos_problemas", []), ensure_ascii=False),
                ),
            )

        for stat in payload.get("source_stats", []):
            cursor.execute(
                """
                INSERT INTO source_stats (
                    execution_id,
                    url,
                    status,
                    articles_found,
                    error
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    execution_id,
                    stat.get("url"),
                    stat.get("status"),
                    int(stat.get("articles_found", 0) or 0),
                    stat.get("error"),
                ),
            )

        connection.commit()
        return execution_id
