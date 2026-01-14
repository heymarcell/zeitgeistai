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

# Google Trends RSS feed base URL
TRENDS_RSS_BASE = "https://trends.google.com/trending/rss"

# Major regions for global coverage (top economies/population)
# US, UK, Germany, France, India, Japan, Brazil, Australia
GLOBAL_REGIONS = ["US", "GB", "DE", "FR", "IN", "JP", "BR", "AU"]

# Cache for trends data
_trends_cache: Dict[str, Any] = {
    "data": None,
    "timestamp": None,
    "ttl": 3600  # Cache for 1 hour
}


async def get_trending_topics_async() -> List[str]:
    """
    Async version of get_trending_topics.
    
    Fetches from multiple regions for global coverage and deduplicates.
    """
    logger.info("async_trends_collection_started")
    
    # Check cache first
    if _is_cache_valid():
        logger.debug("async_trends_cache_hit")
        return _trends_cache["data"]
    
    # Fetch from all regions in parallel
    tasks = [_fetch_trends_from_region(region) for region in GLOBAL_REGIONS]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Combine and deduplicate
    all_topics = []
    seen = set()
    
    for result in results:
        if isinstance(result, list):
            for topic in result:
                topic_lower = topic.lower()
                if topic_lower not in seen:
                    seen.add(topic_lower)
                    all_topics.append(topic)
    
    if all_topics:
        # Limit to top 30 global topics
        trending = all_topics[:30]
        _trends_cache["data"] = trending
        _trends_cache["timestamp"] = datetime.now(timezone.utc)
        logger.info("async_trends_collection_complete", count=len(trending), regions=len(GLOBAL_REGIONS))
        return trending
    
    # Return cached data if available
    if _trends_cache["data"]:
        logger.debug("async_trends_using_stale_cache")
        return _trends_cache["data"]
    
    logger.warning("async_trends_collection_failed")
    return []


async def _fetch_trends_from_region(region: str) -> List[str]:
    """Fetch trending topics from a specific region."""
    try:
        url = f"{TRENDS_RSS_BASE}?geo={region}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }
        
        response_text = await fetch_url(url, headers=headers)
        
        if not response_text:
            return []
        
        # Parse RSS XML
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response_text, 'xml')
        items = soup.find_all('item')
        
        trending = []
        for item in items[:10]:  # Top 10 per region
            title = item.find('title')
            if title:
                trending.append(title.text.strip())
        
        if trending:
            logger.debug("async_trends_region_success", region=region, count=len(trending))
        return trending
            
    except Exception as e:
        logger.debug("async_trends_region_error", region=region, error=str(e))
        return []


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
