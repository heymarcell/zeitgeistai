"""
Illustration Concept Generator

Generates illustration concepts for digest visuals.
Does NOT generate actual images - provides structured concept for artists/AI.

Uses Claude Sonnet 4.5 for creative illustration concepts.
"""

from typing import List, Dict, Any
import json
import structlog

from src.config import settings

logger = structlog.get_logger()


def generate_illustration_concept(
    digest: Dict[str, Any],
    clusters: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Generate an illustration concept for a digest.
    
    The concept describes the visual without generating the image.
    This allows for flexibility in generation method (DALL-E, Midjourney, human artist).
    
    Args:
        digest: Generated digest with headline, summary
        clusters: Source clusters for context
        
    Returns:
        Illustration concept dictionary
    """
    logger.info("illustration_concept_started")
    
    # Extract key information for concept
    headline = digest.get("headline", "")
    summary = digest.get("summary", "")[:500]
    top_topics = []
    
    for cluster in clusters[:3]:
        top_topics.extend(cluster.get("topics", [])[:2])
    
    # Try Claude Sonnet for creative concepts
    concept = _generate_with_claude(headline, summary, top_topics)
    
    if not concept:
        # Fallback to Gemini
        concept = _generate_with_gemini(headline, summary, top_topics)
    
    if not concept:
        # Final fallback: rule-based concept
        concept = _generate_fallback_concept(headline, top_topics)
    
    logger.info("illustration_concept_complete", style=concept.get("style", ""))
    return concept


def _generate_with_claude(
    headline: str,
    summary: str,
    topics: List[str]
) -> Dict[str, Any]:
    """Generate illustration concept using Claude Sonnet 4.5."""
    if not settings.ANTHROPIC_API_KEY:
        return None
    
    try:
        import anthropic
        
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        
        prompt = f"""Create an illustration concept for this news digest.

Headline: {headline}
Summary: {summary}
Key Topics: {', '.join(topics[:5])}

Generate a visual concept with:
1. Core concept (what the illustration shows)
2. Art style (editorial, photojournalistic, abstract, etc.)
3. Mood/atmosphere
4. Key visual elements (3-5 specific elements)
5. Color palette suggestion
6. Things to AVOID (text, specific faces, logos, etc.)

Respond in JSON format:
{{
    "concept": "Description of what the illustration should show",
    "style": "Art style name",
    "mood": "Emotional tone",
    "key_elements": ["element1", "element2", "element3"],
    "color_palette": "Color description",
    "avoid": ["thing1", "thing2"]
}}"""
        
        response = client.messages.create(
            model=settings.CLAUDE_MODEL_ILLUSTRATION,
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )
        
        text = response.content[0].text
        
        # Parse JSON from response
        if "{" in text and "}" in text:
            json_start = text.index("{")
            json_end = text.rindex("}") + 1
            return json.loads(text[json_start:json_end])
        
    except Exception as e:
        logger.warning("claude_illustration_failed", error=str(e))
    
    return None


def _generate_with_gemini(
    headline: str,
    summary: str,
    topics: List[str]
) -> Dict[str, Any]:
    """Generate illustration concept using Gemini."""
    if not settings.GEMINI_API_KEY:
        return None
    
    try:
        from google import genai
        
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        
        prompt = f"""Create an illustration concept for this news digest.

Headline: {headline}
Summary: {summary[:300]}
Topics: {', '.join(topics[:5])}

Respond ONLY with this JSON:
{{
    "concept": "what the illustration shows",
    "style": "art style",
    "mood": "emotional tone",
    "key_elements": ["element1", "element2", "element3"],
    "color_palette": "colors",
    "avoid": ["thing1", "thing2"]
}}"""
        
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        text = response.text
        
        if "{" in text and "}" in text:
            json_start = text.index("{")
            json_end = text.rindex("}") + 1
            return json.loads(text[json_start:json_end])
        
    except Exception as e:
        logger.warning("gemini_illustration_failed", error=str(e))
    
    return None


def _generate_fallback_concept(
    headline: str,
    topics: List[str]
) -> Dict[str, Any]:
    """Generate a basic illustration concept without LLM."""
    # Map topics to visual styles
    style_map = {
        "WAR": ("Photojournalistic", "Somber, tense"),
        "CONFLICT": ("Documentary", "Urgent, dramatic"),
        "POLITICS": ("Editorial illustration", "Formal, serious"),
        "SUMMIT": ("Diplomatic portrait", "Formal, hopeful"),
        "TECHNOLOGY": ("Futuristic concept art", "Innovative, bright"),
        "AI": ("Digital art", "Sleek, technological"),
        "CLIMATE": ("Environmental photography", "Urgent, natural"),
        "PROTEST": ("Photojournalistic", "Dynamic, passionate"),
        "ECONOMY": ("Infographic style", "Professional, analytical"),
        "HEALTH": ("Medical illustration", "Clean, reassuring"),
    }
    
    # Find best matching style
    style = "Editorial illustration"
    mood = "Informative, balanced"
    
    for topic in topics:
        topic_upper = topic.upper()
        if topic_upper in style_map:
            style, mood = style_map[topic_upper]
            break
    
    return {
        "concept": f"Visual representation of: {headline[:100]}",
        "style": style,
        "mood": mood,
        "key_elements": [t.replace("_", " ").title() for t in topics[:3]],
        "color_palette": "Muted, professional tones with accent colors",
        "avoid": ["Text", "Specific faces", "Brand logos", "Sensitive imagery"],
    }


if __name__ == "__main__":
    # Test illustration concept generation
    import logging
    logging.basicConfig(level=logging.INFO)
    
    test_digest = {
        "headline": "NATO Summit Reaches Historic Defense Agreement",
        "summary": "World leaders gathered in Brussels for a landmark summit..."
    }
    
    test_clusters = [
        {"topics": ["NATO", "SUMMIT", "DEFENSE", "BRUSSELS"]},
    ]
    
    concept = generate_illustration_concept(test_digest, test_clusters)
    print(json.dumps(concept, indent=2))
