"""
GDELT BigQuery Collector

Fetches news articles from GDELT Global Knowledge Graph using BigQuery.
Uses the free tier (1 TB/month) with optimized queries.
"""

import os
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any
import structlog

from google.cloud import bigquery
from google.oauth2 import service_account

from src.config import settings

logger = structlog.get_logger()


def get_bigquery_client() -> bigquery.Client:
    """Initialize BigQuery client with credentials."""
    if settings.GOOGLE_APPLICATION_CREDENTIALS:
        credentials = service_account.Credentials.from_service_account_file(
            settings.GOOGLE_APPLICATION_CREDENTIALS
        )
        return bigquery.Client(credentials=credentials)
    return bigquery.Client()


def collect_gdelt_articles() -> List[Dict[str, Any]]:
    """
    Collect recent articles from GDELT Global Knowledge Graph.
    
    Returns:
        List of article dictionaries with:
        - url: Article URL
        - themes: List of V2 themes
        - tone: Average tone score
        - date: Publication date
        - locations: Mentioned locations
        - persons: Mentioned persons
        - organizations: Mentioned organizations
    """
    logger.info("gdelt_collection_started", 
                lookback_hours=settings.GDELT_LOOKBACK_HOURS)
    
    client = get_bigquery_client()
    
    # Calculate time window
    now = datetime.now(timezone.utc)
    lookback = now - timedelta(hours=settings.GDELT_LOOKBACK_HOURS)
    
    # Optimized query - select only needed columns, use partitions
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
    
    try:
        query_job = client.query(query)
        results = query_job.result()
        
        articles = []
        for row in results:
            article = {
                "url": row.url,
                "themes": parse_gdelt_field(row.themes),
                "tone": parse_tone(row.tone),
                "date": str(row.date),
                "locations": parse_gdelt_field(row.locations),
                "persons": parse_gdelt_field(row.persons),
                "organizations": parse_gdelt_field(row.organizations),
                "source": "gdelt"
            }
            articles.append(article)
        
        logger.info("gdelt_collection_complete", count=len(articles))
        return articles
        
    except Exception as e:
        logger.error("gdelt_collection_failed", error=str(e))
        return []


def parse_gdelt_field(field: str) -> List[str]:
    """Parse GDELT semicolon-separated field into list."""
    if not field:
        return []
    # V2 format uses semicolons to separate, commas for sub-fields
    items = field.split(";")
    # Extract first part of each item (the main value)
    return [item.split(",")[0].strip() for item in items if item.strip()]


def parse_tone(tone_str: str) -> Dict[str, float]:
    """
    Parse GDELT V2Tone field.
    
    Format: Tone,PositiveScore,NegativeScore,Polarity,ActivityDensity,SelfGroupDensity
    """
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
    # Test collection
    import logging
    logging.basicConfig(level=logging.INFO)
    
    articles = collect_gdelt_articles()
    print(f"Collected {len(articles)} articles")
    if articles:
        print(f"Sample: {articles[0]}")
