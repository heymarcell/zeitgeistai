"""
Cloud Embeddings Module

Uses Gemini API (google.genai SDK) for text embeddings.
This enables fully cloud-native architecture without GPU requirements.

Model: gemini-embedding-001
- Default: 3072 dimensions
- MRL: Can reduce to 768 or 1536 for efficiency
"""

from typing import List
import asyncio
import structlog

from google import genai

from src.config import settings

logger = structlog.get_logger()

# Get embedding dimension from config (768 default, can use 3072 for max quality)
EMBEDDING_DIMS = settings.EMBEDDING_DIMS

# Lazy-load client
_client = None


def _get_client():
    """Get or create Gemini client."""
    global _client
    if _client is None:
        if not settings.GEMINI_API_KEY:
            logger.warning("gemini_api_key_not_set")
            return None
        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _client


def embed_texts(
    texts: List[str],
    task_type: str = "SEMANTIC_SIMILARITY"
) -> List[List[float]]:
    """
    Generate embeddings for a list of texts using Gemini API.
    
    Args:
        texts: List of texts to embed
        task_type: Embedding task type:
            - SEMANTIC_SIMILARITY: For comparing text similarity
            - RETRIEVAL_QUERY: For search queries
            - RETRIEVAL_DOCUMENT: For documents to be searched
            - CLASSIFICATION: For text classification
            - CLUSTERING: For clustering tasks
    
    Returns:
        List of embedding vectors (768 dimensions each by default)
    """
    if not texts:
        return []
    
    client = _get_client()
    if not client:
        return [[0.0] * EMBEDDING_DIMS for _ in texts]
    
    try:
        # Use new google.genai API
        embeddings = []
        batch_size = 100  # Gemini supports up to 100 texts per batch
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            
            result = client.models.embed_content(
                model="gemini-embedding-001",
                contents=batch,
                config={
                    "task_type": task_type,
                    "output_dimensionality": EMBEDDING_DIMS
                }
            )
            
            # Extract embeddings from response
            for embedding in result.embeddings:
                embeddings.append(list(embedding.values))
        
        logger.debug("embeddings_generated", count=len(embeddings), dims=EMBEDDING_DIMS)
        return embeddings
        
    except Exception as e:
        logger.error("embedding_failed", error=str(e))
        return [[0.0] * EMBEDDING_DIMS for _ in texts]


async def embed_texts_async(
    texts: List[str],
    task_type: str = "SEMANTIC_SIMILARITY"
) -> List[List[float]]:
    """
    Async wrapper for embed_texts.
    
    Uses thread pool since google.genai is synchronous.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, embed_texts, texts, task_type)


def embed_single(text: str, task_type: str = "SEMANTIC_SIMILARITY") -> List[float]:
    """Embed a single text and return its vector."""
    result = embed_texts([text], task_type)
    return result[0] if result else [0.0] * EMBEDDING_DIMS


# Article-specific embedding functions
def embed_articles(articles: List[dict]) -> List[List[float]]:
    """
    Generate embeddings for article content.
    
    Extracts text from themes/content for embedding.
    """
    texts = []
    for article in articles:
        # Combine themes and other text for embedding
        themes = article.get("themes", [])
        if isinstance(themes, list):
            text = " ".join(themes[:10])
        else:
            text = str(themes)
        
        # Add any other text content
        if "content" in article:
            text = f"{text} {article['content'][:500]}"
        
        texts.append(text if text.strip() else "news article")
    
    return embed_texts(texts, task_type="CLUSTERING")


def embed_cluster_topics(topics: List[str]) -> List[float]:
    """
    Generate embedding for cluster topics.
    
    Used for Story Arc fingerprinting.
    """
    text = " ".join(topics[:10])
    return embed_single(text, task_type="SEMANTIC_SIMILARITY")


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    
    # Test embedding
    test_texts = [
        "NATO summit discusses defense spending",
        "Climate change summit in Paris",
        "Technology stocks rise on AI news"
    ]
    
    embeddings = embed_texts(test_texts)
    print(f"Generated {len(embeddings)} embeddings")
    print(f"Dimension: {len(embeddings[0])}")
    print(f"First embedding (first 10 values): {embeddings[0][:10]}")
