"""
Mastodon Multi-Instance Collector

Samples posts from multiple Mastodon instances to get broader coverage
of the fediverse. Uses public timeline API.
"""

from typing import List, Dict, Any
import structlog

from mastodon import Mastodon

from src.config import settings

logger = structlog.get_logger()

# Popular Mastodon instances for sampling
MASTODON_INSTANCES = [
    "https://mastodon.social",      # Largest general instance
    "https://mastodon.online",      # Second largest
    "https://mstdn.social",         # Tech community
    "https://infosec.exchange",     # Security community
    "https://journa.host",          # Journalists
]


def collect_mastodon_posts() -> List[Dict[str, Any]]:
    """
    Collect recent posts from multiple Mastodon instances.
    
    Returns:
        List of post dictionaries with:
        - text: Post content (HTML stripped)
        - author: Author handle@instance
        - created_at: Timestamp
        - reblogs: Reblog count
        - favourites: Favourite count
    """
    logger.info("mastodon_collection_started",
                instances=len(MASTODON_INSTANCES),
                sample_size=settings.MASTODON_SAMPLE_SIZE)
    
    posts = []
    posts_per_instance = settings.MASTODON_SAMPLE_SIZE // len(MASTODON_INSTANCES)
    
    for instance_url in MASTODON_INSTANCES:
        try:
            instance_posts = collect_from_instance(instance_url, posts_per_instance)
            posts.extend(instance_posts)
            logger.debug("mastodon_instance_collected", 
                        instance=instance_url, 
                        count=len(instance_posts))
        except Exception as e:
            logger.warning("mastodon_instance_failed", 
                          instance=instance_url, 
                          error=str(e))
            continue
    
    logger.info("mastodon_collection_complete", count=len(posts))
    return posts


def collect_from_instance(instance_url: str, limit: int) -> List[Dict[str, Any]]:
    """Collect posts from a single Mastodon instance."""
    # Create client without auth for public timeline
    mastodon = Mastodon(api_base_url=instance_url)
    
    # Get public timeline
    timeline = mastodon.timeline_public(limit=limit)
    
    posts = []
    for status in timeline:
        # Strip HTML from content
        content = strip_html(status.get("content", ""))
        
        posts.append({
            "text": content,
            "author": f"{status['account']['acct']}@{instance_url.replace('https://', '')}",
            "created_at": status.get("created_at"),
            "reblogs": status.get("reblogs_count", 0),
            "favourites": status.get("favourites_count", 0),
            "replies": status.get("replies_count", 0),
            "url": status.get("url", ""),
            "language": status.get("language", "en"),
            "source": "mastodon",
            "instance": instance_url
        })
    
    return posts


def strip_html(html_content: str) -> str:
    """Strip HTML tags from content."""
    import re
    # Remove HTML tags
    clean = re.sub(r'<[^>]+>', '', html_content)
    # Decode HTML entities
    clean = clean.replace("&amp;", "&")
    clean = clean.replace("&lt;", "<")
    clean = clean.replace("&gt;", ">")
    clean = clean.replace("&quot;", '"')
    clean = clean.replace("&#39;", "'")
    clean = clean.replace("&nbsp;", " ")
    return clean.strip()


def get_mastodon_trending_topics(posts: List[Dict[str, Any]]) -> List[str]:
    """Extract trending topics from Mastodon posts."""
    hashtags = {}
    
    for post in posts:
        text = post.get("text", "")
        # Extract hashtags
        words = text.split()
        for word in words:
            if word.startswith("#") and len(word) > 1:
                tag = word.lower().strip("#.,!?")
                hashtags[tag] = hashtags.get(tag, 0) + 1
    
    sorted_tags = sorted(hashtags.items(), key=lambda x: x[1], reverse=True)
    return [f"#{tag}" for tag, count in sorted_tags[:10]]


if __name__ == "__main__":
    # Test collection
    import logging
    logging.basicConfig(level=logging.INFO)
    
    posts = collect_mastodon_posts()
    print(f"Collected {len(posts)} posts")
    if posts:
        print(f"Sample: {posts[0]}")
