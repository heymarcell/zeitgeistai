"""
Async Mastodon Multi-Instance Collector

Asynchronously samples public timelines from multiple Mastodon instances in parallel.
"""

import asyncio
from typing import List, Dict, Any
from datetime import datetime, timezone
import structlog

from src.collectors.async_base import fetch_json
from src.config import settings

logger = structlog.get_logger()

# Diverse instance list for broader fediverse coverage
DEFAULT_INSTANCES = [
    "https://mastodon.social",
    "https://mastodon.online", 
    "https://mstdn.social",
    "https://infosec.exchange",
    "https://journa.host",
]


async def collect_mastodon_posts_async(
    instances: List[str] = None,
    limit_per_instance: int = 20
) -> List[Dict[str, Any]]:
    """
    Asynchronously collect posts from multiple Mastodon instances in parallel.
    
    Args:
        instances: List of Mastodon instance URLs
        limit_per_instance: Posts to fetch per instance
        
    Returns:
        Combined list of posts from all instances
    """
    if instances is None:
        instances = DEFAULT_INSTANCES
    
    sample_size = settings.MASTODON_SAMPLE_SIZE
    limit_per_instance = min(limit_per_instance, sample_size // len(instances))
    
    logger.info("async_mastodon_collection_started", 
                instances=len(instances),
                limit_per_instance=limit_per_instance)
    
    # Fetch from all instances in parallel
    tasks = [
        _fetch_instance_timeline(instance, limit_per_instance)
        for instance in instances
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Combine results
    all_posts = []
    for instance, result in zip(instances, results):
        if isinstance(result, Exception):
            logger.warning("async_mastodon_instance_failed",
                          instance=instance,
                          error=str(result))
        elif result:
            all_posts.extend(result)
            logger.debug("async_mastodon_instance_collected",
                        instance=instance,
                        count=len(result))
    
    logger.info("async_mastodon_collection_complete", count=len(all_posts))
    return all_posts


async def _fetch_instance_timeline(
    instance_url: str,
    limit: int = 20
) -> List[Dict[str, Any]]:
    """Fetch public timeline from a single Mastodon instance."""
    api_url = f"{instance_url}/api/v1/timelines/public?limit={limit}"
    
    try:
        data = await fetch_json(api_url)
        
        if not data or not isinstance(data, list):
            return []
        
        posts = []
        for status in data:
            # Skip non-public or reblogged posts
            if status.get("reblog") or status.get("visibility") != "public":
                continue
            
            # Extract text from HTML content
            content = status.get("content", "")
            # Simple HTML stripping
            import re
            text = re.sub(r'<[^>]+>', '', content)
            text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
            
            posts.append({
                "text": text,
                "author": status.get("account", {}).get("acct", "unknown"),
                "created_at": status.get("created_at"),
                "url": status.get("url"),
                "reblogs": status.get("reblogs_count", 0),
                "favourites": status.get("favourites_count", 0),
                "instance": instance_url,
                "source": "mastodon"
            })
        
        return posts
        
    except Exception as e:
        logger.debug("async_mastodon_fetch_error", 
                    instance=instance_url, 
                    error=str(e))
        raise


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    
    async def test():
        posts = await collect_mastodon_posts_async()
        print(f"Got {len(posts)} posts")
        if posts:
            print(f"Sample: {posts[0]['text'][:80]}...")
    
    asyncio.run(test())
