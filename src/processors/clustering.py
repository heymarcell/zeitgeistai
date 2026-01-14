"""
Clustering Module

Groups related articles using HDBSCAN with UMAP dimensionality reduction.
Uses Gemini cloud embeddings instead of local sentence-transformers.
"""

from typing import List, Dict, Any
import numpy as np
import structlog

import hdbscan
import umap

from src.config import settings
from src.processors.embeddings import embed_texts, EMBEDDING_DIMS

logger = structlog.get_logger()


def cluster_articles(articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Cluster articles by semantic similarity.
    
    Uses Gemini cloud embeddings, UMAP for dimensionality
    reduction, and HDBSCAN for clustering.
    
    Args:
        articles: List of article dictionaries with 'themes' or 'url' fields
        
    Returns:
        List of cluster dictionaries, each containing:
        - cluster_id: Cluster identifier
        - articles: List of articles in the cluster
        - centroid: Cluster centroid embedding (768 dims)
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
    
    # Generate embeddings using Gemini cloud API
    embedding_list = embed_texts(texts, task_type="CLUSTERING")
    embeddings = np.array(embedding_list)
    logger.info("embeddings_generated", shape=embeddings.shape, source="gemini_cloud")
    
    # Handle edge case: too few articles
    if len(embeddings) < settings.MIN_CLUSTER_SIZE:
        logger.info("too_few_articles_for_clustering", count=len(embeddings))
        return _create_single_cluster(articles, embeddings)
    
    # Apply UMAP for dimensionality reduction
    n_components = min(settings.UMAP_N_COMPONENTS, len(embeddings) - 2)
    if len(embeddings) > n_components + 1:
        reducer = umap.UMAP(
            n_components=n_components,
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
        # Calculate centroid using ORIGINAL embeddings (768 dims)
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
            "centroid": centroid.tolist(),  # 768-dim for Qdrant
            "topics": [t[0] for t in top_themes],
            "size": len(cluster_data["articles"])
        })
    
    # Sort by cluster size
    result.sort(key=lambda x: x["size"], reverse=True)
    
    logger.info("clustering_complete", 
                num_clusters=len(result),
                noise_count=sum(1 for l in cluster_labels if l == -1))
    
    return result


def _create_single_cluster(
    articles: List[Dict[str, Any]], 
    embeddings: np.ndarray
) -> List[Dict[str, Any]]:
    """Create a single cluster when too few articles for HDBSCAN."""
    if len(articles) == 0:
        return []
    
    centroid = np.mean(embeddings, axis=0)
    
    # Extract themes
    all_themes = []
    for article in articles:
        themes = article.get("themes", [])
        if isinstance(themes, list):
            all_themes.extend(themes)
    
    theme_counts = {}
    for theme in all_themes:
        theme_counts[theme] = theme_counts.get(theme, 0) + 1
    
    top_themes = sorted(theme_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    
    return [{
        "cluster_id": 0,
        "articles": articles,
        "centroid": centroid.tolist(),
        "topics": [t[0] for t in top_themes],
        "size": len(articles)
    }]


if __name__ == "__main__":
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
        print(f"  Centroid dims: {len(c['centroid'])}")
