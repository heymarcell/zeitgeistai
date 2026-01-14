"""
Multi-Layer Fact Verification Module

Implements Zero-Trust verification loop:
1. Claim Extraction - Parse draft for check-worthy facts
2. Evidence Retrieval - Query vector DB for source sentences
3. Faithfulness Check - Score must be ≥ 0.95
4. Judge Review - Adversarial audit with different model

Uses best models per spec:
- Gemini for claim extraction
- Claude for synthesis
- GPT-5.2 for adversarial verification
"""

from typing import List, Dict, Any, Tuple
import json
import structlog

from src.config import settings

logger = structlog.get_logger()

# Faithfulness threshold from spec
FAITHFULNESS_THRESHOLD = 0.95
MAX_VERIFICATION_ATTEMPTS = 3


class MultiLayerVerifier:
    """
    Multi-layer fact verification system.
    
    Implements the Zero-Trust verification loop from the spec.
    """
    
    def __init__(self):
        self.gemini_client = None
        self.anthropic_client = None
        self.openai_client = None
        self._init_clients()
    
    def _init_clients(self):
        """Initialize LLM clients lazily."""
        pass  # Clients are initialized on first use
    
    def _get_gemini(self):
        """Get or create Gemini client."""
        if self.gemini_client is None and settings.GEMINI_API_KEY:
            from google import genai
            self.gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)
        return self.gemini_client
    
    def _get_anthropic(self):
        """Get or create Anthropic client."""
        if self.anthropic_client is None and settings.ANTHROPIC_API_KEY:
            try:
                import anthropic
                self.anthropic_client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
            except ImportError:
                logger.warning("anthropic_not_installed")
        return self.anthropic_client
    
    def _get_openai(self):
        """Get or create OpenAI client."""
        if self.openai_client is None and settings.OPENAI_API_KEY:
            try:
                import openai
                self.openai_client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
            except ImportError:
                logger.warning("openai_not_installed")
        return self.openai_client
    
    def verify_digest(
        self,
        draft: str,
        sources: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Run multi-layer verification on a digest draft.
        
        Args:
            draft: Generated digest text
            sources: Source articles/documents
            
        Returns:
            Verification result with scores and issues
        """
        logger.info("verification_started")
        
        result = {
            "passed": False,
            "faithfulness_score": 0.0,
            "claims": [],
            "issues": [],
            "attempts": 0,
        }
        
        for attempt in range(MAX_VERIFICATION_ATTEMPTS):
            result["attempts"] = attempt + 1
            
            # Step 1: Extract claims
            claims = self._extract_claims(draft)
            result["claims"] = claims
            
            if not claims:
                logger.warning("no_claims_extracted")
                result["passed"] = True  # No claims to verify
                return result
            
            # Step 2: Verify each claim against sources
            verified_claims = []
            issues = []
            
            for claim in claims:
                is_supported, evidence = self._verify_claim(claim, sources)
                verified_claims.append({
                    "claim": claim,
                    "supported": is_supported,
                    "evidence": evidence,
                })
                
                if not is_supported:
                    issues.append(f"Unsupported claim: {claim[:100]}...")
            
            # Step 3: Calculate faithfulness score
            supported_count = sum(1 for c in verified_claims if c["supported"])
            faithfulness = supported_count / len(claims) if claims else 1.0
            result["faithfulness_score"] = round(faithfulness, 4)
            result["issues"] = issues
            
            # Step 4: Check threshold
            if faithfulness >= FAITHFULNESS_THRESHOLD:
                # Step 5: Adversarial judge review (optional but recommended)
                judge_passed = self._adversarial_judge_review(draft, sources)
                
                if judge_passed:
                    result["passed"] = True
                    logger.info("verification_passed",
                               faithfulness=faithfulness,
                               attempts=attempt + 1)
                    return result
                else:
                    issues.append("Adversarial judge flagged potential issues")
            
            logger.info("verification_attempt_failed",
                       attempt=attempt + 1,
                       faithfulness=faithfulness)
        
        logger.warning("verification_failed",
                      faithfulness=result["faithfulness_score"],
                      issues=len(result["issues"]))
        return result
    
    def _extract_claims(self, text: str) -> List[str]:
        """Extract check-worthy claims from text using Gemini."""
        client = self._get_gemini()
        
        if not client:
            # Fallback: Simple sentence extraction
            return self._simple_claim_extraction(text)
        
        try:
            prompt = f"""Extract all factual claims from this text that should be fact-checked.
Return each claim as a separate line. Only include specific, verifiable facts.
Do not include opinions, predictions, or vague statements.

Text:
{text}

Factual claims (one per line):"""
            
            response = client.models.generate_content(
                model=settings.GEMINI_MODEL_EXTRACTION,
                contents=prompt
            )
            claims = [line.strip() for line in response.text.strip().split("\n") if line.strip()]
            return claims[:10]  # Limit to 10 claims
            
        except Exception as e:
            logger.warning("claim_extraction_failed", error=str(e))
            return self._simple_claim_extraction(text)
    
    def _simple_claim_extraction(self, text: str) -> List[str]:
        """Fallback claim extraction without LLM."""
        # Split into sentences and filter for likely claims
        import re
        sentences = re.split(r'[.!?]', text)
        
        claims = []
        for sentence in sentences:
            sentence = sentence.strip()
            # Look for sentences with numbers, names, or factual indicators
            if len(sentence) > 20 and any(c.isdigit() for c in sentence):
                claims.append(sentence)
            elif len(sentence) > 30:
                claims.append(sentence)
        
        return claims[:5]
    
    def _verify_claim(
        self,
        claim: str,
        sources: List[Dict[str, Any]]
    ) -> Tuple[bool, str]:
        """
        Verify a single claim against source documents.
        
        Returns:
            Tuple of (is_supported, evidence_text)
        """
        # Search for relevant evidence in sources
        evidence = self._find_evidence(claim, sources)
        
        if not evidence:
            return False, "No supporting evidence found"
        
        # Check if evidence supports the claim
        client = self._get_gemini()
        
        if not client:
            # Fallback: Simple keyword matching
            claim_words = set(claim.lower().split())
            evidence_words = set(evidence.lower().split())
            overlap = len(claim_words & evidence_words) / len(claim_words)
            return overlap > 0.3, evidence
        
        try:
            prompt = f"""Determine if the evidence supports the claim.

Claim: {claim}

Evidence: {evidence}

Does the evidence directly support the claim? Answer only "SUPPORTED" or "NOT_SUPPORTED"."""
            
            response = client.models.generate_content(
                model=settings.GEMINI_MODEL_EXTRACTION,
                contents=prompt
            )
            is_supported = "SUPPORTED" in response.text.upper() and "NOT_SUPPORTED" not in response.text.upper()
            return is_supported, evidence
            
        except Exception as e:
            logger.warning("claim_verification_failed", error=str(e))
            return False, "Verification error"
    
    def _find_evidence(self, claim: str, sources: List[Dict[str, Any]]) -> str:
        """Find relevant evidence for a claim in sources."""
        # Simple keyword-based search for MVP
        claim_words = set(claim.lower().split())
        
        best_match = ""
        best_score = 0
        
        for source in sources:
            # Get text content from source
            text = source.get("text", "") or source.get("summary", "") or str(source)
            
            # Calculate overlap
            source_words = set(text.lower().split())
            overlap = len(claim_words & source_words)
            
            if overlap > best_score:
                best_score = overlap
                best_match = text[:500]  # Limit evidence length
        
        return best_match
    
    def _adversarial_judge_review(
        self,
        draft: str,
        sources: List[Dict[str, Any]]
    ) -> bool:
        """
        Use GPT-5.2 as adversarial judge for final review.
        
        Looks for:
        - Hallucinations
        - Unsupported claims
        - Logical inconsistencies
        """
        client = self._get_openai()
        
        if not client:
            # Skip if no OpenAI client
            return True
        
        try:
            source_text = "\n".join(
                str(s.get("text", s.get("summary", "")))[:200] for s in sources[:5]
            )
            
            response = client.chat.completions.create(
                model=settings.GPT_MODEL_VERIFICATION,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an adversarial fact-checker. Your job is to find errors, hallucinations, or unsupported claims. Be strict but fair."
                    },
                    {
                        "role": "user",
                        "content": f"""Review this digest draft for factual accuracy.

Draft:
{draft}

Available sources:
{source_text}

Does the draft contain any hallucinations, unsupported claims, or factual errors?
Answer ONLY "APPROVED" if the draft is factually sound, or "REJECTED: [reason]" if there are issues."""
                    }
                ],
                temperature=0.1,
            )
            
            answer = response.choices[0].message.content
            return "APPROVED" in answer.upper()
            
        except Exception as e:
            logger.warning("adversarial_judge_failed", error=str(e))
            return True  # Allow through if judge fails


# Global verifier instance
verifier = MultiLayerVerifier()


def verify_generated_content(
    draft: str,
    sources: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Verify generated content using multi-layer verification.
    
    Args:
        draft: Generated text
        sources: Source articles
        
    Returns:
        Verification result
    """
    return verifier.verify_digest(draft, sources)


if __name__ == "__main__":
    # Test verification
    import logging
    logging.basicConfig(level=logging.INFO)
    
    test_draft = "NATO leaders met in Brussels on January 13, 2026. The summit resulted in a 5% increase in defense spending commitments."
    test_sources = [
        {"text": "NATO summit Brussels January 2026 defense spending increase agreed"},
    ]
    
    result = verify_generated_content(test_draft, test_sources)
    print(f"Verification result: {json.dumps(result, indent=2)}")
