from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class MonitorConfig:
    user_agent: str
    default_timeout: int
    keywords_a: set[str]
    keywords_b: set[str]
    municipalities_pcj: set[str]
    hydro_context_terms: set[str]
    article_hints: tuple[str, ...]
    months_pt: dict[str, int]


def _default_config_path() -> Path:
    return Path(__file__).resolve().parent / "defaults.json"


def load_monitor_config(config_file: str | None = None) -> MonitorConfig:
    config_path = Path(config_file) if config_file else _default_config_path()
    data = json.loads(config_path.read_text(encoding="utf-8"))
    return MonitorConfig(
        user_agent=data["user_agent"],
        default_timeout=int(data["default_timeout"]),
        keywords_a=set(data["keywords_a"]),
        keywords_b=set(data["keywords_b"]),
        municipalities_pcj=set(data["municipalities_pcj"]),
        hydro_context_terms=set(data["hydro_context_terms"]),
        article_hints=tuple(data["article_hints"]),
        months_pt={str(key): int(value) for key, value in data["months_pt"].items()},
    )


def load_urls(path: Path) -> list[str]:
    raw = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        data = json.loads(raw)
        if not isinstance(data, list):
            raise ValueError("O arquivo JSON deve conter uma lista de URLs.")
        return [str(item).strip() for item in data if str(item).strip()]
    return [line.strip() for line in raw.splitlines() if line.strip() and not line.strip().startswith("#")]

