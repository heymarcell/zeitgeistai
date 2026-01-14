"""
Async GDELT BigQuery Collector

Wraps BigQuery client in async executor for non-blocking operation.
BigQuery Python client is synchronous, so we use run_in_executor.
"""

import asyncio
from typing import List, Dict, Any
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
import structlog

from src.config import settings

logger = structlog.get_logger()

# Thread pool for running sync BigQuery calls
_executor = ThreadPoolExecutor(max_workers=2)


async def collect_gdelt_articles_async() -> List[Dict[str, Any]]:
    """
    Asynchronously collect articles from GDELT BigQuery.
    
    Uses thread pool executor since BigQuery client is synchronous.
    """
    logger.info("async_gdelt_collection_started",
                lookback_hours=settings.GDELT_LOOKBACK_HOURS)
    
    try:
        loop = asyncio.get_event_loop()
        articles = await loop.run_in_executor(_executor, _sync_collect_gdelt)
        
        logger.info("async_gdelt_collection_complete", count=len(articles))
        return articles
        
    except Exception as e:
        logger.error("async_gdelt_collection_failed", error=str(e))
        return []


def _sync_collect_gdelt() -> List[Dict[str, Any]]:
    """Synchronous GDELT collection (runs in thread pool)."""
    from google.cloud import bigquery
    from google.oauth2 import service_account
    
    # Initialize client
    if settings.GOOGLE_APPLICATION_CREDENTIALS:
        credentials = service_account.Credentials.from_service_account_file(
            settings.GOOGLE_APPLICATION_CREDENTIALS
        )
        client = bigquery.Client(credentials=credentials)
    else:
        client = bigquery.Client()
    
    # Calculate time window
    now = datetime.now(timezone.utc)
    lookback = now - timedelta(hours=settings.GDELT_LOOKBACK_HOURS)
    
    # Optimized query
    query = f"""
    SELECT 
        DocumentIdentifier as url,
        V2Themes as themes,
        V2Tone as tone,
        DATE as date,
        V2Locations as locations,
        V2Persons as persons,
        V2Organizations as organizations
    FROM `gdelt-bq.gdeltv2.gkg_partitioned`
    WHERE 
        _PARTITIONTIME >= TIMESTAMP('{lookback.strftime('%Y-%m-%d %H:%M:%S')}')
        AND _PARTITIONTIME < TIMESTAMP('{now.strftime('%Y-%m-%d %H:%M:%S')}')
        AND V2Themes IS NOT NULL
        AND DocumentIdentifier IS NOT NULL
    LIMIT {settings.GDELT_MAX_ARTICLES}
    """
    
    query_job = client.query(query)
    results = query_job.result()
    
    articles = []
    for row in results:
        article = {
            "url": row.url,
            "themes": _parse_gdelt_field(row.themes),
            "tone": _parse_tone(row.tone),
            "date": str(row.date),
            "locations": _parse_gdelt_field(row.locations),
            "persons": _parse_gdelt_field(row.persons),
            "organizations": _parse_gdelt_field(row.organizations),
            "source": "gdelt"
        }
        articles.append(article)
    
    return articles


def _parse_gdelt_field(field: str) -> List[str]:
    """Parse GDELT semicolon-separated field into list."""
    if not field:
        return []
    items = field.split(";")
    return [item.split(",")[0].strip() for item in items if item.strip()]


def _parse_tone(tone_str: str) -> Dict[str, float]:
    """Parse GDELT V2Tone field."""
    if not tone_str:
        return {"average": 0.0}
    
    try:
        parts = tone_str.split(",")
        return {
            "average": float(parts[0]) if len(parts) > 0 else 0.0,
            "positive": float(parts[1]) if len(parts) > 1 else 0.0,
            "negative": float(parts[2]) if len(parts) > 2 else 0.0,
            "polarity": float(parts[3]) if len(parts) > 3 else 0.0,
        }
    except (ValueError, IndexError):
        return {"average": 0.0}


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    
    async def test():
        articles = await collect_gdelt_articles_async()
        print(f"Got {len(articles)} articles")
        if articles:
            print(f"Sample: {articles[0]}")
    
    asyncio.run(test())
