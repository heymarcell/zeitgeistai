"""
Virality Scoring Module

Calculates viral velocity scores using the research-calibrated formula:
Zv = 0.28(Et) + 0.22(Ve) + 0.15(Cc) + 0.12(Tf) + 0.10(Pv) + 0.08(Ta) + 0.05(Sc)
"""

from typing import List, Dict, Any
from datetime import datetime, timezone
import math
import structlog

logger = structlog.get_logger()

# Scoring weights (research-calibrated)
WEIGHTS = {
    "emotional_triggers": 0.28,
    "velocity_engagement": 0.22,
    "crisis_category": 0.15,
    "timing_freshness": 0.12,
    "practical_value": 0.10,
    "trend_alignment": 0.08,
    "source_credibility": 0.05,
}

# High-arousal emotional themes (from psychology research)
HIGH_AROUSAL_THEMES = {
    "CRISIS", "WAR", "CONFLICT", "DEATH", "DISASTER", "PROTEST",
    "SCANDAL", "CONTROVERSY", "BREAKTHROUGH", "HISTORIC", "SHOCKING"
}

# Crisis/viral category themes
CRISIS_THEMES = {
    "WAR", "CONFLICT", "PROTEST", "TERROR", "DISASTER",
    "EPIDEMIC", "EMERGENCY", "CRISIS"
}

# Practical value themes
PRACTICAL_THEMES = {
    "HOWTO", "TIPS", "GUIDE", "ADVICE", "EXPLAINER",
    "TUTORIAL", "EDUCATION", "HEALTH"
}


def calculate_virality_scores(
    clusters: List[Dict[str, Any]],
    bluesky_posts: List[Dict[str, Any]],
    mastodon_posts: List[Dict[str, Any]],
    trending_topics: List[str]
) -> List[Dict[str, Any]]:
    """
    Calculate viral velocity scores for each cluster.
    
    Args:
        clusters: List of article clusters
        bluesky_posts: Recent Bluesky posts for engagement signals
        mastodon_posts: Recent Mastodon posts for engagement signals
        trending_topics: Google Trends topics for alignment
        
    Returns:
        Clusters sorted by virality score (highest first)
    """
    logger.info("scoring_started", num_clusters=len(clusters))
    
    # Extract social signals
    social_keywords = extract_social_keywords(bluesky_posts, mastodon_posts)
    trending_set = set(t.lower() for t in trending_topics)
    
    for cluster in clusters:
        # Get cluster topics
        topics = set(t.upper() for t in cluster.get("topics", []))
        
        # Calculate each factor
        emotional = calculate_emotional_score(topics)
        velocity = calculate_velocity_score(cluster, social_keywords)
        crisis = calculate_crisis_score(topics)
        freshness = calculate_freshness_score(cluster)
        practical = calculate_practical_score(topics)
        trend_align = calculate_trend_alignment(cluster, trending_set)
        credibility = calculate_source_credibility(cluster)
        
        # Apply weighted formula
        score = (
            WEIGHTS["emotional_triggers"] * emotional +
            WEIGHTS["velocity_engagement"] * velocity +
            WEIGHTS["crisis_category"] * crisis +
            WEIGHTS["timing_freshness"] * freshness +
            WEIGHTS["practical_value"] * practical +
            WEIGHTS["trend_alignment"] * trend_align +
            WEIGHTS["source_credibility"] * credibility
        )
        
        cluster["virality_score"] = round(score, 4)
        cluster["score_breakdown"] = {
            "emotional": round(emotional, 3),
            "velocity": round(velocity, 3),
            "crisis": round(crisis, 3),
            "freshness": round(freshness, 3),
            "practical": round(practical, 3),
            "trend_alignment": round(trend_align, 3),
            "credibility": round(credibility, 3),
        }
    
    # Sort by score
    clusters.sort(key=lambda x: x.get("virality_score", 0), reverse=True)
    
    logger.info("scoring_complete", 
                top_score=clusters[0]["virality_score"] if clusters else 0)
    
    return clusters


def calculate_emotional_score(topics: set) -> float:
    """Score based on high-arousal emotional themes."""
    matches = len(topics & HIGH_AROUSAL_THEMES)
    return min(matches / 3.0, 1.0)  # Normalize to 0-1


def calculate_velocity_score(cluster: Dict[str, Any], social_keywords: Dict[str, int]) -> float:
    """Score based on social engagement velocity."""
    cluster_topics = [t.lower() for t in cluster.get("topics", [])]
    
    total_mentions = 0
    for topic in cluster_topics:
        total_mentions += social_keywords.get(topic, 0)
    
    # Normalize (assuming 100 mentions is high velocity)
    return min(total_mentions / 100.0, 1.0)


def calculate_crisis_score(topics: set) -> float:
    """Score based on crisis/viral category presence."""
    matches = len(topics & CRISIS_THEMES)
    return min(matches / 2.0, 1.0)


def calculate_freshness_score(cluster: Dict[str, Any]) -> float:
    """Score based on recency (logarithmic decay)."""
    # For MVP, assume all articles are fresh (within 4 hours)
    # TODO: Parse article dates and calculate actual freshness
    return 0.8


def calculate_practical_score(topics: set) -> float:
    """Score based on practical value themes."""
    matches = len(topics & PRACTICAL_THEMES)
    return min(matches / 2.0, 1.0)


def calculate_trend_alignment(cluster: Dict[str, Any], trending: set) -> float:
    """Score based on alignment with Google Trends."""
    cluster_topics = set(t.lower() for t in cluster.get("topics", []))
    
    # Check for any overlap
    matches = 0
    for topic in cluster_topics:
        if any(topic in trend for trend in trending):
            matches += 1
    
    return min(matches / 2.0, 1.0)


def calculate_source_credibility(cluster: Dict[str, Any]) -> float:
    """Score based on source credibility tiers."""
    # Tier 1: Major wire services
    tier1 = {"reuters.com", "apnews.com", "afp.com"}
    # Tier 2: Major newspapers
    tier2 = {"nytimes.com", "washingtonpost.com", "theguardian.com", "bbc.com"}
    
    articles = cluster.get("articles", [])
    if not articles:
        return 0.5
    
    scores = []
    for article in articles:
        url = article.get("url", "")
        domain = url.split("/")[2] if len(url.split("/")) > 2 else ""
        
        if any(t in domain for t in tier1):
            scores.append(1.0)
        elif any(t in domain for t in tier2):
            scores.append(0.8)
        else:
            scores.append(0.5)
    
    return sum(scores) / len(scores) if scores else 0.5


def extract_social_keywords(
    bluesky_posts: List[Dict[str, Any]],
    mastodon_posts: List[Dict[str, Any]]
) -> Dict[str, int]:
    """Extract keyword frequencies from social posts."""
    keywords = {}
    
    all_posts = bluesky_posts + mastodon_posts
    
    for post in all_posts:
        text = post.get("text", "").lower()
        words = text.split()
        for word in words:
            # Clean word
            word = word.strip("#@.,!?")
            if len(word) > 3:  # Skip short words
                keywords[word] = keywords.get(word, 0) + 1
    
    return keywords


if __name__ == "__main__":
    # Test scoring
    test_clusters = [
        {
            "cluster_id": 0,
            "topics": ["POLITICS", "NATO", "WAR"],
            "articles": [{"url": "https://reuters.com/article1"}],
            "size": 10
        },
        {
            "cluster_id": 1,
            "topics": ["TECHNOLOGY", "AI"],
            "articles": [{"url": "https://techcrunch.com/article1"}],
            "size": 5
        }
    ]
    
    scored = calculate_virality_scores(test_clusters, [], [], [])
    for c in scored:
        print(f"Cluster {c['cluster_id']}: score={c['virality_score']}")
        print(f"  Breakdown: {c['score_breakdown']}")
