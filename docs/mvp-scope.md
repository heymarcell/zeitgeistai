# Zeitgeist Engine: MVP Scope

> **Goal:** Ship a working end-to-end pipeline that generates and publishes one digest.
> **Timeline:** 1 week
> **Budget:** ~$16/month

---

## MVP Definition

### What's IN the MVP

| Feature                        | Priority | Status |
| ------------------------------ | -------- | ------ |
| GDELT ingestion (last 4 hours) | P0       | 🔴     |
| Bluesky Jetstream sampling     | P0       | 🔴     |
| Basic deduplication (SHA-256)  | P0       | 🔴     |
| Simple clustering (HDBSCAN)    | P0       | 🔴     |
| LLM summarization (Gemini)     | P0       | 🔴     |
| Static digest output (JSON)    | P0       | 🔴     |
| Bluesky posting                | P1       | 🔴     |
| Mastodon posting               | P1       | 🔴     |
| Manual trigger endpoint        | P1       | 🔴     |

### What's NOT in the MVP

| Feature                       | Reason                     | When    |
| ----------------------------- | -------------------------- | ------- |
| Story Arc Registry            | Complex, can add later     | Phase 2 |
| Contrarian detection          | Nice-to-have               | Phase 2 |
| Visual image collection       | Complex pipeline           | Phase 3 |
| Multi-layer fact verification | Can use single LLM for MVP | Phase 2 |
| PayloadCMS integration        | JSON output sufficient     | Phase 2 |
| Cloudflare Workers deployment | Run locally first          | Phase 3 |
| Full static site              | JSON output sufficient     | Phase 3 |

---

## MVP Architecture (Simplified)

```
┌──────────────────────────────────────────────────────────────┐
│                      MVP PIPELINE                            │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│   1. COLLECT                                                 │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│   │   GDELT     │  │  Bluesky    │  │  pytrends   │         │
│   │  BigQuery   │  │  Jetstream  │  │  (cached)   │         │
│   └──────┬──────┘  └──────┬──────┘  └──────┬──────┘         │
│          │                │                │                 │
│          └────────────────┼────────────────┘                 │
│                           ▼                                  │
│   2. PROCESS                                                 │
│   ┌─────────────────────────────────────────────────────┐   │
│   │  Dedupe (SHA-256) → Embed → HDBSCAN → Rank          │   │
│   └───────────────────────────┬─────────────────────────┘   │
│                               ▼                              │
│   3. GENERATE                                                │
│   ┌─────────────────────────────────────────────────────┐   │
│   │  Gemini 3 Pro: Summarize top cluster → Write digest │   │
│   └───────────────────────────┬─────────────────────────┘   │
│                               ▼                              │
│   4. OUTPUT                                                  │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│   │  JSON File  │  │  Bluesky    │  │  Mastodon   │         │
│   │  (digest)   │  │   Post      │  │    Post     │         │
│   └─────────────┘  └─────────────┘  └─────────────┘         │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## MVP Implementation Tasks

### Day 1: Setup + GDELT

- [ ] Create project structure
- [ ] Set up Python environment
- [ ] Configure BigQuery access
- [ ] Implement `src/collectors/gdelt.py`
- [ ] Test: Query last 4 hours of GDELT

### Day 2: Social Collectors

- [ ] Implement `src/collectors/bluesky.py` (Jetstream)
- [ ] Implement `src/collectors/trends.py` (with caching)
- [ ] Test: Collect 100 posts from Bluesky
- [ ] Test: Get trending topics

### Day 3: Processing

- [ ] Implement `src/processors/dedup.py` (SHA-256 only)
- [ ] Implement `src/processors/clustering.py` (HDBSCAN)
- [ ] Implement `src/processors/scoring.py` (simple ranking)
- [ ] Test: Cluster sample data

### Day 4: Generation

- [ ] Set up Gemini API client
- [ ] Implement `src/generators/synthesis.py`
- [ ] Create digest template
- [ ] Test: Generate digest from cluster

### Day 5: Output + Integration

- [ ] Implement `src/publishers/bluesky.py`
- [ ] Implement `src/publishers/mastodon.py`
- [ ] Create `src/main.py` (full pipeline)
- [ ] Test: End-to-end run

### Day 6: Polish

- [ ] Add error handling
- [ ] Add logging
- [ ] Create `.env.example`
- [ ] Write basic docs
- [ ] Test: Multiple runs

### Day 7: Buffer / Deploy

- [ ] Fix bugs
- [ ] Optional: Deploy to Cloudflare
- [ ] Test: Manual trigger

---

## MVP Output Format

### Digest JSON

```json
{
  "digest_id": "2026-01-13-14",
  "generated_at": "2026-01-13T14:00:00Z",
  "edition": "Afternoon Update",
  "headline": "NATO Summit Tensions Rise as...",
  "summary": "Global leaders gathered in Brussels today...",
  "top_stories": [
    {
      "title": "NATO Summit Day 2",
      "summary": "...",
      "sources": ["reuters.com", "bbc.com"],
      "virality_score": 0.87,
      "topics": ["POLITICS", "INTERNATIONAL"]
    }
  ],
  "trending_topics": ["#NATO", "#Brussels2026"],
  "social_signal": {
    "bluesky_posts": 1247,
    "mastodon_posts": 342
  }
}
```

### Social Post Format

```
🌐 Zeitgeist | Afternoon Update

📰 NATO Summit Tensions Rise as Leaders Clash on Defense Spending

Global leaders gathered in Brussels today amid heightened tensions...

🔗 Full digest: zeitgeist.app/2026-01-13-14

#Zeitgeist #GlobalNews #NATO
```

---

## MVP Success Criteria

| Metric                 | Target      |
| ---------------------- | ----------- |
| End-to-end completion  | < 5 minutes |
| GDELT articles fetched | 1,000+      |
| Bluesky posts sampled  | 100+        |
| Clusters identified    | 5-20        |
| Digest generated       | Valid JSON  |
| Social post published  | 2 platforms |
| Cost per digest        | < $0.10     |

---

## MVP Dependencies

```txt
# requirements.txt (MVP version)
google-cloud-bigquery==3.14.0
atproto==0.0.50
Mastodon.py==1.8.1
pytrends==4.9.2
hdbscan==0.8.33
sentence-transformers==2.2.2
google-generativeai==0.3.0
python-dotenv==1.0.0
```

---

## MVP Config

```python
# src/config.py (MVP version)
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Collection
    GDELT_LOOKBACK_HOURS: int = 4
    BLUESKY_SAMPLE_SIZE: int = 200

    # Processing
    MIN_CLUSTER_SIZE: int = 5

    # Generation
    GEMINI_API_KEY: str
    GEMINI_MODEL: str = "gemini-3-pro"

    # Output
    BLUESKY_HANDLE: str
    BLUESKY_APP_PASSWORD: str
    MASTODON_ACCESS_TOKEN: str
    MASTODON_INSTANCE: str = "https://mastodon.social"

    # Feature flags
    ENABLE_BLUESKY_POST: bool = True
    ENABLE_MASTODON_POST: bool = True

    class Config:
        env_file = ".env"

settings = Settings()
```

---

## Post-MVP Roadmap

### Phase 2 (Week 2-3)

- Story Arc Registry
- Multi-layer fact verification
- Contrarian signal detection
- PayloadCMS integration

### Phase 3 (Week 4-5)

- Visual image collection
- Illustration concept generation
- Static site dashboard
- Cloudflare Workers deployment

### Phase 4 (Week 6+)

- Monitoring dashboard
- A/B testing different formats
- Performance optimization
- Additional social platforms
