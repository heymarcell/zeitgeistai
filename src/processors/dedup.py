"""
Deduplication Module

Removes duplicate articles using SHA-256 hash for MVP.
Full implementation will add SimHash and semantic deduplication.
"""

import hashlib
from typing import List, Dict, Any
import structlog

logger = structlog.get_logger()


def deduplicate_articles(articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Remove duplicate articles using URL hashing.
    
    MVP implementation uses simple SHA-256 hash of URLs.
    
    Args:
        articles: List of article dictionaries
        
    Returns:
        Deduplicated list of articles
    """
    logger.info("deduplication_started", count=len(articles))
    
    seen_hashes = set()
    unique_articles = []
    
    for article in articles:
        # Create hash from URL
        url = article.get("url", "")
        if not url:
            continue
            
        url_hash = hashlib.sha256(url.encode()).hexdigest()
        
        if url_hash not in seen_hashes:
            seen_hashes.add(url_hash)
            article["hash"] = url_hash
            unique_articles.append(article)
    
    removed = len(articles) - len(unique_articles)
    logger.info("deduplication_complete", 
                original=len(articles),
                unique=len(unique_articles),
                removed=removed)
    
    return unique_articles


def create_content_hash(text: str) -> str:
    """Create a hash from text content for content-based dedup."""
    # Normalize text
    normalized = text.lower().strip()
    # Remove extra whitespace
    normalized = " ".join(normalized.split())
    return hashlib.sha256(normalized.encode()).hexdigest()


# TODO: Add SimHash for near-duplicate detection
# TODO: Add semantic deduplication using embeddings
