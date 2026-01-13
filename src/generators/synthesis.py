"""
Narrative Synthesis Module

Uses best-in-class LLMs for each stage:
- Gemini 2.5 Flash: Entity/claim extraction
- Gemini 3 Pro: Article summarization  
- Claude Opus 4.5: Final narrative synthesis
- GPT-5.2: Adversarial verification
"""

from typing import List, Dict, Any
import json
import structlog

from src.config import settings

logger = structlog.get_logger()


class NarrativeSynthesizer:
    """
    Multi-model narrative synthesizer.
    
    Uses tiered LLM approach for optimal quality/cost tradeoff.
    """
    
    def __init__(self):
        self.gemini_client = None
        self.anthropic_client = None
        
    def _get_gemini(self, model_name: str = None):
        """Get Gemini client."""
        if not settings.GEMINI_API_KEY:
            return None
            
        try:
            import google.generativeai as genai
            genai.configure(api_key=settings.GEMINI_API_KEY)
            return genai.GenerativeModel(model_name or settings.GEMINI_MODEL_SUMMARIZATION)
        except Exception as e:
            logger.warning("gemini_init_failed", error=str(e))
            return None
    
    def _get_anthropic(self):
        """Get Anthropic client."""
        if not settings.ANTHROPIC_API_KEY:
            return None
            
        try:
            import anthropic
            return anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        except Exception as e:
            logger.warning("anthropic_init_failed", error=str(e))
            return None
    
    def generate_digest(
        self,
        digest_id: str,
        edition: str,
        clusters: List[Dict[str, Any]],
        trending: List[str]
    ) -> Dict[str, Any]:
        """
        Generate complete digest using multi-model pipeline.
        
        Pipeline:
        1. Extract entities/claims (Gemini Flash)
        2. Summarize articles (Gemini Pro)
        3. Synthesize narrative (Claude Opus 4.5)
        4. Verify facts (GPT-5.2) - handled by verification module
        """
        logger.info("synthesis_started", digest_id=digest_id, num_clusters=len(clusters))
        
        if not clusters:
            return self._create_empty_digest(digest_id, edition)
        
        # Stage 1: Extract key information
        extracted = self._extract_entities(clusters)
        
        # Stage 2: Summarize top clusters  
        summaries = self._summarize_clusters(clusters[:3])
        
        # Stage 3: Synthesize final narrative
        digest = self._synthesize_narrative(
            digest_id=digest_id,
            edition=edition,
            extracted=extracted,
            summaries=summaries,
            trending=trending,
            clusters=clusters
        )
        
        logger.info("synthesis_complete", headline=digest.get("headline", "")[:50])
        return digest
    
    def _extract_entities(self, clusters: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract entities and claims from clusters using Gemini Flash."""
        model = self._get_gemini(settings.GEMINI_MODEL_EXTRACTION)
        
        if not model:
            # Fallback: extract from cluster metadata
            entities = []
            for cluster in clusters[:3]:
                entities.extend(cluster.get("topics", [])[:3])
            return {"entities": list(set(entities))[:10], "claims": []}
        
        try:
            cluster_text = ""
            for i, cluster in enumerate(clusters[:3]):
                topics = ", ".join(cluster.get("topics", [])[:5])
                cluster_text += f"Cluster {i+1}: {topics}\n"
            
            prompt = f"""Extract key entities and factual claims from these news clusters.

{cluster_text}

Respond in JSON:
{{
    "entities": ["Person: Name", "Org: Name", "Location: Name"],
    "claims": ["Specific factual claim 1", "Claim 2"]
}}"""
            
            response = model.generate_content(prompt)
            text = response.text
            
            if "{" in text:
                json_str = text[text.index("{"):text.rindex("}")+1]
                return json.loads(json_str)
                
        except Exception as e:
            logger.warning("entity_extraction_failed", error=str(e))
        
        return {"entities": [], "claims": []}
    
    def _summarize_clusters(self, clusters: List[Dict[str, Any]]) -> List[str]:
        """Summarize each cluster using Gemini Pro."""
        model = self._get_gemini(settings.GEMINI_MODEL_SUMMARIZATION)
        
        summaries = []
        
        for cluster in clusters:
            if model:
                try:
                    topics = ", ".join(cluster.get("topics", [])[:5])
                    articles = cluster.get("articles", [])[:3]
                    
                    prompt = f"""Summarize this news cluster in 2-3 sentences.

Topics: {topics}
Number of articles: {cluster.get('size', len(articles))}
Virality score: {cluster.get('virality_score', 0):.2f}

Write a concise summary of what's happening:"""
                    
                    response = model.generate_content(prompt)
                    summaries.append(response.text.strip())
                    
                except Exception as e:
                    logger.warning("cluster_summarization_failed", error=str(e))
                    summaries.append(f"News cluster about: {', '.join(cluster.get('topics', [])[:3])}")
            else:
                summaries.append(f"News cluster about: {', '.join(cluster.get('topics', [])[:3])}")
        
        return summaries
    
    def _synthesize_narrative(
        self,
        digest_id: str,
        edition: str,
        extracted: Dict[str, Any],
        summaries: List[str],
        trending: List[str],
        clusters: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Synthesize final narrative using Claude Opus 4.5."""
        
        # Try Claude first (best quality)
        anthropic = self._get_anthropic()
        
        if anthropic:
            try:
                return self._synthesize_with_claude(
                    anthropic, digest_id, edition, extracted, summaries, trending, clusters
                )
            except Exception as e:
                logger.warning("claude_synthesis_failed", error=str(e))
        
        # Fallback to Gemini
        gemini = self._get_gemini(settings.GEMINI_MODEL_SUMMARIZATION)
        
        if gemini:
            try:
                return self._synthesize_with_gemini(
                    gemini, digest_id, edition, extracted, summaries, trending, clusters
                )
            except Exception as e:
                logger.warning("gemini_synthesis_failed", error=str(e))
        
        # Final fallback
        return self._create_fallback_digest(digest_id, edition, clusters)
    
    def _synthesize_with_claude(
        self,
        client,
        digest_id: str,
        edition: str,
        extracted: Dict[str, Any],
        summaries: List[str],
        trending: List[str],
        clusters: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Use Claude Opus 4.5 for narrative synthesis."""
        
        summaries_text = "\n".join(f"- {s}" for s in summaries)
        entities_text = ", ".join(extracted.get("entities", [])[:10])
        trending_text = ", ".join(trending[:10]) if trending else "No trending data"
        
        prompt = f"""You are the editor of Zeitgeist, a global news intelligence service.
Create the {edition} digest for {digest_id}.

## Source Summaries:
{summaries_text}

## Key Entities:
{entities_text}

## Currently Trending:
{trending_text}

## Your Task:
Create a compelling news digest with:
1. A headline (max 100 chars) - punchy, informative
2. A 2-3 paragraph summary (200-300 words) covering the most significant stories
3. 3-5 key takeaways as bullet points
4. Brief mentions of other notable stories

Write in clear, journalistic prose. Be factual, not sensational.

Respond in JSON:
{{
    "headline": "Your headline",
    "summary": "Your 2-3 paragraph summary",
    "key_takeaways": ["Takeaway 1", "Takeaway 2", "Takeaway 3"],
    "additional_stories": ["Brief story 1", "Brief story 2"]
}}"""
        
        response = client.messages.create(
            model=settings.CLAUDE_MODEL_SYNTHESIS,
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}]
        )
        
        text = response.content[0].text
        
        # Parse JSON
        if "{" in text:
            json_str = text[text.index("{"):text.rindex("}")+1]
            parsed = json.loads(json_str)
            
            return {
                "digest_id": digest_id,
                "edition": edition,
                "headline": parsed.get("headline", "Global News Update"),
                "summary": parsed.get("summary", ""),
                "key_takeaways": parsed.get("key_takeaways", []),
                "additional_stories": parsed.get("additional_stories", []),
                "entities": extracted.get("entities", []),
                "clusters_analyzed": len(clusters),
                "model_used": "claude-opus-4.5",
            }
        
        raise ValueError("Could not parse Claude response")
    
    def _synthesize_with_gemini(
        self,
        model,
        digest_id: str,
        edition: str,
        extracted: Dict[str, Any],
        summaries: List[str],
        trending: List[str],
        clusters: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Fallback synthesis using Gemini."""
        
        summaries_text = "\n".join(f"- {s}" for s in summaries)
        
        prompt = f"""Create a news digest for {edition}.

Stories:
{summaries_text}

Respond in JSON:
{{
    "headline": "Headline (max 100 chars)",
    "summary": "2-3 paragraph summary",
    "key_takeaways": ["Point 1", "Point 2", "Point 3"]
}}"""
        
        response = model.generate_content(prompt)
        text = response.text
        
        if "{" in text:
            json_str = text[text.index("{"):text.rindex("}")+1]
            parsed = json.loads(json_str)
            
            return {
                "digest_id": digest_id,
                "edition": edition,
                "headline": parsed.get("headline", "Global News Update"),
                "summary": parsed.get("summary", ""),
                "key_takeaways": parsed.get("key_takeaways", []),
                "clusters_analyzed": len(clusters),
                "model_used": "gemini",
            }
        
        raise ValueError("Could not parse Gemini response")
    
    def _create_empty_digest(self, digest_id: str, edition: str) -> Dict[str, Any]:
        """Create empty digest when no clusters available."""
        return {
            "digest_id": digest_id,
            "edition": edition,
            "headline": "No Major Stories Detected",
            "summary": "The global news landscape is relatively quiet at this time.",
            "key_takeaways": [],
            "clusters_analyzed": 0,
        }
    
    def _create_fallback_digest(
        self,
        digest_id: str,
        edition: str,
        clusters: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Create fallback digest when LLMs fail."""
        top_topics = []
        for c in clusters[:3]:
            top_topics.extend(c.get("topics", [])[:2])
        
        topics_text = ", ".join(list(set(top_topics))[:5])
        
        return {
            "digest_id": digest_id,
            "edition": edition,
            "headline": f"Top Stories: {topics_text}",
            "summary": f"This edition covers {len(clusters)} major story clusters focusing on {topics_text}.",
            "key_takeaways": [f"Focus area: {t}" for t in top_topics[:3]],
            "clusters_analyzed": len(clusters),
            "model_used": "fallback",
        }


# Global synthesizer
_synthesizer = NarrativeSynthesizer()


def generate_digest_narrative(
    digest_id: str,
    edition: str,
    clusters: List[Dict[str, Any]],
    trending: List[str]
) -> Dict[str, Any]:
    """Generate digest narrative using multi-model pipeline."""
    return _synthesizer.generate_digest(digest_id, edition, clusters, trending)


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    
    test_clusters = [
        {
            "cluster_id": 0,
            "topics": ["NATO", "SUMMIT", "DEFENSE"],
            "articles": [],
            "virality_score": 0.85,
            "size": 25
        }
    ]
    
    digest = generate_digest_narrative(
        "2026-01-13-14",
        "Afternoon Update",
        test_clusters,
        ["NATO", "Brussels"]
    )
    
    print(json.dumps(digest, indent=2))
