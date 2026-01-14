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

Supports both sync and async collection modes.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any

import structlog

from src.config import settings

# Sync Collectors
from src.collectors.gdelt import collect_gdelt_articles
from src.collectors.bluesky import collect_bluesky_posts
from src.collectors.mastodon import collect_mastodon_posts
from src.collectors.trends import get_trending_topics

# Async Collectors
from src.collectors.async_gdelt import collect_gdelt_articles_async
from src.collectors.async_bluesky import collect_bluesky_posts_async
from src.collectors.async_mastodon import collect_mastodon_posts_async
from src.collectors.async_trends import get_trending_topics_async
from src.collectors.async_base import close_session

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


async def collect_signals_async() -> Tuple[List, List, List, List]:
    """
    Collect signals from all sources asynchronously in parallel.
    
    Returns:
        Tuple of (gdelt_articles, bluesky_posts, mastodon_posts, trending)
    """
    logger.info("async_collection_started")
    start = datetime.now(timezone.utc)
    
    try:
        # Run all collectors in parallel
        results = await asyncio.gather(
            collect_gdelt_articles_async(),
            collect_bluesky_posts_async(),
            collect_mastodon_posts_async(),
            get_trending_topics_async(),
            return_exceptions=True
        )
        
        # Extract results, handling exceptions
        gdelt = results[0] if not isinstance(results[0], Exception) else []
        bluesky = results[1] if not isinstance(results[1], Exception) else []
        mastodon = results[2] if not isinstance(results[2], Exception) else []
        trending = results[3] if not isinstance(results[3], Exception) else []
        
        # Log any exceptions
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                source = ["GDELT", "Bluesky", "Mastodon", "Trends"][i]
                logger.warning(f"async_collection_failed_{source.lower()}", 
                             error=str(result))
        
        duration = (datetime.now(timezone.utc) - start).total_seconds()
        logger.info("async_collection_complete",
                   gdelt=len(gdelt),
                   bluesky=len(bluesky),
                   mastodon=len(mastodon),
                   trends=len(trending),
                   duration_seconds=round(duration, 2))
        
        return gdelt, bluesky, mastodon, trending
        
    finally:
        # Cleanup aiohttp session
        await close_session()


def collect_signals_sync() -> Tuple[List, List, List, List]:
    """
    Collect signals from all sources synchronously (sequential).
    
    Returns:
        Tuple of (gdelt_articles, bluesky_posts, mastodon_posts, trending)
    """
    logger.info("sync_collection_started")
    start = datetime.now(timezone.utc)
    
    gdelt = collect_gdelt_articles()
    bluesky = collect_bluesky_posts()
    mastodon = collect_mastodon_posts()
    trending = get_trending_topics()
    
    duration = (datetime.now(timezone.utc) - start).total_seconds()
    logger.info("sync_collection_complete",
               gdelt=len(gdelt),
               bluesky=len(bluesky),
               mastodon=len(mastodon),
               trends=len(trending),
               duration_seconds=round(duration, 2))
    
    return gdelt, bluesky, mastodon, trending


async def run_pipeline_async() -> dict:
    """
    Run the complete Zeitgeist pipeline asynchronously.
    
    Uses async collectors for parallel signal acquisition.
    """
    start_time = datetime.now(timezone.utc)
    digest_id = generate_digest_id()
    edition = get_edition_name(start_time.hour)
    
    logger.info("pipeline_started", 
               digest_id=digest_id, 
               edition=edition, 
               async_mode=True)
    
    try:
        # =====================================================================
        # PHASE 1: SIGNAL ACQUISITION (Parallel)
        # =====================================================================
        gdelt_articles, bluesky_posts, mastodon_posts, trending = \
            await collect_signals_async()
        
        social_posts = bluesky_posts + mastodon_posts
        
        # =====================================================================
        # PHASE 2: PROCESSING
        # =====================================================================
        logger.info("phase_2_processing_started")
        
        all_articles = gdelt_articles
        deduped = deduplicate_articles(all_articles)
        logger.info("deduplication_complete", 
                    original=len(all_articles), 
                    unique=len(deduped))
        
        clusters = cluster_articles(deduped)
        logger.info("clustering_complete", num_clusters=len(clusters))
        
        scored_clusters = calculate_virality_scores(
            clusters, 
            bluesky_posts, 
            mastodon_posts,
            trending
        )
        
        clusters_with_arcs = match_clusters_to_story_arcs(
            scored_clusters,
            digest_id
        )
        
        clusters_with_divergence = calculate_narrative_divergence(
            clusters_with_arcs,
            gdelt_articles,
            social_posts
        )
        
        # =====================================================================
        # PHASE 3: GENERATION
        # =====================================================================
        logger.info("phase_3_generation_started")
        
        digest = generate_digest_narrative(
            digest_id=digest_id,
            edition=edition,
            clusters=clusters_with_divergence,
            trending=trending
        )
        
        verification = verify_generated_content(
            digest.get("summary", ""),
            sources=[{"text": str(a)} for a in gdelt_articles[:10]]
        )
        digest["verification"] = verification
        
        illustration = generate_illustration_concept(digest, clusters_with_divergence)
        digest["illustration_concept"] = illustration
        
        # Add metadata
        digest["generated_at"] = start_time.isoformat()
        digest["pipeline_version"] = "2.1.0"  # Async version
        digest["async_mode"] = True
        digest["signals"] = {
            "gdelt_articles": len(gdelt_articles),
            "bluesky_posts": len(bluesky_posts),
            "mastodon_posts": len(mastodon_posts),
            "trending_topics": len(trending),
        }
        
        digest["story_arcs"] = [
            c.get("story_arc") for c in clusters_with_divergence[:5]
            if c.get("story_arc")
        ]
        
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
        output_dir = Path(settings.OUTPUT_DIR)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"digest-{digest_id}.json"
        
        with open(output_file, "w") as f:
            json.dump(digest, f, indent=2, ensure_ascii=False, default=str)
        logger.info("digest_saved", path=str(output_file))
        
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
                    verified=verification.get("passed"),
                    async_mode=True)
        
        return digest
        
    except Exception as e:
        logger.exception("pipeline_failed", error=str(e))
        raise


def run_pipeline() -> dict:
    """
    Run the complete Zeitgeist pipeline.
    
    Automatically chooses async or sync mode based on settings.
    """
    if settings.USE_ASYNC_COLLECTORS:
        return asyncio.run(run_pipeline_async())
    else:
        return run_pipeline_sync()


def run_pipeline_sync() -> dict:
    """
    Run the complete Zeitgeist pipeline synchronously.
    
    Legacy sync mode for compatibility.
    """
    start_time = datetime.now(timezone.utc)
    digest_id = generate_digest_id()
    edition = get_edition_name(start_time.hour)
    
    logger.info("pipeline_started", 
               digest_id=digest_id, 
               edition=edition, 
               async_mode=False)
    
    try:
        # PHASE 1: SIGNAL ACQUISITION (Sequential)
        gdelt_articles, bluesky_posts, mastodon_posts, trending = \
            collect_signals_sync()
        
        social_posts = bluesky_posts + mastodon_posts
        
        # PHASE 2: PROCESSING
        all_articles = gdelt_articles
        deduped = deduplicate_articles(all_articles)
        clusters = cluster_articles(deduped)
        scored_clusters = calculate_virality_scores(
            clusters, bluesky_posts, mastodon_posts, trending
        )
        clusters_with_arcs = match_clusters_to_story_arcs(scored_clusters, digest_id)
        clusters_with_divergence = calculate_narrative_divergence(
            clusters_with_arcs, gdelt_articles, social_posts
        )
        
        # PHASE 3: GENERATION
        digest = generate_digest_narrative(
            digest_id=digest_id,
            edition=edition,
            clusters=clusters_with_divergence,
            trending=trending
        )
        
        verification = verify_generated_content(
            digest.get("summary", ""),
            sources=[{"text": str(a)} for a in gdelt_articles[:10]]
        )
        digest["verification"] = verification
        
        illustration = generate_illustration_concept(digest, clusters_with_divergence)
        digest["illustration_concept"] = illustration
        
        # Metadata
        digest["generated_at"] = start_time.isoformat()
        digest["pipeline_version"] = "2.1.0"
        digest["async_mode"] = False
        digest["signals"] = {
            "gdelt_articles": len(gdelt_articles),
            "bluesky_posts": len(bluesky_posts),
            "mastodon_posts": len(mastodon_posts),
            "trending_topics": len(trending),
        }
        
        # PHASE 4: OUTPUT
        output_dir = Path(settings.OUTPUT_DIR)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"digest-{digest_id}.json"
        
        with open(output_file, "w") as f:
            json.dump(digest, f, indent=2, ensure_ascii=False, default=str)
        
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        logger.info("pipeline_complete", 
                    digest_id=digest_id, 
                    duration_seconds=round(duration, 2))
        
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
    logging.basicConfig(level=logging.INFO)
    digest = run_pipeline()
    print(json.dumps(digest, indent=2, default=str))
