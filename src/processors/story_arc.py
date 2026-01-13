"""
Story Arc Registry Module

Tracks multi-day narratives and maintains story continuity.
Stories can span days/weeks and should be recognized as ongoing.

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

# Story Arc storage path
STORY_ARC_FILE = Path(settings.OUTPUT_DIR) / "story_arcs.json"

# Similarity threshold for matching to existing story
SIMILARITY_THRESHOLD = 0.85


class StoryArcRegistry:
    """
    Maintains a registry of ongoing story arcs.
    
    Each story arc tracks:
    - Semantic fingerprint (centroid embedding)
    - Timeline of appearances
    - Core entities
    - Narrative phase
    """
    
    def __init__(self):
        self.arcs: Dict[str, Dict[str, Any]] = {}
        self._load_arcs()
    
    def _load_arcs(self):
        """Load existing story arcs from disk."""
        try:
            if STORY_ARC_FILE.exists():
                with open(STORY_ARC_FILE, 'r') as f:
                    data = json.load(f)
                    self.arcs = data.get("arcs", {})
                logger.info("story_arcs_loaded", count=len(self.arcs))
        except Exception as e:
            logger.warning("story_arcs_load_failed", error=str(e))
            self.arcs = {}
    
    def _save_arcs(self):
        """Save story arcs to disk."""
        try:
            STORY_ARC_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(STORY_ARC_FILE, 'w') as f:
                json.dump({"arcs": self.arcs, "updated_at": datetime.now(timezone.utc).isoformat()}, f, indent=2)
            logger.debug("story_arcs_saved", count=len(self.arcs))
        except Exception as e:
            logger.error("story_arcs_save_failed", error=str(e))
    
    def match_or_create(
        self,
        cluster: Dict[str, Any],
        digest_id: str
    ) -> Dict[str, Any]:
        """
        Match a cluster to an existing story arc or create a new one.
        
        Args:
            cluster: Article cluster with centroid embedding
            digest_id: Current digest ID for tracking
            
        Returns:
            Story arc dict with match info
        """
        centroid = cluster.get("centroid", [])
        if not centroid:
            return self._create_new_arc(cluster, digest_id)
        
        # Find best matching existing arc
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
        
        # Check if match exceeds threshold
        if best_match and best_similarity >= SIMILARITY_THRESHOLD:
            return self._update_existing_arc(best_match, cluster, digest_id, best_similarity)
        
        return self._create_new_arc(cluster, digest_id)
    
    def _create_new_arc(self, cluster: Dict[str, Any], digest_id: str) -> Dict[str, Any]:
        """Create a new story arc from cluster."""
        arc_id = str(uuid.uuid4())[:8]
        now = datetime.now(timezone.utc).isoformat()
        
        # Extract core entities from topics
        topics = cluster.get("topics", [])
        
        arc = {
            "arc_id": arc_id,
            "fingerprint": cluster.get("centroid", []),
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
        self._save_arcs()
        
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
        arc = self.arcs[arc_id]
        now = datetime.now(timezone.utc).isoformat()
        
        # Update timing
        arc["last_seen_at"] = now
        if digest_id not in arc["digests"]:
            arc["digests"].append(digest_id)
        
        # Update velocity history
        current_velocity = cluster.get("virality_score", 0)
        arc["velocity_history"].append(current_velocity)
        
        # Update peak
        if current_velocity > arc.get("peak_velocity", 0):
            arc["peak_velocity"] = current_velocity
        
        # Update fingerprint with exponential moving average
        old_fp = np.array(arc["fingerprint"])
        new_fp = np.array(cluster.get("centroid", []))
        if len(old_fp) == len(new_fp):
            arc["fingerprint"] = (0.7 * old_fp + 0.3 * new_fp).tolist()
        
        # Update phase
        arc["phase"] = self._determine_phase(arc)
        
        self._save_arcs()
        
        logger.info("story_arc_updated",
                    arc_id=arc_id,
                    similarity=round(similarity, 3),
                    phase=arc["phase"],
                    appearances=len(arc["digests"]))
        
        return {"arc": arc, "is_new": False, "similarity": similarity}
    
    def _determine_phase(self, arc: Dict[str, Any]) -> str:
        """Determine the narrative phase of a story arc."""
        first_seen = datetime.fromisoformat(arc["first_seen_at"].replace("Z", "+00:00"))
        age_hours = (datetime.now(timezone.utc) - first_seen).total_seconds() / 3600
        
        velocities = arc.get("velocity_history", [])
        peak_velocity = arc.get("peak_velocity", 0)
        current_velocity = velocities[-1] if velocities else 0
        
        # Phase logic from spec
        if age_hours < 24:
            return "EMERGING"
        elif age_hours < 72:
            # Check if at peak
            if current_velocity >= peak_velocity * 0.9:
                return "PEAK"
            return "DEVELOPING"
        else:
            # Check if fading
            if current_velocity < peak_velocity * 0.5:
                return "FADING"
            return "DEVELOPING"
    
    def _generate_title(self, topics: List[str]) -> str:
        """Generate a canonical title from topics."""
        if not topics:
            return "Untitled Story"
        
        # Clean up topics
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
            last_seen = datetime.fromisoformat(arc["last_seen_at"].replace("Z", "+00:00"))
            if last_seen >= cutoff and arc.get("phase") != "FADING":
                active.append(arc)
        
        return sorted(active, key=lambda x: x.get("peak_velocity", 0), reverse=True)
    
    def cleanup_old_arcs(self, max_age_days: int = 7):
        """Remove story arcs older than max_age_days."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
        
        to_remove = []
        for arc_id, arc in self.arcs.items():
            last_seen = datetime.fromisoformat(arc["last_seen_at"].replace("Z", "+00:00"))
            if last_seen < cutoff:
                to_remove.append(arc_id)
        
        for arc_id in to_remove:
            del self.arcs[arc_id]
        
        if to_remove:
            self._save_arcs()
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
            "appearances": len(result["arc"]["digests"]),
        }
    
    logger.info("story_arc_matching_complete")
    return clusters


if __name__ == "__main__":
    # Test story arc registry
    import logging
    logging.basicConfig(level=logging.INFO)
    
    # Create test clusters
    test_clusters = [
        {
            "cluster_id": 0,
            "topics": ["NATO", "SUMMIT", "DEFENSE"],
            "centroid": [0.1] * 100,
            "virality_score": 0.85
        }
    ]
    
    # Match to arcs
    result = match_clusters_to_story_arcs(test_clusters, "2026-01-13-14")
    print(f"Story arc: {result[0]['story_arc']}")
