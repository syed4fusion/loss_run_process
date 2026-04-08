from __future__ import annotations

from app.config import settings
from app.pipeline.graph import build_graph

_GRAPH = None


def set_graph(graph) -> None:
    global _GRAPH
    _GRAPH = graph


def get_graph():
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_graph(settings.DATABASE_URL)
    return _GRAPH
