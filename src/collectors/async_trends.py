"""
Async Google Trends Collector

Asynchronous version of trends collection using aiohttp for RSS/API fetching.
"""

import asyncio
from typing import List, Dict, Any
from datetime import datetime, timezone
import structlog

from src.collectors.async_base import fetch_url
from src.config import settings

logger = structlog.get_logger()

# Google Trends RSS feed
TRENDS_RSS_URL = "https://trends.google.com/trending/rss?geo=US"

# Cache for trends data
_trends_cache: Dict[str, Any] = {
    "data": None,
    "timestamp": None,
    "ttl": 3600  # Cache for 1 hour
}


async def get_trending_topics_async() -> List[str]:
    """
    Async version of get_trending_topics.
    
    Uses RSS feed as primary method with caching.
    """
    logger.info("async_trends_collection_started")
    
    # Check cache first
    if _is_cache_valid():
        logger.debug("async_trends_cache_hit")
        return _trends_cache["data"]
    
    # Try RSS feed
    trending = await _fetch_trends_from_rss()
    
    if trending:
        _trends_cache["data"] = trending
        _trends_cache["timestamp"] = datetime.now(timezone.utc)
        logger.info("async_trends_collection_complete", count=len(trending))
        return trending
    
    # Return cached data if available
    if _trends_cache["data"]:
        logger.debug("async_trends_using_stale_cache")
        return _trends_cache["data"]
    
    logger.warning("async_trends_collection_failed")
    return []


async def _fetch_trends_from_rss() -> List[str]:
    """Fetch trending topics from Google Trends RSS feed."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }
        
        response_text = await fetch_url(TRENDS_RSS_URL, headers=headers)
        
        if not response_text:
            return None
        
        # Parse RSS XML
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response_text, 'xml')
        items = soup.find_all('item')
        
        trending = []
        for item in items[:20]:
            title = item.find('title')
            if title:
                trending.append(title.text.strip())
        
        if trending:
            logger.debug("async_trends_rss_success", count=len(trending))
            return trending
            
    except Exception as e:
        logger.debug("async_trends_rss_error", error=str(e))
    
    return None


def _is_cache_valid() -> bool:
    """Check if cached trends data is still valid."""
    if not _trends_cache["data"] or not _trends_cache["timestamp"]:
        return False
    
    age = (datetime.now(timezone.utc) - _trends_cache["timestamp"]).total_seconds()
    return age < _trends_cache["ttl"]


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    
    async def test():
        topics = await get_trending_topics_async()
        print(f"Got {len(topics)} topics: {topics[:5]}")
    
    asyncio.run(test())
