#!/usr/bin/env python
"""
Test script to verify the Zeitgeist Engine pipeline works.
Runs each component in isolation to check for errors.
"""

import json
from datetime import datetime

print("=" * 60)
print("ZEITGEIST ENGINE - PIPELINE TEST")
print("=" * 60)


def test_config():
    """Test configuration loading."""
    print("\n[1/6] Testing Configuration...")
    from src.config import settings
    print(f"  ✓ Config loaded")
    print(f"    - Output dir: {settings.OUTPUT_DIR}")
    print(f"    - Cluster size: {settings.MIN_CLUSTER_SIZE}")
    print(f"    - Gemini key: {'SET' if settings.GEMINI_API_KEY else 'NOT SET'}")


def test_trends():
    """Test Google Trends collector."""
    print("\n[2/6] Testing Google Trends...")
    from src.collectors.trends import get_trending_topics
    topics = get_trending_topics()
    if topics:
        print(f"  ✓ Got {len(topics)} trending topics")
        print(f"    - Top 3: {topics[:3]}")
    else:
        print("  ⚠ No topics (API may be rate-limited)")


def test_mastodon():
    """Test Mastodon collector."""
    print("\n[3/6] Testing Mastodon...")
    from src.collectors.mastodon import collect_mastodon_posts
    posts = collect_mastodon_posts()
    print(f"  ✓ Collected {len(posts)} posts from fediverse")
    if posts:
        print(f"    - Sample: {posts[0]['text'][:60]}...")


def test_dedup():
    """Test deduplication."""
    print("\n[4/6] Testing Deduplication...")
    from src.processors.dedup import deduplicate_articles
    
    test_articles = [
        {"url": "https://example.com/1", "text": "Test article 1"},
        {"url": "https://example.com/2", "text": "Test article 2"},
        {"url": "https://example.com/1", "text": "Duplicate"},  # Duplicate URL
    ]
    
    result = deduplicate_articles(test_articles)
    print(f"  ✓ Dedup works: {len(test_articles)} → {len(result)} articles")


def test_clustering():
    """Test clustering (if enough data)."""
    print("\n[5/6] Testing Clustering...")
    from src.processors.clustering import cluster_articles
    
    # Create test articles with themes
    test_articles = [
        {"url": f"https://example.com/{i}", "themes": ["POLITICS", "NATO", "SUMMIT"]}
        for i in range(10)
    ] + [
        {"url": f"https://example.com/{i+10}", "themes": ["TECHNOLOGY", "AI", "GOOGLE"]}
        for i in range(10)
    ]
    
    clusters = cluster_articles(test_articles)
    print(f"  ✓ Clustering works: {len(clusters)} clusters from {len(test_articles)} articles")


def test_scoring():
    """Test virality scoring."""
    print("\n[6/6] Testing Virality Scoring...")
    from src.processors.scoring import calculate_virality_scores
    
    test_clusters = [
        {
            "cluster_id": 0,
            "topics": ["POLITICS", "NATO", "WAR"],
            "articles": [{"url": "https://reuters.com/article1"}],
            "size": 25
        }
    ]
    
    scored = calculate_virality_scores(test_clusters, [], [], [])
    print(f"  ✓ Scoring works: score = {scored[0]['virality_score']:.3f}")
    print(f"    - Breakdown: {scored[0]['score_breakdown']}")


def main():
    """Run all tests."""
    try:
        test_config()
        test_trends()
        test_mastodon()
        test_dedup()
        test_clustering()
        test_scoring()
        
        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)
        print("\nNext steps:")
        print("1. Set GEMINI_API_KEY in .env to enable generation")
        print("2. Set BLUESKY_* credentials to enable posting")
        print("3. Run: python -m src.main")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
