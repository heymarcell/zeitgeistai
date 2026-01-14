"""
Qdrant Vector Database Client

Provides Story Arc persistence using Qdrant's vector similarity search.
Story arcs are stored as embeddings (fingerprints) with metadata payloads.

Collections:
- story_arcs: Multi-day narrative tracking with semantic matching
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import structlog

from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.models import Distance, VectorParams, PointStruct

from src.config import settings

logger = structlog.get_logger()

# Collection configuration
STORY_ARCS_COLLECTION = "zeitgeist_story_arcs"
VECTOR_SIZE = 768  # Gemini gemini-embedding-001 with MRL

# Singleton client
_client: Optional[QdrantClient] = None


def get_qdrant_client() -> Optional[QdrantClient]:
    """
    Get or create Qdrant client singleton.
    
    Returns None if Qdrant is not configured.
    """
    global _client
    
    if _client is not None:
        return _client
    
    # Check if Qdrant is configured
    if not settings.QDRANT_URL or settings.QDRANT_URL == "http://localhost:6333":
        # Check if API key suggests cloud usage
        if not settings.QDRANT_API_KEY:
            logger.debug("qdrant_not_configured", url=settings.QDRANT_URL)
            return None
    
    try:
        _client = QdrantClient(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY if settings.QDRANT_API_KEY else None,
            timeout=30,
        )
        
        # Test connection
        _client.get_collections()
        logger.info("qdrant_connected", url=settings.QDRANT_URL)
        
        return _client
        
    except Exception as e:
        logger.warning("qdrant_connection_failed", error=str(e))
        _client = None
        return None


def ensure_collections() -> bool:
    """
    Ensure required collections exist in Qdrant.
    
    Returns True if collections are ready, False otherwise.
    """
    client = get_qdrant_client()
    if not client:
        return False
    
    try:
        # Check if story_arcs collection exists
        collections = client.get_collections()
        existing = [c.name for c in collections.collections]
        
        if STORY_ARCS_COLLECTION not in existing:
            client.create_collection(
                collection_name=STORY_ARCS_COLLECTION,
                vectors_config=VectorParams(
                    size=VECTOR_SIZE,
                    distance=Distance.COSINE,
                ),
            )
            logger.info("qdrant_collection_created", collection=STORY_ARCS_COLLECTION)
        
        return True
        
    except Exception as e:
        logger.error("qdrant_ensure_collections_failed", error=str(e))
        return False


def upsert_story_arc(arc: Dict[str, Any]) -> bool:
    """
    Insert or update a story arc in Qdrant.
    
    Args:
        arc: Story arc dictionary with arc_id, fingerprint, and metadata
        
    Returns:
        True if successful, False otherwise
    """
    client = get_qdrant_client()
    if not client:
        return False
    
    try:
        arc_id = arc.get("arc_id", "")
        fingerprint = arc.get("fingerprint", [])
        
        # Ensure fingerprint has correct dimension
        if len(fingerprint) != VECTOR_SIZE:
            # Pad or truncate
            if len(fingerprint) < VECTOR_SIZE:
                fingerprint = fingerprint + [0.0] * (VECTOR_SIZE - len(fingerprint))
            else:
                fingerprint = fingerprint[:VECTOR_SIZE]
        
        # Prepare payload (all metadata except fingerprint)
        payload = {k: v for k, v in arc.items() if k != "fingerprint"}
        
        # Convert lists to JSON-serializable format
        if "velocity_history" in payload:
            payload["velocity_history"] = list(payload["velocity_history"])
        
        point = PointStruct(
            id=arc_id,  # Use arc_id as point ID
            vector=fingerprint,
            payload=payload,
        )
        
        client.upsert(
            collection_name=STORY_ARCS_COLLECTION,
            points=[point],
        )
        
        logger.debug("qdrant_arc_upserted", arc_id=arc_id)
        return True
        
    except Exception as e:
        logger.error("qdrant_upsert_failed", arc_id=arc.get("arc_id"), error=str(e))
        return False


def search_similar_arcs(
    fingerprint: List[float],
    threshold: float = 0.85,
    limit: int = 5
) -> List[Dict[str, Any]]:
    """
    Search for story arcs similar to the given fingerprint.
    
    Args:
        fingerprint: Embedding vector to search for
        threshold: Minimum similarity score (0-1)
        limit: Maximum results to return
        
    Returns:
        List of matching arcs with similarity scores
    """
    client = get_qdrant_client()
    if not client:
        return []
    
    try:
        # Ensure fingerprint has correct dimension
        if len(fingerprint) != VECTOR_SIZE:
            if len(fingerprint) < VECTOR_SIZE:
                fingerprint = fingerprint + [0.0] * (VECTOR_SIZE - len(fingerprint))
            else:
                fingerprint = fingerprint[:VECTOR_SIZE]
        
        results = client.search(
            collection_name=STORY_ARCS_COLLECTION,
            query_vector=fingerprint,
            limit=limit,
            score_threshold=threshold,
        )
        
        arcs = []
        for hit in results:
            arc = hit.payload.copy()
            arc["fingerprint"] = []  # Don't include full vector in results
            arc["similarity"] = hit.score
            arcs.append(arc)
        
        logger.debug("qdrant_search_complete", matches=len(arcs))
        return arcs
        
    except Exception as e:
        logger.error("qdrant_search_failed", error=str(e))
        return []


def get_all_arcs(max_age_hours: int = 168) -> Dict[str, Dict[str, Any]]:
    """
    Get all story arcs from Qdrant.
    
    Args:
        max_age_hours: Only return arcs updated within this many hours
        
    Returns:
        Dictionary of arc_id -> arc data
    """
    client = get_qdrant_client()
    if not client:
        return {}
    
    try:
        # Scroll through all points
        arcs = {}
        offset = None
        
        while True:
            results, offset = client.scroll(
                collection_name=STORY_ARCS_COLLECTION,
                limit=100,
                offset=offset,
                with_payload=True,
                with_vectors=True,
            )
            
            for point in results:
                arc = point.payload.copy()
                arc["arc_id"] = point.id
                arc["fingerprint"] = list(point.vector) if point.vector else []
                arcs[point.id] = arc
            
            if offset is None:
                break
        
        logger.debug("qdrant_get_all_complete", count=len(arcs))
        return arcs
        
    except Exception as e:
        logger.error("qdrant_get_all_failed", error=str(e))
        return {}


def delete_arc(arc_id: str) -> bool:
    """Delete a story arc from Qdrant."""
    client = get_qdrant_client()
    if not client:
        return False
    
    try:
        client.delete(
            collection_name=STORY_ARCS_COLLECTION,
            points_selector=models.PointIdsList(points=[arc_id]),
        )
        logger.debug("qdrant_arc_deleted", arc_id=arc_id)
        return True
        
    except Exception as e:
        logger.error("qdrant_delete_failed", arc_id=arc_id, error=str(e))
        return False


def cleanup_old_arcs(max_age_days: int = 7) -> int:
    """
    Remove story arcs older than max_age_days.
    
    Returns number of arcs deleted.
    """
    client = get_qdrant_client()
    if not client:
        return 0
    
    try:
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(days=max_age_days)).isoformat()
        
        # Get all arcs and filter by age
        arcs = get_all_arcs()
        to_delete = []
        
        for arc_id, arc in arcs.items():
            last_seen = arc.get("last_seen_at", "")
            if last_seen and last_seen < cutoff:
                to_delete.append(arc_id)
        
        if to_delete:
            client.delete(
                collection_name=STORY_ARCS_COLLECTION,
                points_selector=models.PointIdsList(points=to_delete),
            )
            logger.info("qdrant_cleanup_complete", deleted=len(to_delete))
        
        return len(to_delete)
        
    except Exception as e:
        logger.error("qdrant_cleanup_failed", error=str(e))
        return 0


if __name__ == "__main__":
    # Test Qdrant connection
    import logging
    logging.basicConfig(level=logging.INFO)
    
    client = get_qdrant_client()
    if client:
        print("✓ Qdrant connected")
        if ensure_collections():
            print(f"✓ Collection '{STORY_ARCS_COLLECTION}' ready")
    else:
        print("✗ Qdrant not configured or unavailable")
