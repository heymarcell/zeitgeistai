"""
Clustering Module

Groups related articles using HDBSCAN with UMAP dimensionality reduction.
"""

from typing import List, Dict, Any, Tuple
import numpy as np
import structlog

from sentence_transformers import SentenceTransformer
import hdbscan
import umap

from src.config import settings

logger = structlog.get_logger()

# Lazy-load embedding model
_embedding_model = None


def get_embedding_model() -> SentenceTransformer:
    """Get or create embedding model (lazy loading)."""
    global _embedding_model
    if _embedding_model is None:
        logger.info("loading_embedding_model", model=settings.EMBEDDING_MODEL)
        _embedding_model = SentenceTransformer(settings.EMBEDDING_MODEL)
    return _embedding_model


def cluster_articles(articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Cluster articles by semantic similarity.
    
    Uses sentence-transformers for embeddings, UMAP for dimensionality
    reduction, and HDBSCAN for clustering.
    
    Args:
        articles: List of article dictionaries with 'themes' or 'url' fields
        
    Returns:
        List of cluster dictionaries, each containing:
        - cluster_id: Cluster identifier
        - articles: List of articles in the cluster
        - centroid: Cluster centroid embedding
        - topics: Dominant topics in the cluster
    """
    if not articles:
        return []
    
    logger.info("clustering_started", num_articles=len(articles))
    
    # Create text representations for embedding
    texts = []
    for article in articles:
        # Combine themes into text for embedding
        themes = article.get("themes", [])
        if isinstance(themes, list):
            text = " ".join(themes[:10])  # Use top 10 themes
        else:
            text = str(themes)
        
        # Add URL domain as context
        url = article.get("url", "")
        if url:
            domain = url.split("/")[2] if len(url.split("/")) > 2 else ""
            text = f"{domain} {text}"
        
        texts.append(text if text.strip() else "unknown")
    
    # Generate embeddings
    model = get_embedding_model()
    embeddings = model.encode(texts, show_progress_bar=False)
    logger.info("embeddings_generated", shape=embeddings.shape)
    
    # Apply UMAP for dimensionality reduction
    if len(embeddings) > settings.UMAP_N_COMPONENTS:
        reducer = umap.UMAP(
            n_components=min(settings.UMAP_N_COMPONENTS, len(embeddings) - 1),
            metric='cosine',
            random_state=42
        )
        embeddings_reduced = reducer.fit_transform(embeddings)
        logger.info("umap_applied", 
                    original_dims=embeddings.shape[1],
                    reduced_dims=embeddings_reduced.shape[1])
    else:
        embeddings_reduced = embeddings
    
    # Apply HDBSCAN clustering
    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=settings.MIN_CLUSTER_SIZE,
        min_samples=settings.MIN_SAMPLES,
        metric='euclidean'
    )
    cluster_labels = clusterer.fit_predict(embeddings_reduced)
    
    # Group articles by cluster
    clusters = {}
    for idx, label in enumerate(cluster_labels):
        if label == -1:  # Skip noise
            continue
        if label not in clusters:
            clusters[label] = {
                "cluster_id": label,
                "articles": [],
                "embeddings": []
            }
        clusters[label]["articles"].append(articles[idx])
        clusters[label]["embeddings"].append(embeddings[idx])
    
    # Calculate cluster metadata
    result = []
    for cluster_id, cluster_data in clusters.items():
        # Calculate centroid
        cluster_embeddings = np.array(cluster_data["embeddings"])
        centroid = np.mean(cluster_embeddings, axis=0)
        
        # Extract dominant topics
        all_themes = []
        for article in cluster_data["articles"]:
            themes = article.get("themes", [])
            if isinstance(themes, list):
                all_themes.extend(themes)
        
        # Count theme occurrences
        theme_counts = {}
        for theme in all_themes:
            theme_counts[theme] = theme_counts.get(theme, 0) + 1
        
        top_themes = sorted(theme_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        
        result.append({
            "cluster_id": cluster_id,
            "articles": cluster_data["articles"],
            "centroid": centroid.tolist(),
            "topics": [t[0] for t in top_themes],
            "size": len(cluster_data["articles"])
        })
    
    # Sort by cluster size
    result.sort(key=lambda x: x["size"], reverse=True)
    
    logger.info("clustering_complete", 
                num_clusters=len(result),
                noise_count=sum(1 for l in cluster_labels if l == -1))
    
    return result


if __name__ == "__main__":
    # Test clustering
    import logging
    logging.basicConfig(level=logging.INFO)
    
    # Sample data
    test_articles = [
        {"url": "https://example.com/1", "themes": ["POLITICS", "NATO", "SUMMIT"]},
        {"url": "https://example.com/2", "themes": ["POLITICS", "NATO", "DEFENSE"]},
        {"url": "https://example.com/3", "themes": ["TECHNOLOGY", "AI", "GOOGLE"]},
    ]
    
    clusters = cluster_articles(test_articles)
    print(f"Found {len(clusters)} clusters")
    for c in clusters:
        print(f"Cluster {c['cluster_id']}: {c['size']} articles, topics: {c['topics']}")
