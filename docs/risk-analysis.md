# Zeitgeist Engine: Risk Analysis & Gap Assessment

> **Document Purpose:** Identify potential problems, missing components, and solutions before implementation.
> **Last Updated:** January 2026

---

## Executive Summary

After comprehensive research, I've identified **12 critical issues** and **8 missing components** in the current spec. This document provides solutions for each.

| Category            | Issues Found | Severity  |
| ------------------- | ------------ | --------- |
| Data Acquisition    | 4            | 🔴 High   |
| Processing Pipeline | 3            | 🟡 Medium |
| LLM/Generation      | 2            | 🟡 Medium |
| Infrastructure      | 2            | 🟢 Low    |
| Missing Components  | 8            | 🟡 Medium |

---

## 1. Data Acquisition Issues

### 1.1 🔴 Pytrends Rate Limiting (CRITICAL)

**Problem:**

- Google blocks ~1,400 requests per 4-hour window
- HTTP 429 errors are common and unpredictable
- No official Google Trends API until July 2025

**Impact:** Trend data may be unavailable during high-traffic periods

**Solutions:**

```python
# Solution 1: Exponential backoff with retry
from pytrends.request import TrendReq
import time

pytrends = TrendReq(
    hl='en-US',
    retries=3,
    backoff_factor=1.5  # Wait 1.5x longer after each failure
)

# Solution 2: Minimal queries with caching
TRENDS_CACHE = {}
CACHE_TTL = 3600  # 1 hour

def get_trends_cached():
    if 'trends' in TRENDS_CACHE and time.time() - TRENDS_CACHE['ts'] < CACHE_TTL:
        return TRENDS_CACHE['trends']

    try:
        trends = pytrends.trending_searches(pn='united_states')
        TRENDS_CACHE['trends'] = trends
        TRENDS_CACHE['ts'] = time.time()
        time.sleep(5)  # Mandatory delay
        return trends
    except Exception as e:
        return TRENDS_CACHE.get('trends', [])  # Return stale cache
```

**Recommendation:**

- Query Google Trends only **once per digest** (every 4 hours = 6 queries/day)
- Cache results aggressively
- Implement fallback to GDELT themes if Trends fails

---

### 1.2 🔴 Bluesky Firehose Bandwidth (CRITICAL)

**Problem:**

- Full firehose = **232 GB/day** (7 TB/month!)
- High bandwidth costs if running on cloud
- Processing overhead for filtering

**Solution: Use Jetstream Instead**

Jetstream is Bluesky's lightweight alternative:

- Posts only (filtered) = **850 MB/day** (25.5 GB/month with compression)
- JSON format (no MST verification overhead)
- 90% bandwidth reduction

```python
# Use Jetstream instead of full firehose
import websocket
import json

def on_message(ws, message):
    data = json.loads(message)
    if data.get('collection') == 'app.bsky.feed.post':
        # Process post
        pass

ws = websocket.WebSocketApp(
    "wss://jetstream.atproto.tools/subscribe?wantedCollections=app.bsky.feed.post",
    on_message=on_message
)
ws.run_forever()
```

**Recommendation:**

- Use Jetstream for posts (850 MB/day)
- Apply compression (zstd)
- Filter by engagement threshold before processing

---

### 1.3 🟡 GDELT BigQuery Query Costs

**Problem:**

- Free tier = 1 TB/month
- Unoptimized queries can consume 10-50 GB each
- Risk of exceeding free tier

**Solutions:**

```sql
-- OPTIMIZED: Select only needed columns, filter by time
SELECT
    DocumentIdentifier,
    V2Themes,
    V2Tone,
    DATE
FROM `gdelt-bq.gdeltv2.gkg_partitioned`  -- Use partitioned table!
WHERE _PARTITIONTIME >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 4 HOUR)
  AND V2Themes IS NOT NULL
LIMIT 5000
```

**Query Budget Allocation:**
| Query Type | Freq | Est. Size | Monthly Usage |
|------------|------|-----------|---------------|
| GKG themes | 6/day | 5 GB | 900 GB |
| Events | 1/day | 10 GB | 300 GB |
| **TOTAL** | | | **~200 GB** ✅ |

---

### 1.4 🟡 Mastodon Federation Coverage

**Problem:**

- No single API covers all Mastodon instances
- Public timeline only shows federated posts
- Some instances block automated access

**Solution: Multi-instance sampling**

```python
MASTODON_INSTANCES = [
    'https://mastodon.social',      # Largest general
    'https://mastodon.online',      # Second largest
    'https://mstdn.social',         # Tech-focused
    'https://infosec.exchange',     # Security community
    'https://journa.host',          # Journalists
]

def sample_mastodon_timeline():
    posts = []
    for instance in MASTODON_INSTANCES:
        try:
            mastodon = Mastodon(api_base_url=instance)
            posts.extend(mastodon.timeline_public(limit=20))
        except:
            continue
    return posts
```

---

## 2. Processing Pipeline Issues

### 2.1 🟡 HDBSCAN High Noise Percentage

**Problem:**

- HDBSCAN can label 30-50% of data as "noise" (-1)
- News articles with unique topics get discarded
- Affects cluster quality

**Solutions:**

1. **UMAP Preprocessing** (Recommended)

```python
import umap
from hdbscan import HDBSCAN

# Reduce dimensions before clustering
reducer = umap.UMAP(n_components=50, metric='cosine')
embeddings_reduced = reducer.fit_transform(embeddings)

# Then cluster
clusterer = HDBSCAN(min_cluster_size=5, min_samples=2)
labels = clusterer.fit_predict(embeddings_reduced)
```

2. **Tune Parameters**

```python
# More lenient clustering
clusterer = HDBSCAN(
    min_cluster_size=3,      # Smaller clusters allowed
    min_samples=1,           # Less strict core point requirement
    cluster_selection_epsilon=0.5  # Merge close clusters
)
```

3. **Post-process Noise Points**

- Assign noise points to nearest cluster if similarity > 0.7
- Create "Miscellaneous" category for remaining noise

---

### 2.2 🟡 Embedding Drift Over Time

**Problem:**

- Embedding models may be updated
- New terminology not captured by static embeddings
- Search quality degrades over time

**Mitigation Strategy:**

```python
# Monitor embedding drift
def detect_embedding_drift(old_embeddings, new_embeddings):
    from scipy.spatial.distance import cosine

    # Compare centroid shift
    old_centroid = np.mean(old_embeddings, axis=0)
    new_centroid = np.mean(new_embeddings, axis=0)
    drift_score = cosine(old_centroid, new_centroid)

    if drift_score > 0.1:  # 10% drift threshold
        logger.warning(f"Embedding drift detected: {drift_score:.2%}")
        # Trigger re-indexing

    return drift_score
```

**Schedule:**

- Monitor drift weekly
- Re-index Qdrant if drift > 10%
- Update embedding model quarterly

---

### 2.3 🟡 Cold Start Problem

**Problem:**

- New stories have no historical context
- Story Arc matching fails for emerging topics
- First digest of day lacks baseline

**Solutions:**

1. **Seed with GDELT Historical Data**

```python
# On first run, load last 24 hours of GDELT data
def initialize_story_arcs():
    if qdrant_collection_empty():
        historical = query_gdelt_last_24h()
        process_and_store(historical)
```

2. **Warm Cache Strategy**

- Pre-populate embeddings for known major entities (countries, leaders, orgs)
- Bootstrap Story Arc Registry with Reuters/AP wire categories

---

## 3. LLM/Generation Issues

### 3.1 🟡 RAG Hallucination Risk

**Problem:**

- Even with RAG, LLMs can hallucinate
- Retrieved context may be irrelevant
- 0.95 faithfulness threshold may reject valid content

**Multi-Layer Verification:**

```python
def verify_generated_content(draft, sources):
    # Layer 1: Claim extraction
    claims = extract_claims(draft)  # Gemini Flash

    # Layer 2: Evidence retrieval
    for claim in claims:
        evidence = qdrant.search(claim.embedding, limit=3)
        claim.evidence_score = calculate_support(claim, evidence)

    # Layer 3: Cross-reference with GDELT
    gdelt_match = verify_against_gdelt(claims)

    # Layer 4: Final judge (only for high-value claims)
    if any(c.evidence_score < 0.8 for c in claims):
        judge_result = gpt_judge(claims, sources)

    # Threshold: 95% of claims must be supported
    supported = sum(1 for c in claims if c.evidence_score >= 0.8)
    return supported / len(claims) >= 0.95
```

**Fallback:**

- If verification fails 3x, skip synthesis and output curated list only
- Log failed verifications for manual review

---

### 3.2 🟡 LLM API Failures

**Problem:**

- API outages (Gemini, Claude, OpenAI)
- Rate limiting during peak hours
- Network timeouts

**Circuit Breaker Pattern:**

```python
from pybreaker import CircuitBreaker

# Configure circuit breaker
gemini_breaker = CircuitBreaker(
    fail_max=3,           # Open after 3 failures
    reset_timeout=300     # Try again after 5 minutes
)

@gemini_breaker
def call_gemini(prompt):
    return gemini_client.generate(prompt)

# Fallback chain
def generate_with_fallback(prompt):
    try:
        return call_gemini(prompt)
    except CircuitBreakerError:
        try:
            return call_mistral(prompt)  # Fallback to Mistral
        except:
            return call_local_model(prompt)  # Final fallback
```

---

## 4. Infrastructure Issues

### 4.1 🟢 Qdrant Cold Start Latency

**Problem:**

- First query after restart is slow
- Index loading from disk takes time

**Solution:**

- Keep Qdrant running 24/7 (use Qdrant Cloud)
- Implement health check endpoint
- Pre-warm cache on deployment

---

### 4.2 🟢 Scheduler Reliability

**Problem:**

- Cron jobs can fail silently
- No alerting for missed digests

**Solution: Use Prefect with monitoring**

```python
from prefect import flow, task
from prefect.runtime import flow_run

@task(retries=3, retry_delay_seconds=60)
def generate_digest():
    # ... digest logic
    pass

@flow(log_prints=True)
def zeitgeist_pipeline():
    generate_digest()

# Schedule every 4 hours
if __name__ == "__main__":
    zeitgeist_pipeline.serve(
        name="zeitgeist-scheduler",
        cron="0 2,6,10,14,18,22 * * *"
    )
```

---

## 5. Missing Components

### 5.1 🔴 Error Handling & Alerting

**Currently Missing:**

- No monitoring dashboard
- No alerts for failures
- No logging strategy

**Add:**

```python
import logging
from logging.handlers import RotatingFileHandler

# Structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler('zeitgeist.log', maxBytes=10MB, backupCount=5),
        logging.StreamHandler()
    ]
)

# Alert on critical failures (email/Slack/Discord)
def alert_on_failure(error):
    # Send to Discord webhook
    webhook_url = os.getenv('DISCORD_WEBHOOK')
    requests.post(webhook_url, json={'content': f'🚨 Zeitgeist Error: {error}'})
```

---

### 5.2 🔴 Data Persistence Strategy

**Currently Missing:**

- Where are digests stored?
- How to handle database failures?
- Backup strategy?

**Add:**

- SQLite for digest metadata (simple, reliable)
- JSON files for digest content (version controlled)
- Daily backup to cloud storage

---

### 5.3 🟡 Rate Limit Tracking

**Currently Missing:**

- No tracking of API usage
- Risk of exceeding quotas

**Add:**

```python
# Track API usage
class RateLimitTracker:
    def __init__(self):
        self.usage = defaultdict(int)
        self.limits = {
            'gdelt': 1_000_000_000_000,  # 1 TB/month
            'pytrends': 50,               # per 4 hours
            'gemini': 1_000_000_000,     # tokens/month
        }

    def record(self, service, amount):
        self.usage[service] += amount
        if self.usage[service] > self.limits[service] * 0.8:
            logger.warning(f"{service} at 80% quota!")
```

---

### 5.4 🟡 Content Deduplication Across Digests

**Currently Missing:**

- Same story may appear in consecutive digests
- Need to track "already covered" stories

**Add:**

- Store digest story IDs in memory/Redis
- Check against last 3 digests before including
- Flag as "Update" if story is continuation

---

### 5.5 🟡 Language/Region Handling

**Currently Missing:**

- Spec assumes English only
- No regional filtering

**Decision Needed:**

- English only for MVP? ✅
- Add language detection later
- Regional variants (US vs UK vs AU)?

---

### 5.6 🟡 Testing Strategy

**Currently Missing:**

- No unit tests
- No integration tests
- No mock data for development

**Add:**

- `tests/` directory with pytest
- Mock GDELT/Bluesky responses
- Snapshot testing for digest output

---

### 5.7 🟡 Configuration Management

**Currently Missing:**

- Hardcoded values in spec
- No environment variables

**Add:**

```python
# config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DIGEST_FREQUENCY_HOURS: int = 4
    MIN_CLUSTER_SIZE: int = 5
    FAITHFULNESS_THRESHOLD: float = 0.95

    GEMINI_API_KEY: str
    QDRANT_URL: str
    QDRANT_API_KEY: str

    class Config:
        env_file = '.env'

settings = Settings()
```

---

### 5.8 🟢 Documentation

**Currently Missing:**

- API documentation
- Deployment guide
- Runbook for operations

---

## 6. Updated Risk Matrix

| Risk                 | Probability | Impact | Mitigation Status              |
| -------------------- | ----------- | ------ | ------------------------------ |
| Pytrends rate limit  | High        | High   | ✅ Solved (caching + fallback) |
| Bluesky bandwidth    | High        | Medium | ✅ Solved (Jetstream)          |
| GDELT quota exceeded | Medium      | High   | ✅ Solved (query optimization) |
| HDBSCAN high noise   | Medium      | Medium | ✅ Solved (UMAP + tuning)      |
| LLM hallucination    | Medium      | High   | ✅ Solved (multi-layer verify) |
| API outages          | Low         | High   | ✅ Solved (circuit breaker)    |
| Embedding drift      | Low         | Medium | ⚠️ Partial (monitoring only)   |
| Cold start           | Low         | Low    | ✅ Solved (warm cache)         |

---

## 7. Recommended Priority Actions

### Phase 0: Before Coding

1. ✅ Finalize this risk assessment
2. Set up project structure with `config.py`
3. Create `.env.example` with all required keys
4. Set up logging infrastructure

### Phase 1: Core Pipeline (Week 1-2)

1. Implement GDELT ingestion with query optimization
2. Implement Jetstream (not full firehose) for Bluesky
3. Add pytrends with aggressive caching
4. Set up Qdrant with proper schema

### Phase 2: Processing (Week 3-4)

1. Implement UMAP + HDBSCAN clustering
2. Add Story Arc Registry
3. Implement deduplication across digests
4. Add viral velocity scoring

### Phase 3: Generation (Week 5-6)

1. Set up LLM clients with circuit breakers
2. Implement multi-layer verification
3. Add illustration concept generation
4. Create output templates

### Phase 4: Operations (Week 7-8)

1. Set up Prefect scheduler
2. Add Discord/Slack alerting
3. Create monitoring dashboard
4. Write deployment documentation

---

## 8. Open Questions for User

1. **Language Scope:** English only, or include other languages?
2. **Geographic Focus:** Global, or prioritize specific regions?
3. **Hosting:** Where will this run? (Local, VPS, Cloud?)
4. **Social Output:** Which platforms for automated posting?
5. **Web Dashboard:** Simple static site or interactive?
