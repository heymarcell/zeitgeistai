"""Collectors package - External signal acquisition."""

# Sync collectors
from src.collectors.gdelt import collect_gdelt_articles
from src.collectors.bluesky import collect_bluesky_posts
from src.collectors.mastodon import collect_mastodon_posts
from src.collectors.trends import get_trending_topics

# Async collectors
from src.collectors.async_gdelt import collect_gdelt_articles_async
from src.collectors.async_bluesky import collect_bluesky_posts_async
from src.collectors.async_mastodon import collect_mastodon_posts_async
from src.collectors.async_trends import get_trending_topics_async

__all__ = [
    # Sync
    "collect_gdelt_articles",
    "collect_bluesky_posts",
    "collect_mastodon_posts",
    "get_trending_topics",
    # Async
    "collect_gdelt_articles_async",
    "collect_bluesky_posts_async",
    "collect_mastodon_posts_async",
    "get_trending_topics_async",
]
