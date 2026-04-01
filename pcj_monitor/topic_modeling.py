from __future__ import annotations

import pandas as pd
from bertopic import BERTopic
from typing import List, Optional, Tuple
from .models import RelevantNews


def apply_bertopic_to_news(
    news_list: List[RelevantNews],
    language: str = "portuguese",
) -> Tuple[List[RelevantNews], dict, Optional[BERTopic]]:
    """
    Aplica BERTopic aos resumos das notícias para identificar tópicos.
    Atualiza o campo 'topico' de cada RelevantNews.
    Retorna a lista atualizada, um resumo dos tópicos e o modelo treinado.
    """
    if not news_list:
        return news_list, {"total_topics": 0, "topics": []}, None

    docs = [news.resumo for news in news_list]

    # Mínimo de documentos para BERTopic fazer sentido
    if len(docs) < 5:
        return news_list, {"total_topics": 0, "topics": []}, None

    try:
        model = BERTopic(language=language, calculate_probabilities=False, verbose=False)
        topics, _ = model.fit_transform(docs)

        for news, topic in zip(news_list, topics):
            news.topico = topic

        summary = get_topic_summary(model)
        return news_list, summary, model

    except Exception:
        # Fallback se BERTopic falhar (poucos docs, dependência faltando, etc.)
        return news_list, {"total_topics": 0, "topics": []}, None


def get_topic_summary(model: BERTopic) -> dict:
    """Gera um resumo dos tópicos encontrados."""
    topic_info = model.get_topic_info()
    summary: dict = {
        "total_topics": len(topic_info) - 1,  # Exclui tópico -1 (outliers)
        "topics": [],
    }

    for _, row in topic_info.iterrows():
        if row["Topic"] != -1:
            summary["topics"].append(
                {
                    "topic_id": int(row["Topic"]),
                    "count": int(row["Count"]),
                    "name": str(row["Name"]),
                    "representation": list(row["Representation"]),
                }
            )

    return summary
