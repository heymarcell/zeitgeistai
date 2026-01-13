"""
Zeitgeist Engine - Main Pipeline

Orchestrates the complete digest generation pipeline:
1. Collect signals from GDELT, Bluesky, Mastodon, and Google Trends
2. Deduplicate and cluster articles
3. Match to Story Arcs (multi-day tracking)
4. Detect contrarian/underreported stories
5. Generate narrative with verification
6. Create illustration concept
7. Publish to social platforms
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import structlog

from src.config import settings

# Collectors
from src.collectors.gdelt import collect_gdelt_articles
from src.collectors.bluesky import collect_bluesky_posts
from src.collectors.mastodon import collect_mastodon_posts
from src.collectors.trends import get_trending_topics

# Processors
from src.processors.dedup import deduplicate_articles
from src.processors.clustering import cluster_articles
from src.processors.scoring import calculate_virality_scores
from src.processors.story_arc import match_clusters_to_story_arcs
from src.processors.contrarian import calculate_narrative_divergence

# Generators
from src.generators.synthesis import generate_digest_narrative
from src.generators.verification import verify_generated_content
from src.generators.illustration import generate_illustration_concept

# Publishers
from src.publishers.bluesky import post_to_bluesky
from src.publishers.mastodon import post_to_mastodon


# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
)

logger = structlog.get_logger()


def get_edition_name(hour: int) -> str:
    """Get the edition name based on UTC hour."""
    editions = {
        2: "Overnight Edition",
        6: "Dawn Edition",
        10: "Morning Brief",
        14: "Afternoon Update",
        18: "Evening Digest",
        22: "Night Report",
    }
    scheduled_hours = sorted(editions.keys())
    closest = min(scheduled_hours, key=lambda x: abs(x - hour))
    return editions[closest]


def generate_digest_id() -> str:
    """Generate a unique digest ID based on current timestamp."""
    now = datetime.now(timezone.utc)
    return f"{now.strftime('%Y-%m-%d')}-{now.hour:02d}"


def run_pipeline() -> dict:
    """
    Run the complete Zeitgeist pipeline with all Phase 2 features.
    
    Returns:
        dict: The generated digest with all metadata
    """
    start_time = datetime.now(timezone.utc)
    digest_id = generate_digest_id()
    edition = get_edition_name(start_time.hour)
    
    logger.info("pipeline_started", digest_id=digest_id, edition=edition)
    
    try:
        # =====================================================================
        # PHASE 1: SIGNAL ACQUISITION
        # =====================================================================
        logger.info("phase_1_collection_started")
        
        # Collect from all sources
        gdelt_articles = collect_gdelt_articles()
        logger.info("gdelt_collected", count=len(gdelt_articles))
        
        bluesky_posts = collect_bluesky_posts()
        logger.info("bluesky_collected", count=len(bluesky_posts))
        
        mastodon_posts = collect_mastodon_posts()
        logger.info("mastodon_collected", count=len(mastodon_posts))
        
        trending = get_trending_topics()
        logger.info("trends_collected", count=len(trending))
        
        # Combine social posts
        social_posts = bluesky_posts + mastodon_posts
        
        # =====================================================================
        # PHASE 2: PROCESSING
        # =====================================================================
        logger.info("phase_2_processing_started")
        
        # Deduplicate articles
        all_articles = gdelt_articles
        deduped = deduplicate_articles(all_articles)
        logger.info("deduplication_complete", 
                    original=len(all_articles), 
                    unique=len(deduped))
        
        # Cluster articles
        clusters = cluster_articles(deduped)
        logger.info("clustering_complete", num_clusters=len(clusters))
        
        # Calculate virality scores
        scored_clusters = calculate_virality_scores(
            clusters, 
            bluesky_posts, 
            mastodon_posts,
            trending
        )
        logger.info("scoring_complete")
        
        # Match to Story Arcs (Phase 2 feature)
        clusters_with_arcs = match_clusters_to_story_arcs(
            scored_clusters,
            digest_id
        )
        logger.info("story_arcs_matched")
        
        # Detect contrarian signals (Phase 2 feature)
        clusters_with_divergence = calculate_narrative_divergence(
            clusters_with_arcs,
            gdelt_articles,
            social_posts
        )
        logger.info("contrarian_detection_complete")
        
        # =====================================================================
        # PHASE 3: GENERATION
        # =====================================================================
        logger.info("phase_3_generation_started")
        
        # Generate narrative
        digest = generate_digest_narrative(
            digest_id=digest_id,
            edition=edition,
            clusters=clusters_with_divergence,
            trending=trending
        )
        logger.info("narrative_generated", headline=digest.get("headline", "")[:50])
        
        # Verify content (Phase 2 feature)
        verification = verify_generated_content(
            digest.get("summary", ""),
            sources=[{"text": str(a)} for a in gdelt_articles[:10]]
        )
        digest["verification"] = verification
        logger.info("verification_complete", 
                    passed=verification.get("passed"),
                    faithfulness=verification.get("faithfulness_score"))
        
        # Generate illustration concept (Phase 2 feature)
        illustration = generate_illustration_concept(digest, clusters_with_divergence)
        digest["illustration_concept"] = illustration
        logger.info("illustration_generated", style=illustration.get("style"))
        
        # Add pipeline metadata
        digest["generated_at"] = start_time.isoformat()
        digest["pipeline_version"] = "2.0.0"
        digest["signals"] = {
            "gdelt_articles": len(gdelt_articles),
            "bluesky_posts": len(bluesky_posts),
            "mastodon_posts": len(mastodon_posts),
            "trending_topics": len(trending),
        }
        
        # Add story arc summary
        digest["story_arcs"] = [
            c.get("story_arc") for c in clusters_with_divergence[:5]
            if c.get("story_arc")
        ]
        
        # Add hidden stories
        hidden_stories = [
            c for c in clusters_with_divergence
            if c.get("narrative_divergence", {}).get("type") in 
               ["SEVERELY_UNDERREPORTED", "UNDERREPORTED"]
        ]
        if hidden_stories:
            digest["hidden_stories"] = [
                {"topics": h.get("topics", [])[:3], 
                 "nd_score": h.get("narrative_divergence", {}).get("nd_score")}
                for h in hidden_stories[:3]
            ]
        
        # =====================================================================
        # PHASE 4: OUTPUT
        # =====================================================================
        logger.info("phase_4_output_started")
        
        # Save to file
        output_dir = Path(settings.OUTPUT_DIR)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"digest-{digest_id}.json"
        
        with open(output_file, "w") as f:
            json.dump(digest, f, indent=2, ensure_ascii=False, default=str)
        logger.info("digest_saved", path=str(output_file))
        
        # Post to social platforms
        social_text = format_social_post(digest)
        
        if settings.ENABLE_BLUESKY_POST:
            try:
                post_to_bluesky(social_text)
                logger.info("bluesky_posted")
            except Exception as e:
                logger.error("bluesky_post_failed", error=str(e))
        
        if settings.ENABLE_MASTODON_POST:
            try:
                post_to_mastodon(social_text)
                logger.info("mastodon_posted")
            except Exception as e:
                logger.error("mastodon_post_failed", error=str(e))
        
        # =====================================================================
        # COMPLETE
        # =====================================================================
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        logger.info("pipeline_complete", 
                    digest_id=digest_id, 
                    duration_seconds=round(duration, 2),
                    clusters=len(clusters_with_divergence),
                    verified=verification.get("passed"))
        
        return digest
        
    except Exception as e:
        logger.exception("pipeline_failed", error=str(e))
        raise


def format_social_post(digest: dict) -> str:
    """Format digest for social media posting."""
    template = """🌐 Zeitgeist | {edition}

📰 {headline}

{summary}

🔗 zeitgeist.app/{digest_id}

#Zeitgeist #GlobalNews #AI"""
    
    # Truncate summary to fit social limits
    summary = digest.get("summary", "")
    if len(summary) > 180:
        summary = summary[:177] + "..."
    
    return template.format(
        edition=digest.get("edition", "Update"),
        headline=digest.get("headline", ""),
        summary=summary,
        digest_id=digest.get("digest_id", "")
    )


if __name__ == "__main__":
    # Run pipeline manually
    logging.basicConfig(level=logging.INFO)
    digest = run_pipeline()
    print(json.dumps(digest, indent=2, default=str))
