"""
Contrarian Signal Detection Module

Detects stories where grassroots discussion diverges from mainstream coverage.
Uses Narrative Divergence Index (Nd) to surface underreported stories.

Nd > 3.0: Severely Underreported → Flag as "Hidden Story"
Nd 2.0-3.0: Underreported → Boost virality by 15%
Nd 0.5-2.0: Normal Coverage → No adjustment
Nd < 0.5: Overreported/Astroturf → Demote virality by 10%
"""

from typing import List, Dict, Any
from collections import defaultdict
import structlog

logger = structlog.get_logger()

# Historical ratio (mainstream/grassroots) for normalization
HISTORICAL_RATIO_BASELINE = 10.0  # Typical 10 news articles per 1 social discussion

# Thresholds from spec
SEVERELY_UNDERREPORTED_THRESHOLD = 3.0
UNDERREPORTED_THRESHOLD = 2.0
OVERREPORTED_THRESHOLD = 0.5


def calculate_narrative_divergence(
    clusters: List[Dict[str, Any]],
    gdelt_articles: List[Dict[str, Any]],
    social_posts: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Calculate Narrative Divergence Index for each cluster.
    
    Detects stories that are being discussed heavily on social media
    but not covered proportionally in mainstream news (and vice versa).
    
    Args:
        clusters: Article clusters with topics
        gdelt_articles: All GDELT articles (mainstream signal)
        social_posts: Bluesky + Mastodon posts (grassroots signal)
        
    Returns:
        Clusters with narrative_divergence field added
    """
    logger.info("contrarian_detection_started", num_clusters=len(clusters))
    
    # Count topic mentions in each source
    mainstream_counts = _count_topic_mentions(gdelt_articles, "mainstream")
    grassroots_counts = _count_topic_mentions(social_posts, "grassroots")
    
    for cluster in clusters:
        topics = cluster.get("topics", [])
        
        # Count mainstream volume for this cluster
        mainstream_volume = sum(
            mainstream_counts.get(topic.lower(), 0) for topic in topics
        )
        
        # Count grassroots volume for this cluster
        grassroots_volume = sum(
            grassroots_counts.get(topic.lower(), 0) for topic in topics
        )
        
        # Calculate Narrative Divergence Index
        nd = _calculate_nd(mainstream_volume, grassroots_volume)
        
        # Determine divergence type and adjustment
        divergence_type, adjustment = _interpret_nd(nd)
        
        # Apply adjustment to virality score
        if "virality_score" in cluster:
            original_score = cluster["virality_score"]
            cluster["virality_score"] = original_score * (1 + adjustment)
        
        cluster["narrative_divergence"] = {
            "nd_score": round(nd, 3),
            "type": divergence_type,
            "mainstream_volume": mainstream_volume,
            "grassroots_volume": grassroots_volume,
            "adjustment": adjustment,
        }
        
        if divergence_type in ["SEVERELY_UNDERREPORTED", "UNDERREPORTED"]:
            logger.info("hidden_story_detected",
                       topics=topics[:3],
                       nd_score=round(nd, 2),
                       type=divergence_type)
    
    logger.info("contrarian_detection_complete")
    return clusters


def _count_topic_mentions(
    items: List[Dict[str, Any]],
    source_type: str
) -> Dict[str, int]:
    """Count how many times each topic is mentioned in items."""
    counts = defaultdict(int)
    
    for item in items:
        # Get text content based on source type
        if source_type == "mainstream":
            # GDELT articles have themes
            themes = item.get("themes", [])
            if isinstance(themes, list):
                for theme in themes:
                    counts[theme.lower()] += 1
        else:
            # Social posts have text
            text = item.get("text", "").lower()
            words = text.split()
            for word in words:
                # Clean word
                word = word.strip("#@.,!?")
                if len(word) > 3:
                    counts[word] += 1
    
    return dict(counts)


def _calculate_nd(mainstream_volume: int, grassroots_volume: int) -> float:
    """
    Calculate Narrative Divergence Index.
    
    Nd = expected_ratio / actual_ratio
    
    Where:
    - expected_ratio = HISTORICAL_RATIO_BASELINE (typically 10:1 mainstream:grassroots)
    - actual_ratio = mainstream_volume / grassroots_volume
    """
    # Avoid division by zero
    grassroots_volume = max(grassroots_volume, 1)
    mainstream_volume = max(mainstream_volume, 1)
    
    actual_ratio = mainstream_volume / grassroots_volume
    
    # Nd = expected / actual
    # High Nd means social is discussing it more than mainstream covers it
    nd = HISTORICAL_RATIO_BASELINE / actual_ratio
    
    return nd


def _interpret_nd(nd: float) -> tuple:
    """
    Interpret Narrative Divergence Index.
    
    Returns:
        tuple: (divergence_type, adjustment_factor)
    """
    if nd > SEVERELY_UNDERREPORTED_THRESHOLD:
        return ("SEVERELY_UNDERREPORTED", 0.20)  # Boost 20%
    elif nd > UNDERREPORTED_THRESHOLD:
        return ("UNDERREPORTED", 0.15)  # Boost 15%
    elif nd < OVERREPORTED_THRESHOLD:
        return ("OVERREPORTED", -0.10)  # Demote 10%
    else:
        return ("NORMAL", 0.0)


def get_hidden_stories(clusters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Get clusters flagged as hidden/underreported stories.
    """
    hidden = []
    for cluster in clusters:
        nd_info = cluster.get("narrative_divergence", {})
        if nd_info.get("type") in ["SEVERELY_UNDERREPORTED", "UNDERREPORTED"]:
            hidden.append(cluster)
    
    return sorted(hidden, key=lambda x: x.get("narrative_divergence", {}).get("nd_score", 0), reverse=True)


if __name__ == "__main__":
    # Test contrarian detection
    import logging
    logging.basicConfig(level=logging.INFO)
    
    test_clusters = [
        {
            "cluster_id": 0,
            "topics": ["CLIMATE", "PROTEST", "ACTIVISM"],
            "virality_score": 0.5
        }
    ]
    
    # Simulate: high social discussion, low mainstream coverage
    gdelt_articles = [{"themes": ["POLITICS"]}]  # Not covering climate
    social_posts = [{"text": "Climate protest happening!"} for _ in range(50)]
    
    result = calculate_narrative_divergence(test_clusters, gdelt_articles, social_posts)
    print(f"Divergence result: {result[0]['narrative_divergence']}")
