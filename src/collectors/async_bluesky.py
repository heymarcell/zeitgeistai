"""
Async Bluesky Collector

Wraps the synchronous atproto client in async executor for non-blocking operation.
Note: atproto doesn't have native async support, so we use run_in_executor.
"""

import asyncio
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor
import structlog

from src.config import settings

logger = structlog.get_logger()

# Thread pool for running sync atproto calls
_executor = ThreadPoolExecutor(max_workers=2)


async def collect_bluesky_posts_async() -> List[Dict[str, Any]]:
    """
    Asynchronously collect posts from Bluesky.
    
    Uses thread pool executor since atproto is synchronous.
    """
    logger.info("async_bluesky_collection_started")
    
    if not settings.BLUESKY_HANDLE or not settings.BLUESKY_APP_PASSWORD:
        logger.warning("async_bluesky_credentials_missing")
        return []
    
    try:
        # Run sync collection in thread pool
        loop = asyncio.get_event_loop()
        posts = await loop.run_in_executor(_executor, _sync_collect_bluesky)
        
        logger.info("async_bluesky_collection_complete", count=len(posts))
        return posts
        
    except Exception as e:
        logger.error("async_bluesky_collection_failed", error=str(e))
        return []


def _sync_collect_bluesky() -> List[Dict[str, Any]]:
    """Synchronous Bluesky collection (runs in thread pool)."""
    from atproto import Client
    
    client = Client()
    client.login(settings.BLUESKY_HANDLE, settings.BLUESKY_APP_PASSWORD)
    
    posts = []
    
    # Get timeline feed
    feed = client.get_timeline(limit=settings.BLUESKY_SAMPLE_SIZE)
    
    for item in feed.feed:
        post = item.post
        
        posts.append({
            "text": post.record.text if hasattr(post.record, 'text') else "",
            "author": post.author.handle,
            "created_at": post.record.created_at if hasattr(post.record, 'created_at') else None,
            "likes": post.like_count if hasattr(post, 'like_count') else 0,
            "reposts": post.repost_count if hasattr(post, 'repost_count') else 0,
            "replies": post.reply_count if hasattr(post, 'reply_count') else 0,
            "uri": post.uri,
            "source": "bluesky"
        })
    
    return posts


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    
    async def test():
        posts = await collect_bluesky_posts_async()
        print(f"Got {len(posts)} posts")
        if posts:
            print(f"Sample: {posts[0]['text'][:80]}...")
    
    asyncio.run(test())
