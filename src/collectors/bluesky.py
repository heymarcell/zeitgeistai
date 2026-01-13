"""
Bluesky Jetstream Collector

Samples recent posts from Bluesky using Jetstream (lightweight firehose alternative).
This uses ~850 MB/day instead of 232 GB/day for the full firehose.
"""

import json
import time
from typing import List, Dict, Any
from datetime import datetime, timezone
import structlog

from atproto import Client

from src.config import settings

logger = structlog.get_logger()


def collect_bluesky_posts() -> List[Dict[str, Any]]:
    """
    Collect recent posts from Bluesky.
    
    For MVP, we use the authenticated timeline API instead of Jetstream
    to keep things simple. Jetstream can be added later for real-time.
    
    Returns:
        List of post dictionaries with:
        - text: Post content
        - author: Author handle
        - created_at: Timestamp
        - likes: Like count (if available)
        - reposts: Repost count (if available)
    """
    logger.info("bluesky_collection_started", 
                sample_size=settings.BLUESKY_SAMPLE_SIZE)
    
    if not settings.BLUESKY_HANDLE or not settings.BLUESKY_APP_PASSWORD:
        logger.warning("bluesky_credentials_missing")
        return []
    
    try:
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
        
        logger.info("bluesky_collection_complete", count=len(posts))
        return posts
        
    except Exception as e:
        logger.error("bluesky_collection_failed", error=str(e))
        return []


def get_bluesky_trending_topics(posts: List[Dict[str, Any]]) -> List[str]:
    """
    Extract trending topics from Bluesky posts.
    
    Looks for hashtags and frequently mentioned terms.
    """
    hashtags = {}
    
    for post in posts:
        text = post.get("text", "")
        # Extract hashtags
        words = text.split()
        for word in words:
            if word.startswith("#") and len(word) > 1:
                tag = word.lower().strip("#.,!?")
                hashtags[tag] = hashtags.get(tag, 0) + 1
    
    # Sort by frequency and return top 10
    sorted_tags = sorted(hashtags.items(), key=lambda x: x[1], reverse=True)
    return [f"#{tag}" for tag, count in sorted_tags[:10]]


if __name__ == "__main__":
    # Test collection
    import logging
    logging.basicConfig(level=logging.INFO)
    
    posts = collect_bluesky_posts()
    print(f"Collected {len(posts)} posts")
    if posts:
        print(f"Sample: {posts[0]}")
        
    trending = get_bluesky_trending_topics(posts)
    print(f"Trending: {trending}")
