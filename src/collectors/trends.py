"""
Google Trends Collector

ARCHIVED PYTRENDS: The GeneralMills/pytrends repo was archived April 2025.
This module uses a workaround with direct web scraping as fallback.
"""

import time
import json
import re
from typing import List, Dict, Any
from datetime import datetime, timezone
import structlog

import requests
from bs4 import BeautifulSoup

from src.config import settings

logger = structlog.get_logger()

# Cache for trends data
_trends_cache: Dict[str, Any] = {
    "data": None,
    "timestamp": None,
    "ttl": 3600  # Cache for 1 hour
}

# Google Trends Daily Trending Searches RSS feed
TRENDS_RSS_URL = "https://trends.google.com/trending/rss?geo=US"

# Alternative: Google Trends Explore endpoint (may require more setup)
TRENDS_EXPLORE_URL = "https://trends.google.com/trends/api/dailytrends"


def get_trending_topics() -> List[str]:
    """
    Get trending search topics from Google Trends.
    
    Uses RSS feed as primary method (more reliable than pytrends).
    Falls back to cache if all methods fail.
    
    Returns:
        List of trending topic strings
    """
    logger.info("trends_collection_started")
    
    # Check cache first
    if _is_cache_valid():
        logger.info("trends_cache_hit")
        return _trends_cache["data"]
    
    # Try multiple methods in order of reliability
    trending = None
    
    # Method 1: Try RSS feed (most reliable)
    trending = _fetch_trends_from_rss()
    
    # Method 2: Try daily trends API
    if not trending:
        trending = _fetch_trends_from_api()
    
    # Method 3: Try pytrends as fallback
    if not trending:
        trending = _fetch_trends_from_pytrends()
    
    if trending:
        # Update cache
        _trends_cache["data"] = trending
        _trends_cache["timestamp"] = datetime.now(timezone.utc)
        logger.info("trends_collection_complete", count=len(trending))
        return trending
    
    # Return cached data if available, even if stale
    if _trends_cache["data"]:
        logger.info("trends_using_stale_cache")
        return _trends_cache["data"]
    
    logger.warning("trends_collection_failed", error="All methods failed")
    return []


def _fetch_trends_from_rss() -> List[str]:
    """Fetch trending topics from Google Trends RSS feed."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }
        response = requests.get(TRENDS_RSS_URL, headers=headers, timeout=10)
        
        if response.status_code != 200:
            logger.debug("trends_rss_failed", status=response.status_code)
            return None
        
        # Parse RSS XML
        soup = BeautifulSoup(response.text, 'xml')
        items = soup.find_all('item')
        
        trending = []
        for item in items[:20]:  # Top 20
            title = item.find('title')
            if title:
                trending.append(title.text.strip())
        
        if trending:
            logger.debug("trends_rss_success", count=len(trending))
            return trending
        
    except Exception as e:
        logger.debug("trends_rss_error", error=str(e))
    
    return None


def _fetch_trends_from_api() -> List[str]:
    """Fetch trending topics from Google Trends daily trends API."""
    try:
        params = {
            "hl": "en-US",
            "ed": datetime.now().strftime("%Y%m%d"),
            "geo": "US",
            "ns": "15",
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }
        
        response = requests.get(TRENDS_EXPLORE_URL, params=params, headers=headers, timeout=10)
        
        if response.status_code != 200:
            logger.debug("trends_api_failed", status=response.status_code)
            return None
        
        # Response has )]}' prefix that needs to be removed
        text = response.text
        if text.startswith(")]}'"):
            text = text[5:]
        
        data = json.loads(text)
        
        trending = []
        for day in data.get("default", {}).get("trendingSearchesDays", []):
            for search in day.get("trendingSearches", []):
                title = search.get("title", {}).get("query", "")
                if title:
                    trending.append(title)
        
        if trending:
            logger.debug("trends_api_success", count=len(trending))
            return trending[:20]
        
    except Exception as e:
        logger.debug("trends_api_error", error=str(e))
    
    return None


def _fetch_trends_from_pytrends() -> List[str]:
    """Try pytrends as last resort (may fail due to archived repo)."""
    try:
        from pytrends.request import TrendReq
        
        pytrends = TrendReq(hl='en-US', tz=360)
        trending_df = pytrends.trending_searches(pn='united_states')
        
        if not trending_df.empty:
            trending = trending_df[0].tolist()
            time.sleep(2)  # Rate limit protection
            logger.debug("trends_pytrends_success", count=len(trending))
            return trending
            
    except Exception as e:
        logger.debug("trends_pytrends_error", error=str(e))
    
    return None


def _is_cache_valid() -> bool:
    """Check if cached trends data is still valid."""
    if not _trends_cache["data"] or not _trends_cache["timestamp"]:
        return False
    
    age = (datetime.now(timezone.utc) - _trends_cache["timestamp"]).total_seconds()
    return age < _trends_cache["ttl"]


def get_related_queries(keyword: str) -> Dict[str, List[str]]:
    """
    Get related queries for a specific keyword.
    
    Note: Use sparingly due to rate limiting.
    """
    logger.info("related_queries_started", keyword=keyword)
    
    try:
        from pytrends.request import TrendReq
        
        pytrends = TrendReq(hl='en-US', tz=360)
        pytrends.build_payload([keyword], timeframe='now 1-d')
        
        related = pytrends.related_queries()
        
        result = {"top": [], "rising": []}
        
        if keyword in related:
            if related[keyword].get("top") is not None:
                result["top"] = related[keyword]["top"]["query"].tolist()[:5]
            if related[keyword].get("rising") is not None:
                result["rising"] = related[keyword]["rising"]["query"].tolist()[:5]
        
        time.sleep(3)
        return result
        
    except Exception as e:
        logger.warning("related_queries_failed", keyword=keyword, error=str(e))
        return {"top": [], "rising": []}


if __name__ == "__main__":
    # Test collection
    import logging
    logging.basicConfig(level=logging.DEBUG)
    
    trending = get_trending_topics()
    print(f"Trending topics ({len(trending)}):")
    for i, topic in enumerate(trending[:10], 1):
        print(f"  {i}. {topic}")
