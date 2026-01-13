"""Processors package - Signal processing and analysis."""

from src.processors.dedup import deduplicate_articles
from src.processors.clustering import cluster_articles
from src.processors.scoring import calculate_virality_scores
from src.processors.story_arc import match_clusters_to_story_arcs, story_arc_registry
from src.processors.contrarian import calculate_narrative_divergence, get_hidden_stories

__all__ = [
    "deduplicate_articles",
    "cluster_articles",
    "calculate_virality_scores",
    "match_clusters_to_story_arcs",
    "story_arc_registry",
    "calculate_narrative_divergence",
    "get_hidden_stories",
]
