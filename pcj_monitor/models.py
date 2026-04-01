from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Article:
    title: str
    date: str | None
    source: str
    text: str
    link: str


@dataclass
class RelevantNews:
    data: str
    municipio: str | None
    fonte: str
    titulo: str
    link: str
    resumo: str
    palavras_chave_detectadas: list[str]
    classificacao: str
    entidades_locais: list[str] = field(default_factory=list)
    eventos_problemas: list[str] = field(default_factory=list)
    topico: int = -1  # Adicionado para BERTopic

