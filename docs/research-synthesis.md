# Zeitgeist Engine: Research Synthesis & Recommendations

This document synthesizes research findings to extend the Chronos Protocol blueprint with solutions for:

1. Story Arc / Narrative Continuity
2. Optimized Viral Velocity Weights
3. Contrarian Signal Detection
4. Multimodal Image Collection
5. Infrastructure Recommendations (Qdrant, APIs, GDELT)

---

## 1. Story Arc & Narrative Continuity

### The Problem

The current blueprint focuses on hourly snapshots but lacks a mechanism to track **multi-day developing stories**. A war, election, or crisis that spans weeks should be recognized as a continuous narrative, not treated as isolated hourly events.

### Recommended Solution: Story Fingerprinting + Entity-Centric Tracking

**Architecture:**

```
┌─────────────────────────────────────────────────────────────┐
│                    STORY ARC REGISTRY                       │
├─────────────────────────────────────────────────────────────┤
│  story_id: UUID                                             │
│  story_fingerprint: vector (semantic centroid)              │
│  canonical_title: str (LLM-generated summary)               │
│  first_seen_at: timestamp                                   │
│  last_seen_at: timestamp                                    │
│  hourly_snapshots: [zeitgeist_id, zeitgeist_id, ...]        │
│  core_entities: [entity_id, entity_id, ...]                 │
│  narrative_phase: enum [EMERGING, DEVELOPING, PEAK, FADING] │
│  cumulative_velocity: float                                 │
└─────────────────────────────────────────────────────────────┘
```

**Algorithm:**

1. **Clustering with Memory**: When HDBSCAN produces hourly clusters, compute each cluster's semantic centroid (average embedding)
2. **Story Matching**: Compare new cluster centroids against the Story Arc Registry using cosine similarity (threshold: 0.85)
3. **Match Found → Link**: Append the current `zeitgeist_id` to the existing story's `hourly_snapshots` array
4. **No Match → New Story**: Create a new story entry with current cluster as origin
5. **Narrative Phase Detection**: Use temporal patterns to classify:
   - `EMERGING`: First 24 hours, velocity increasing
   - `DEVELOPING`: 24-72 hours, sustained coverage
   - `PEAK`: Velocity at local maximum
   - `FADING`: Velocity declining >50% from peak

**Key Implementation Details:**

- Use **DP-Means clustering** for story matching (allows dynamic cluster count)
- Store `core_entities` (Persons, Orgs, Locations) extracted via NER
- Entity overlap >60% + semantic similarity >0.85 = same story
- Generate `canonical_title` via LLM summarization of first 3 hourly snapshots

**Benefits for Hourly Digest:**

- "Hour 47 of the ongoing [Story Title]..."
- Reference prior digest coverage: "As we reported yesterday..."
- Detect story **milestones**: "This story has now persisted for 7 days"

---

## 2. Optimized Viral Velocity Weights

### Research Findings

Academic and industry research (2024-2025) indicates the following factors drive virality:

| Factor                                                       | Research-Backed Impact     | Suggested Weight |
| ------------------------------------------------------------ | -------------------------- | ---------------- |
| **High-arousal Emotions** (Anxiety, Awe, Anger, Excitement)  | +34% sharing increase      | **25-30%**       |
| **Engagement Velocity** (rate of likes/shares in first hour) | Primary algorithmic signal | **20-25%**       |
| **Practical Value** (how-to, useful content)                 | Consistent share driver    | **10%**          |
| **Social Currency** (makes sharer look good)                 | Key sharing motivation     | **10%**          |
| **Visual Quality** (stunning images, human faces)            | Significant CTR boost      | **10%**          |
| **Timing Freshness**                                         | Logarithmic decay          | **10%**          |
| **Category Alignment** (crisis, scandal, breakthrough)       | Viral category boost       | **10%**          |
| **Trend Alignment** (Google Trends match)                    | Information gap fill       | **5%**           |

### Recommended Formula (Research-Calibrated)

$$Z_v = 0.28(E_t) + 0.22(V_e) + 0.15(C_c) + 0.12(T_f) + 0.10(P_v) + 0.08(T_a) + 0.05(S_c)$$

**Where:**

- **$E_t$ (Emotional Triggers, 28%)**: GDELT GCAM high-arousal emotion score (Anxiety, Anger, Awe weighted 2x vs Sadness, Contentment)
- **$V_e$ (Velocity of Engagement, 22%)**: Rate of change in social signals over the hour (Bluesky + Mastodon + Reddit where available)
- **$C_c$ (Crisis/Category, 15%)**: Binary multiplier for "Viral Category" detection (CRISIS, SCANDAL, TECH_BREAKTHROUGH)
- **$T_f$ (Timing/Freshness, 12%)**: Logarithmic decay: `1 / (1 + log(hours_since_first_mention))`
- **$P_v$ (Practical Value, 10%)**: NLP classification score for "useful" content (how-to, tips, explainers)
- **$T_a$ (Trend Alignment, 8%)**: Semantic similarity to Google Trends "Rising Queries"
- **$S_c$ (Source Credibility, 5%)**: Source tier weighting (Tier 1 = 1.0, Tier 5 = 0.5)

### Adaptive Calibration (Optional Future Enhancement)

Implement an **online learning loop**:

1. Track post-publish engagement on the web dashboard + social posts
2. Log actual performance vs. predicted $Z_v$
3. Use gradient descent to adjust weights monthly
4. This transforms arbitrary weights into data-driven calibration

---

## 3. Contrarian Signal Detection

### The Concept

Detect stories that are **actively underreported** or where grassroots discussion diverges from mainstream coverage. This surfaces important stories being ignored and helps avoid echo-chamber effects.

### Proposed: Narrative Divergence Index ($N_d$)

**Algorithm:**

```python
def calculate_narrative_divergence(topic_cluster):
    # Step 1: Measure mainstream coverage volume
    mainstream_volume = count_articles(
        source=GDELT + NewsAPI,
        topic=topic_cluster,
        source_tier=[1, 2, 3]  # Major outlets
    )

    # Step 2: Measure grassroots discussion volume
    grassroots_volume = count_posts(
        source=[Bluesky, Mastodon, Reddit],
        topic=topic_cluster
    )

    # Step 3: Calculate divergence ratio
    expected_ratio = historical_average(mainstream / grassroots)
    actual_ratio = mainstream_volume / max(grassroots_volume, 1)

    divergence = expected_ratio / actual_ratio

    # divergence > 2.0 = Underreported (grassroots talking, MSM silent)
    # divergence < 0.5 = Overreported (MSM pushing, grassroots ignores)

    return divergence
```

**Contrarian Signal Categories:**

| Divergence Score  | Interpretation                  | Action                                                   |
| ----------------- | ------------------------------- | -------------------------------------------------------- |
| $N_d > 3.0$       | **Severely Underreported**      | Flag for manual review, potential "Hidden Story" feature |
| $2.0 < N_d < 3.0$ | **Underreported**               | Boost $Z_v$ by 15% to surface in digest                  |
| $0.5 < N_d < 2.0$ | **Normal Coverage**             | No adjustment                                            |
| $N_d < 0.5$       | **Overreported/Astroturf Risk** | Demote $Z_v$ by 10%, add skepticism flag                 |

**Data Sources for Grassroots Signal:**

- **Bluesky Firehose** (FREE, real-time, no auth required)
- **Mastodon Public Timeline API** (FREE with token, federated coverage)
- **Reddit** (expensive, use Lazy Loading pattern from blueprint)

**Implementation Notes:**

- Build a "Grassroots Topic Detector" that runs in parallel to GDELT ingestion
- Use same HDBSCAN clustering on social posts
- Cross-reference cluster centroids with GDELT clusters
- "Orphan" grassroots clusters (no GDELT match) = potential contrarian signals

---

## 4. Multimodal Image Collection

### The Vision

Capture the **visual zeitgeist** alongside the textual one. Trending memes, viral images, and visual narratives are equally important cultural signals.

### Architecture: Visual Signal Layer

```
┌─────────────────────────────────────────────────────────────┐
│                    VISUAL ZEITGEIST COLLECTOR               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   ┌─────────────────┐    ┌─────────────────┐               │
│   │  Bluesky Posts  │    │  Mastodon Posts │               │
│   │  (with images)  │    │  (with media)   │               │
│   └────────┬────────┘    └────────┬────────┘               │
│            │                      │                         │
│            └──────────┬───────────┘                         │
│                       ▼                                     │
│            ┌─────────────────────┐                          │
│            │  IMAGE PROCESSOR    │                          │
│            │  • Download image   │                          │
│            │  • Generate caption │                          │
│            │  • Extract embedding│                          │
│            │  • Detect meme/art  │                          │
│            └─────────┬───────────┘                          │
│                      ▼                                      │
│            ┌─────────────────────┐                          │
│            │  VISUAL CLUSTERING  │                          │
│            │  (CLIP embeddings)  │                          │
│            │  + HDBSCAN          │                          │
│            └─────────┬───────────┘                          │
│                      ▼                                      │
│            ┌─────────────────────┐                          │
│            │  VISUAL ZEITGEIST   │                          │
│            │  • Trending memes   │                          │
│            │  • Viral images     │                          │
│            │  • Visual themes    │                          │
│            └─────────────────────┘                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Key Components:**

1. **Image Collection**

   - Bluesky: Filter firehose for posts with attached images
   - Mastodon: Query `/api/v1/timelines/public?only_media=true`
   - Store image URLs + context (post text, author, timestamp)

2. **Image Processing Pipeline**

   - **Caption Generation**: Use Gemini 1.5 Flash multimodal to generate text description
   - **Embedding Generation**: CLIP (ViT-L/14) for visual embeddings (512-dim)
   - **Meme Detection**: Binary classifier to identify meme formats vs. photographs
   - **OCR**: Extract any text in images (meme captions, signs, etc.)

3. **Visual Clustering**

   - Cluster CLIP embeddings with HDBSCAN (same as text)
   - Identify "Visual Topics" (e.g., "AI Ghibli style images", "Political protest photos")
   - Cross-reference with textual clusters for multimodal stories

4. **Output Integration**
   - Add `visual_context` field to digest narratives
   - Include "Visual Trend of the Hour" section
   - Provide image references for illustration generation prompt

**Cost Optimization:**

- CLIP embeddings: Run locally (free, fast)
- Gemini 1.5 Flash for captions: ~$0.07/1M tokens, very cheap for images
- Only process images from posts with >N engagements (filter noise)

---

## 5. Infrastructure Recommendations (Budget: ~$30-50/month)

> [!TIP]
> Optimized for **~$50/month budget** using free Python libraries. Not real-time, but "near-real-time" (5-15 min delay).

### 5.1 GDELT BigQuery (FREE)

| Feature | Free Tier Limit | Notes |
|---------|----------------|-------|
| Query Processing | 1 TB/month | ✅ Optimized queries use ~200-300 GB/month |
| Storage | 10 GB/month | ✅ We query, don't store |

**Setup:** Google Cloud Sandbox (no credit card) → BigQuery → Add Public Datasets → GDELT

---

### 5.2 Python Library Stack (ALL FREE)

| Function | Library | Install |
|----------|---------|--------|
| **Google Trends** | `pytrends` | `pip install pytrends` |
| **Bluesky** | `atproto` | `pip install atproto` |
| **Mastodon** | `Mastodon.py` | `pip install Mastodon.py` |
| **News Text Extraction** | `trafilatura` | `pip install trafilatura` |
| **News Parsing** | `newspaper4k` | `pip install newspaper4k` |
| **JS-heavy Sites** | `playwright` | `pip install playwright` |

**Usage Examples:**

```python
# Google Trends (pytrends) - add delays to avoid rate limits
from pytrends.request import TrendReq
import time
pytrends = TrendReq(hl='en-US')
trending = pytrends.trending_searches(pn='united_states')
time.sleep(2)  # Rate limit protection

# Bluesky Firehose (atproto) - FREE real-time
from atproto import FirehoseSubscribeReposClient, parse_subscribe_repos_message
client = FirehoseSubscribeReposClient()
# Subscribe to all posts in real-time, no auth required

# Mastodon (Mastodon.py) - FREE with token
from mastodon import Mastodon
mastodon = Mastodon(access_token='token', api_base_url='https://mastodon.social')
timeline = mastodon.timeline_public(limit=40)

# News Scraping (trafilatura) - Best for article text
import trafilatura
html = trafilatura.fetch_url('https://example.com/article')
text = trafilatura.extract(html, include_comments=False)
```

---

### 5.3 Social Platform Summary (ALL FREE)

| Platform | Library | Cost | Real-time? |
|----------|---------|------|------------|
| **Bluesky** | `atproto` | FREE | ✅ Firehose |
| **Mastodon** | `Mastodon.py` | FREE | ✅ SSE |
| **Threads** | `playwright` scrape | FREE | ❌ Polled |
| Reddit | Skip (too expensive) | - | - |

---

### 5.4 Qdrant (FREE)

**Qdrant Cloud Free Tier:** 1GB forever = ~3 years of runway with quantization

---

### 5.5 Cost Breakdown

| Component | Cost |
|-----------|------|
| GDELT BigQuery | $0 |
| Social (Bluesky/Mastodon) | $0 |
| Trends (pytrends) | $0 |
| News (trafilatura) | $0 |
| Qdrant Cloud | $0 |
| **LLM APIs (Gemini Flash)** | **~$20-40** |
| **TOTAL** | **~$30-50/month** ✅ |

> [!NOTE]
> **Trade-off:** 5-15 min delay vs real-time. pytrends may need retry logic for rate limits.

---

## 6. Revised Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                           ZEITGEIST ENGINE v2.0                              │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                         SIGNAL ACQUISITION LAYER                        │ │
│  ├─────────────────────────────────────────────────────────────────────────┤ │
│  │                                                                         │ │
│  │   ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────────────┐   │ │
│  │   │  GDELT    │  │  Bluesky  │  │ Mastodon  │  │  Google Trends    │   │ │
│  │   │ BigQuery  │  │ (atproto) │  │(Mastodon.py)│ │    (pytrends)     │   │ │
│  │   │   FREE    │  │   FREE    │  │   FREE    │  │       FREE        │   │ │
│  │   └─────┬─────┘  └─────┬─────┘  └─────┬─────┘  └─────────┬─────────┘   │ │
│  │         │              │              │                  │             │ │
│  │         └──────────────┴──────────────┴──────────────────┘             │ │
│  │                                   │                                     │ │
│  └───────────────────────────────────┼─────────────────────────────────────┘ │
│                                      ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                       PROCESSING & ENRICHMENT                           │ │
│  ├─────────────────────────────────────────────────────────────────────────┤ │
│  │                                                                         │ │
│  │   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │ │
│  │   │ Dedup Sieve │  │  HDBSCAN    │  │   Story     │  │ Contrarian  │   │ │
│  │   │ (3-stage)   │→ │  Cluster    │→ │   Arc       │→ │  Signal     │   │ │
│  │   │             │  │             │  │  Matching   │  │  Detection  │   │ │
│  │   └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘   │ │
│  │                                                                         │ │
│  │   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                    │ │
│  │   │   Visual    │  │  Multimodal │  │   Viral     │                    │ │
│  │   │   Image     │→ │   CLIP      │→ │  Velocity   │                    │ │
│  │   │  Collector  │  │  Clustering │  │  Scoring    │                    │ │
│  │   └─────────────┘  └─────────────┘  └─────────────┘                    │ │
│  │                                                                         │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                       │
│                                      ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                         SEMANTIC MEMORY (Qdrant)                        │ │
│  │                           Free Tier → 1GB                               │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                       │
│                                      ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                       GENERATIVE SYNTHESIS                              │ │
│  ├─────────────────────────────────────────────────────────────────────────┤ │
│  │                                                                         │ │
│  │   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │ │
│  │   │ Gemini 1.5  │  │ Claude 3.5  │  │  GPT-4o     │  │ Illustration│   │ │
│  │   │   Flash     │→ │   Sonnet    │→ │   Judge     │→ │   Concept   │   │ │
│  │   │ (Ingestion) │  │ (Synthesis) │  │ (Verify)    │  │  Generator  │   │ │
│  │   └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘   │ │
│  │                                                                         │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                       │
│                                      ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                            OUTPUT LAYER                                 │ │
│  ├─────────────────────────────────────────────────────────────────────────┤ │
│  │                                                                         │ │
│  │   ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐        │ │
│  │   │  Web Dashboard  │  │  Social Posts   │  │   JSON API      │        │ │
│  │   │    (MVP)        │  │  (Automated)    │  │   (Future)      │        │ │
│  │   └─────────────────┘  └─────────────────┘  └─────────────────┘        │ │
│  │                                                                         │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 7. Summary of Recommendations

| Area                   | Recommendation                                                                      |
| ---------------------- | ----------------------------------------------------------------------------------- |
| **Story Arcs**         | Implement Story Arc Registry with entity-centric tracking + semantic fingerprinting |
| **Viral Weights**      | Use research-calibrated formula with Emotional Triggers at 28% primary weight       |
| **Contrarian Signals** | Calculate Narrative Divergence Index ($N_d$) comparing grassroots vs mainstream     |
| **Visual Zeitgeist**   | Collect images from Bluesky/Mastodon, cluster with CLIP embeddings                  |
| **GDELT**              | BigQuery free tier with query optimization |
| **News Scraping**      | `trafilatura` + `newspaper4k` (FREE) |
| **Trends**             | `pytrends` (FREE, rate-limited) |
| **Social**             | `atproto` (Bluesky) + `Mastodon.py` (FREE) |
| **Vector DB**          | Qdrant Cloud free tier (1GB) |

**Estimated Total Cost: ~$30-50/month** (LLM APIs only)

---

## Next Steps

1. [ ] Review and approve this research synthesis
2. [ ] Create updated `implementation_plan.md` with detailed technical specs
3. [ ] Begin implementation in phases:
   - Phase 1: GDELT + Bluesky integration
   - Phase 2: Dedup + Clustering pipeline
   - Phase 3: Story Arc tracking
   - Phase 4: Visual collection + Contrarian detection
   - Phase 5: Generative synthesis + Output
