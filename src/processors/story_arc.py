"""
Story Arc Registry Module

Tracks multi-day narratives and maintains story continuity.
Stories can span days/weeks and should be recognized as ongoing.

Storage: Uses Qdrant for persistence with file-based fallback.

Story Phases:
- EMERGING: First 24 hours, velocity increasing
- DEVELOPING: 24-72 hours, sustained coverage
- PEAK: Velocity at local maximum
- FADING: Velocity declining >50% from peak
"""

import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional
import numpy as np
import structlog

from src.config import settings

logger = structlog.get_logger()

# Story Arc file storage (fallback)
STORY_ARC_FILE = Path(settings.OUTPUT_DIR) / "story_arcs.json"

# Similarity threshold for matching to existing story
SIMILARITY_THRESHOLD = 0.85

# Vector dimension for Qdrant (Gemini gemini-embedding-001 with MRL)
VECTOR_SIZE = 768


class StoryArcRegistry:
    """
    Maintains a registry of ongoing story arcs.
    
    Uses Qdrant for persistence when available, falls back to file-based storage.
    
    Each story arc tracks:
    - Semantic fingerprint (centroid embedding)
    - Timeline of appearances
    - Core entities
    - Narrative phase
    """
    
    def __init__(self):
        self.arcs: Dict[str, Dict[str, Any]] = {}
        self._use_qdrant = self._init_qdrant()
        self._load_arcs()
    
    def _init_qdrant(self) -> bool:
        """Initialize Qdrant connection if available."""
        try:
            from src.storage.qdrant import get_qdrant_client, ensure_collections
            
            client = get_qdrant_client()
            if client and ensure_collections():
                logger.info("story_arc_using_qdrant")
                return True
        except Exception as e:
            logger.debug("story_arc_qdrant_init_failed", error=str(e))
        
        logger.info("story_arc_using_file_storage")
        return False
    
    def _load_arcs(self):
        """Load existing story arcs from storage."""
        if self._use_qdrant:
            self._load_from_qdrant()
        else:
            self._load_from_file()
    
    def _load_from_qdrant(self):
        """Load arcs from Qdrant."""
        try:
            from src.storage.qdrant import get_all_arcs
            self.arcs = get_all_arcs()
            logger.info("story_arcs_loaded_qdrant", count=len(self.arcs))
        except Exception as e:
            logger.warning("story_arcs_qdrant_load_failed", error=str(e))
            self._load_from_file()  # Fallback
    
    def _load_from_file(self):
        """Load arcs from JSON file."""
        try:
            if STORY_ARC_FILE.exists():
                with open(STORY_ARC_FILE, 'r') as f:
                    data = json.load(f)
                    self.arcs = data.get("arcs", {})
                logger.info("story_arcs_loaded_file", count=len(self.arcs))
        except Exception as e:
            logger.warning("story_arcs_file_load_failed", error=str(e))
            self.arcs = {}
    
    def _save_arc(self, arc: Dict[str, Any]):
        """Save a single arc to storage."""
        if self._use_qdrant:
            self._save_to_qdrant(arc)
        else:
            self._save_to_file()
    
    def _save_to_qdrant(self, arc: Dict[str, Any]):
        """Save arc to Qdrant."""
        try:
            from src.storage.qdrant import upsert_story_arc
            upsert_story_arc(arc)
            logger.debug("story_arc_saved_qdrant", arc_id=arc.get("arc_id"))
        except Exception as e:
            logger.error("story_arc_qdrant_save_failed", error=str(e))
            self._save_to_file()  # Fallback
    
    def _save_to_file(self):
        """Save all arcs to JSON file."""
        try:
            STORY_ARC_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(STORY_ARC_FILE, 'w') as f:
                json.dump({
                    "arcs": self.arcs, 
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }, f, indent=2)
            logger.debug("story_arcs_saved_file", count=len(self.arcs))
        except Exception as e:
            logger.error("story_arcs_file_save_failed", error=str(e))
    
    def match_or_create(
        self,
        cluster: Dict[str, Any],
        digest_id: str
    ) -> Dict[str, Any]:
        """
        Match a cluster to an existing story arc or create a new one.
        
        Uses vector similarity search when Qdrant is available.
        """
        centroid = cluster.get("centroid", [])
        
        if not centroid:
            return self._create_new_arc(cluster, digest_id)
        
        # Use Qdrant similarity search if available
        if self._use_qdrant:
            return self._match_with_qdrant(cluster, digest_id, centroid)
        
        # Fallback to in-memory matching
        return self._match_in_memory(cluster, digest_id, centroid)
    
    def _match_with_qdrant(
        self,
        cluster: Dict[str, Any],
        digest_id: str,
        centroid: List[float]
    ) -> Dict[str, Any]:
        """Match using Qdrant vector search."""
        try:
            from src.storage.qdrant import search_similar_arcs
            
            # Ensure centroid has correct dimension
            if len(centroid) < VECTOR_SIZE:
                centroid = centroid + [0.0] * (VECTOR_SIZE - len(centroid))
            elif len(centroid) > VECTOR_SIZE:
                centroid = centroid[:VECTOR_SIZE]
            
            matches = search_similar_arcs(
                fingerprint=centroid,
                threshold=SIMILARITY_THRESHOLD,
                limit=1
            )
            
            if matches:
                best_match = matches[0]
                arc_id = best_match.get("arc_id")
                similarity = best_match.get("similarity", 0)
                
                # Update in-memory cache
                if arc_id not in self.arcs:
                    self.arcs[arc_id] = best_match
                
                return self._update_existing_arc(
                    arc_id, cluster, digest_id, similarity
                )
                
        except Exception as e:
            logger.warning("qdrant_match_failed", error=str(e))
        
        return self._create_new_arc(cluster, digest_id)
    
    def _match_in_memory(
        self,
        cluster: Dict[str, Any],
        digest_id: str,
        centroid: List[float]
    ) -> Dict[str, Any]:
        """Match using in-memory cosine similarity."""
        best_match = None
        best_similarity = 0.0
        
        for arc_id, arc in self.arcs.items():
            arc_fingerprint = arc.get("fingerprint", [])
            if not arc_fingerprint:
                continue
            
            similarity = self._cosine_similarity(centroid, arc_fingerprint)
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = arc_id
        
        if best_match and best_similarity >= SIMILARITY_THRESHOLD:
            return self._update_existing_arc(
                best_match, cluster, digest_id, best_similarity
            )
        
        return self._create_new_arc(cluster, digest_id)
    
    def _create_new_arc(
        self,
        cluster: Dict[str, Any],
        digest_id: str
    ) -> Dict[str, Any]:
        """Create a new story arc from cluster."""
        arc_id = str(uuid.uuid4())[:8]
        now = datetime.now(timezone.utc).isoformat()
        
        topics = cluster.get("topics", [])
        centroid = cluster.get("centroid", [])
        
        # Normalize centroid to expected size
        if len(centroid) < VECTOR_SIZE:
            centroid = centroid + [0.0] * (VECTOR_SIZE - len(centroid))
        elif len(centroid) > VECTOR_SIZE:
            centroid = centroid[:VECTOR_SIZE]
        
        arc = {
            "arc_id": arc_id,
            "fingerprint": centroid,
            "canonical_title": self._generate_title(topics),
            "core_entities": topics[:5],
            "first_seen_at": now,
            "last_seen_at": now,
            "digests": [digest_id],
            "phase": "EMERGING",
            "peak_velocity": cluster.get("virality_score", 0),
            "velocity_history": [cluster.get("virality_score", 0)],
        }
        
        self.arcs[arc_id] = arc
        self._save_arc(arc)
        
        logger.info("story_arc_created",
                    arc_id=arc_id,
                    title=arc["canonical_title"],
                    phase=arc["phase"])
        
        return {"arc": arc, "is_new": True, "similarity": 1.0}
    
    def _update_existing_arc(
        self,
        arc_id: str,
        cluster: Dict[str, Any],
        digest_id: str,
        similarity: float
    ) -> Dict[str, Any]:
        """Update an existing story arc with new data."""
        arc = self.arcs.get(arc_id, {})
        if not arc:
            return self._create_new_arc(cluster, digest_id)
        
        now = datetime.now(timezone.utc).isoformat()
        
        # Update timing
        arc["last_seen_at"] = now
        if digest_id not in arc.get("digests", []):
            arc.setdefault("digests", []).append(digest_id)
        
        # Update velocity history
        current_velocity = cluster.get("virality_score", 0)
        arc.setdefault("velocity_history", []).append(current_velocity)
        
        # Update peak
        if current_velocity > arc.get("peak_velocity", 0):
            arc["peak_velocity"] = current_velocity
        
        # Update fingerprint with exponential moving average
        old_fp = np.array(arc.get("fingerprint", []))
        new_fp = np.array(cluster.get("centroid", []))
        
        # Normalize sizes
        if len(new_fp) < VECTOR_SIZE:
            new_fp = np.pad(new_fp, (0, VECTOR_SIZE - len(new_fp)))
        elif len(new_fp) > VECTOR_SIZE:
            new_fp = new_fp[:VECTOR_SIZE]
        
        if len(old_fp) == len(new_fp) and len(old_fp) > 0:
            arc["fingerprint"] = (0.7 * old_fp + 0.3 * new_fp).tolist()
        
        # Update phase
        arc["phase"] = self._determine_phase(arc)
        
        self.arcs[arc_id] = arc
        self._save_arc(arc)
        
        logger.info("story_arc_updated",
                    arc_id=arc_id,
                    similarity=round(similarity, 3),
                    phase=arc["phase"],
                    appearances=len(arc.get("digests", [])))
        
        return {"arc": arc, "is_new": False, "similarity": similarity}
    
    def _determine_phase(self, arc: Dict[str, Any]) -> str:
        """Determine the narrative phase of a story arc."""
        first_seen = arc.get("first_seen_at", "")
        if not first_seen:
            return "EMERGING"
        
        try:
            first_seen_dt = datetime.fromisoformat(first_seen.replace("Z", "+00:00"))
            age_hours = (datetime.now(timezone.utc) - first_seen_dt).total_seconds() / 3600
        except:
            return "EMERGING"
        
        velocities = arc.get("velocity_history", [])
        peak_velocity = arc.get("peak_velocity", 0)
        current_velocity = velocities[-1] if velocities else 0
        
        if age_hours < 24:
            return "EMERGING"
        elif age_hours < 72:
            if current_velocity >= peak_velocity * 0.9:
                return "PEAK"
            return "DEVELOPING"
        else:
            if current_velocity < peak_velocity * 0.5:
                return "FADING"
            return "DEVELOPING"
    
    def _generate_title(self, topics: List[str]) -> str:
        """Generate a canonical title from topics."""
        if not topics:
            return "Untitled Story"
        clean = [t.replace("_", " ").title() for t in topics[:3]]
        return " - ".join(clean)
    
    @staticmethod
    def _cosine_similarity(a: List[float], b: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        a = np.array(a)
        b = np.array(b)
        
        if len(a) != len(b) or len(a) == 0:
            return 0.0
        
        dot = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return float(dot / (norm_a * norm_b))
    
    def get_active_arcs(self, max_age_hours: int = 72) -> List[Dict[str, Any]]:
        """Get all active story arcs (not fading) from recent hours."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
        
        active = []
        for arc in self.arcs.values():
            last_seen = arc.get("last_seen_at", "")
            if not last_seen:
                continue
            try:
                last_seen_dt = datetime.fromisoformat(last_seen.replace("Z", "+00:00"))
                if last_seen_dt >= cutoff and arc.get("phase") != "FADING":
                    active.append(arc)
            except:
                continue
        
        return sorted(active, key=lambda x: x.get("peak_velocity", 0), reverse=True)
    
    def cleanup_old_arcs(self, max_age_days: int = 7):
        """Remove story arcs older than max_age_days."""
        if self._use_qdrant:
            try:
                from src.storage.qdrant import cleanup_old_arcs
                deleted = cleanup_old_arcs(max_age_days)
                if deleted > 0:
                    self._load_arcs()  # Reload from Qdrant
                return
            except Exception as e:
                logger.error("qdrant_cleanup_failed", error=str(e))
        
        # File-based cleanup
        cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
        
        to_remove = []
        for arc_id, arc in self.arcs.items():
            last_seen = arc.get("last_seen_at", "")
            if not last_seen:
                continue
            try:
                last_seen_dt = datetime.fromisoformat(last_seen.replace("Z", "+00:00"))
                if last_seen_dt < cutoff:
                    to_remove.append(arc_id)
            except:
                continue
        
        for arc_id in to_remove:
            del self.arcs[arc_id]
        
        if to_remove:
            self._save_to_file()
            logger.info("story_arcs_cleaned", removed=len(to_remove))


# Global registry instance
story_arc_registry = StoryArcRegistry()


def match_clusters_to_story_arcs(
    clusters: List[Dict[str, Any]],
    digest_id: str
) -> List[Dict[str, Any]]:
    """
    Match all clusters to story arcs and add arc metadata.
    
    Args:
        clusters: List of article clusters
        digest_id: Current digest ID
        
    Returns:
        Clusters with story_arc field added
    """
    logger.info("story_arc_matching_started", num_clusters=len(clusters))
    
    for cluster in clusters:
        result = story_arc_registry.match_or_create(cluster, digest_id)
        cluster["story_arc"] = {
            "arc_id": result["arc"]["arc_id"],
            "title": result["arc"]["canonical_title"],
            "phase": result["arc"]["phase"],
            "is_new": result["is_new"],
            "similarity": result["similarity"],
            "appearances": len(result["arc"].get("digests", [])),
        }
    
    logger.info("story_arc_matching_complete")
    return clusters


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    
    # Test story arc registry
    test_clusters = [
        {
            "cluster_id": 0,
            "topics": ["NATO", "SUMMIT", "DEFENSE"],
            "centroid": [0.1] * VECTOR_SIZE,
            "virality_score": 0.85
        }
    ]
    
    result = match_clusters_to_story_arcs(test_clusters, "2026-01-14-20")
    print(f"Story arc: {result[0]['story_arc']}")
    print(f"Using Qdrant: {story_arc_registry._use_qdrant}")
