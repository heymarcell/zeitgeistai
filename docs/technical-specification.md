# Zeitgeist Engine v2.0: Complete Technical Specification

> **Budget Target:** ~$16-20/month for LLM APIs
> **Output:** 1 article + 1 illustration every 4 hours (6 digests/day)
> **Last Updated:** January 2026

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Signal Acquisition Layer](#2-signal-acquisition-layer)
3. [Signal Processing](#3-signal-processing)
4. [Story Arc Tracking](#4-story-arc-tracking)
5. [Viral Velocity Scoring](#5-viral-velocity-scoring)
6. [Contrarian Signal Detection](#6-contrarian-signal-detection)
7. [Multimodal Image Collection](#7-multimodal-image-collection)
8. [Generative Synthesis](#8-generative-synthesis)
9. [Infrastructure & Cost](#9-infrastructure--cost)
10. [Architecture Diagram](#10-architecture-diagram)

---

## 1. Executive Summary

The Zeitgeist Engine captures the global attention landscape hourly, synthesizing news, social signals, and trends into a verified narrative with an illustration concept. The system uses:

- **GDELT** for global news signal detection
- **Bluesky + Mastodon** for social velocity
- **Google Trends** for search intent alignment
- **HDBSCAN clustering** for topic detection
- **RAG-based fact-checking** for accuracy
- **Tiered LLM synthesis** for content generation

### Key Differentiators

| Feature                   | Implementation                                                |
| ------------------------- | ------------------------------------------------------------- |
| **4-Hour Cadence**        | 6 digests/day at 02:00, 06:00, 10:00, 14:00, 18:00, 22:00 UTC |
| **Story Continuity**      | Story Arc Registry tracks multi-day narratives                |
| **Contrarian Detection**  | Surfaces underreported stories via divergence analysis        |
| **Visual Zeitgeist**      | Collects and clusters trending images/memes                   |
| **Zero-Trust Generation** | RAG fact-checking with 0.95 faithfulness threshold            |

---

## 2. Signal Acquisition Layer

### 2.1 GDELT Global Knowledge Graph (FREE)

The backbone for detecting thematic shifts in global news.

**Access:** Google BigQuery (free tier: 1TB/month)

**Key Fields:**

- `V2Themes`: Taxonomic themes with character offsets
- `Counts`: Physical activity quantifiers (PROTEST, ARREST, etc.)
- `GCAM`: Emotional tone analysis (high-arousal emotions weighted higher)

**Query Optimization:**

```sql
SELECT V2Themes, Counts, GCAM, DocumentIdentifier
FROM `gdelt-bq.gdeltv2.gkg`
WHERE DATE(_PARTITIONTIME) = CURRENT_DATE()
  AND _PARTITIONTIME >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 2 HOUR)
LIMIT 10000
```

---

### 2.2 Social Signal Sources (ALL FREE)

| Platform     | Library       | Access Type          | Auth Required |
| ------------ | ------------- | -------------------- | ------------- |
| **Bluesky**  | `atproto`     | Firehose (real-time) | ❌ No         |
| **Mastodon** | `Mastodon.py` | SSE streaming        | ⚠️ Token      |
| **Threads**  | `playwright`  | Scraping (polled)    | ❌ No         |

**Bluesky Firehose Example:**

```python
from atproto import FirehoseSubscribeReposClient, parse_subscribe_repos_message

client = FirehoseSubscribeReposClient()

def on_message(message):
    commit = parse_subscribe_repos_message(message)
    for op in commit.ops:
        if op.action == 'create' and 'app.bsky.feed.post' in op.path:
            # Extract text, images, engagement
            pass

client.start(on_message)
```

**Mastodon Public Timeline:**

```python
from mastodon import Mastodon

mastodon = Mastodon(
    access_token='your_token',
    api_base_url='https://mastodon.social'
)
timeline = mastodon.timeline_public(limit=40)
```

---

### 2.3 Google Trends (FREE via pytrends)

```python
from pytrends.request import TrendReq
import time

pytrends = TrendReq(hl='en-US', tz=360)

def get_trending_searches():
    trending = pytrends.trending_searches(pn='united_states')
    time.sleep(2)  # Rate limit protection
    return trending

def get_related_queries(keyword):
    pytrends.build_payload([keyword], timeframe='now 1-H')
    return pytrends.related_queries()
```

> ⚠️ **Rate Limiting:** Add 2-5 second delays between requests. Implement retry logic for 429 errors.

---

### 2.4 News Content Extraction (FREE)

| Library       | Best For                                      | Install                   |
| ------------- | --------------------------------------------- | ------------------------- |
| `trafilatura` | Clean article text extraction                 | `pip install trafilatura` |
| `newspaper4k` | Full article parsing (authors, dates, images) | `pip install newspaper4k` |
| `playwright`  | JS-rendered sites                             | `pip install playwright`  |

```python
import trafilatura

def extract_article(url):
    html = trafilatura.fetch_url(url)
    return trafilatura.extract(html, include_comments=False)
```

---

## 3. Signal Processing

### 3.1 Three-Stage Deduplication Sieve

| Stage | Algorithm    | Purpose                                         | Complexity |
| ----- | ------------ | ----------------------------------------------- | ---------- |
| 1     | SHA-256 hash | Exact duplicate removal                         | O(1)       |
| 2     | SimHash      | Near-duplicate detection (Hamming distance < 3) | O(n)       |
| 3     | SemDedup     | Semantic deduplication via embeddings           | O(n log n) |

### 3.2 HDBSCAN Clustering

HDBSCAN is **essential** for news because it:

- Handles variable-density clusters (major events vs. niche stories)
- Doesn't require pre-specifying cluster count (k)
- Marks noise points (low-quality content)

```python
from hdbscan import HDBSCAN
import numpy as np

clusterer = HDBSCAN(min_cluster_size=5, min_samples=3)
cluster_labels = clusterer.fit_predict(embeddings)
```

### 3.3 Vector Database (Qdrant - FREE)

**Qdrant Cloud Free Tier:** 1GB forever (~3 years of runway)

**Schema:**

```json
{
  "vector": [1536-dim float array],
  "payload": {
    "gkg_record_id": "string",
    "published_at": "ISO8601",
    "v2_themes": ["POLITICS", "CRISIS"],
    "virality_score": 0.85,
    "source_tier": 2,
    "entities": ["Person:Biden", "Org:NATO"]
  }
}
```

---

## 4. Story Arc Tracking

### The Problem

Hourly snapshots miss **narrative continuity**. A story spanning days/weeks should be recognized as ongoing.

### Solution: Story Arc Registry

```
┌─────────────────────────────────────────────────────────────┐
│                    STORY ARC REGISTRY                       │
├─────────────────────────────────────────────────────────────┤
│  story_id: UUID                                             │
│  story_fingerprint: vector (semantic centroid)              │
│  canonical_title: "NATO Summit Crisis Deepens"              │
│  first_seen_at: 2026-01-10T14:00:00Z                        │
│  last_seen_at: 2026-01-13T18:00:00Z                         │
│  hourly_snapshots: [zeitgeist_001, zeitgeist_047, ...]      │
│  core_entities: [NATO, Biden, Macron]                       │
│  narrative_phase: DEVELOPING                                │
│  cumulative_velocity: 847.3                                 │
└─────────────────────────────────────────────────────────────┘
```

### Algorithm

1. Compute cluster centroid (average embedding)
2. Compare against Story Arc Registry (cosine similarity > 0.85)
3. **Match → Link** to existing story
4. **No Match → Create** new story entry

### Narrative Phase Detection

| Phase        | Criteria                            |
| ------------ | ----------------------------------- |
| `EMERGING`   | First 24 hours, velocity increasing |
| `DEVELOPING` | 24-72 hours, sustained coverage     |
| `PEAK`       | Velocity at local maximum           |
| `FADING`     | Velocity declining >50% from peak   |

---

## 5. Viral Velocity Scoring

### Research-Calibrated Formula

$$Z_v = 0.28(E_t) + 0.22(V_e) + 0.15(C_c) + 0.12(T_f) + 0.10(P_v) + 0.08(T_a) + 0.05(S_c)$$

| Factor | Weight | Description                                                |
| ------ | ------ | ---------------------------------------------------------- |
| $E_t$  | 28%    | **Emotional Triggers** (high-arousal: anxiety, awe, anger) |
| $V_e$  | 22%    | **Velocity of Engagement** (social signal rate of change)  |
| $C_c$  | 15%    | **Crisis/Category** (viral category detection)             |
| $T_f$  | 12%    | **Timing/Freshness** (logarithmic decay)                   |
| $P_v$  | 10%    | **Practical Value** (how-to, tips, explainers)             |
| $T_a$  | 8%     | **Trend Alignment** (Google Trends match)                  |
| $S_c$  | 5%     | **Source Credibility** (tier weighting)                    |

### Diversity Re-Ranking

After scoring, apply diversity pass:

- If top 2 stories share same theme → demote 3rd occurrence
- Promote distinct themes (SCI_SPACE, ECON_CRYPTO) to ensure variety

---

## 6. Contrarian Signal Detection

### Narrative Divergence Index ($N_d$)

Detects stories where grassroots discussion diverges from mainstream coverage.

```python
def calculate_narrative_divergence(topic_cluster):
    mainstream_volume = count_gdelt_articles(topic_cluster)
    grassroots_volume = count_social_posts(topic_cluster)  # Bluesky + Mastodon

    expected_ratio = historical_average(mainstream / grassroots)
    actual_ratio = mainstream_volume / max(grassroots_volume, 1)

    return expected_ratio / actual_ratio
```

### Interpretation

| $N_d$     | Meaning                    | Action                 |
| --------- | -------------------------- | ---------------------- |
| > 3.0     | **Severely Underreported** | Flag as "Hidden Story" |
| 2.0 - 3.0 | **Underreported**          | Boost $Z_v$ by 15%     |
| 0.5 - 2.0 | **Normal Coverage**        | No adjustment          |
| < 0.5     | **Overreported/Astroturf** | Demote $Z_v$ by 10%    |

---

## 7. Multimodal Image Collection

### Visual Zeitgeist Pipeline

```
Social Firehose → Filter Images → Download → CLIP Embedding → HDBSCAN Cluster → Visual Topics
```

### Components

1. **Image Collection**

   - Bluesky: Filter posts with attached images
   - Mastodon: `/api/v1/timelines/public?only_media=true`

2. **Image Processing**

   - CLIP (ViT-L/14) for embeddings (512-dim) - runs locally, FREE
   - Gemini Flash for image captioning (~$0.07/1M tokens)
   - OCR for text extraction from memes

3. **Visual Clustering**
   - Same HDBSCAN approach as text
   - Cross-reference with textual clusters

### Output

- `visual_context` field in digest
- "Visual Trend of the Hour" section
- Image references for illustration prompts

---

## 8. Generative Synthesis

### 8.3 Detailed Cost Calculation (Per Hourly Digest)

**Assumptions:**

- 50 articles per cluster (after dedup)
- ~2,000 tokens per article summary
- Final digest: ~3,000 tokens output
- Illustration concept: ~500 tokens output

---

#### PREMIUM Configuration (Best Quality)

| Stage                          | Model             | Input Tokens | Output Tokens | Cost      |
| ------------------------------ | ----------------- | ------------ | ------------- | --------- |
| **1. Entity/Theme Extraction** | Gemini 2.5 Flash  | 100,000      | 10,000        | $0.014    |
| **2. Claim Detection**         | Gemini 2.5 Flash  | 50,000       | 5,000         | $0.007    |
| **3. Article Summarization**   | Gemini 3 Pro      | 100,000      | 20,000        | $0.225    |
| **4. Trend Analysis**          | Gemini 2.5 Flash  | 20,000       | 5,000         | $0.004    |
| **5. Narrative Synthesis**     | Claude Opus 4.5   | 30,000       | 3,000         | $0.225    |
| **6. Fact Verification**       | GPT-5.2           | 20,000       | 2,000         | $0.063    |
| **7. Illustration Concept**    | Claude Sonnet 4.5 | 5,000        | 500           | $0.023    |
| **TOTAL PER HOUR**             |                   |              |               | **$0.56** |

**Premium Monthly Cost: $0.56 × 24 × 30 = ~$403/month**

---

#### BALANCED Configuration (Quality + Budget)

| Stage                          | Model                 | Input Tokens | Output Tokens | Cost      |
| ------------------------------ | --------------------- | ------------ | ------------- | --------- |
| **1. Entity/Theme Extraction** | Gemini 2.5 Flash-Lite | 100,000      | 10,000        | $0.011    |
| **2. Claim Detection**         | Gemini 2.5 Flash-Lite | 50,000       | 5,000         | $0.005    |
| **3. Article Summarization**   | Gemini 3 Pro          | 100,000      | 20,000        | $0.225    |
| **4. Trend Analysis**          | Gemini 2.5 Flash-Lite | 20,000       | 5,000         | $0.003    |
| **5. Narrative Synthesis**     | Claude Sonnet 4.5     | 30,000       | 3,000         | $0.135    |
| **6. Fact Verification**       | Gemini 3 Pro          | 20,000       | 2,000         | $0.035    |
| **7. Illustration Concept**    | Gemini 2.5 Flash      | 5,000        | 500           | $0.001    |
| **TOTAL PER HOUR**             |                       |              |               | **$0.42** |

**Balanced Monthly Cost: $0.42 × 24 × 30 = ~$302/month**

---

#### BUDGET Configuration (~$50/month target)

| Stage                          | Model                 | Input Tokens | Output Tokens | Cost      |
| ------------------------------ | --------------------- | ------------ | ------------- | --------- |
| **1. Entity/Theme Extraction** | Gemini 2.5 Flash-Lite | 100,000      | 10,000        | $0.011    |
| **2. Claim Detection**         | Gemini 2.5 Flash-Lite | 50,000       | 5,000         | $0.005    |
| **3. Article Summarization**   | Gemini 2.5 Flash      | 100,000      | 20,000        | $0.018    |
| **4. Trend Analysis**          | Gemini 2.5 Flash-Lite | 20,000       | 5,000         | $0.003    |
| **5. Narrative Synthesis**     | Gemini 3 Pro          | 30,000       | 3,000         | $0.053    |
| **6. Fact Verification**       | Gemini 2.5 Flash      | 20,000       | 2,000         | $0.003    |
| **7. Illustration Concept**    | Gemini 2.5 Flash-Lite | 5,000        | 500           | $0.001    |
| **TOTAL PER HOUR**             |                       |              |               | **$0.09** |

**Budget Monthly Cost (24/7): $0.09 × 24 × 30 = ~$65/month**
**Budget Monthly Cost (12/day): $0.09 × 12 × 30 = ~$32/month** ✅

---

#### ULTRA-BUDGET Configuration (Mistral + Gemini)

| Stage                          | Model                 | Input Tokens | Output Tokens | Cost       |
| ------------------------------ | --------------------- | ------------ | ------------- | ---------- |
| **1. Entity/Theme Extraction** | Mistral Nemo          | 100,000      | 10,000        | $0.002     |
| **2. Claim Detection**         | Mistral Nemo          | 50,000       | 5,000         | $0.001     |
| **3. Article Summarization**   | Gemini 2.5 Flash-Lite | 100,000      | 20,000        | $0.014     |
| **4. Trend Analysis**          | Mistral Nemo          | 20,000       | 5,000         | $0.001     |
| **5. Narrative Synthesis**     | Gemini 2.5 Flash      | 30,000       | 3,000         | $0.004     |
| **6. Fact Verification**       | Gemini 2.5 Flash-Lite | 20,000       | 2,000         | $0.002     |
| **7. Illustration Concept**    | Mistral Nemo          | 5,000        | 500           | $0.000     |
| **TOTAL PER HOUR**             |                       |              |               | **$0.024** |

**Ultra-Budget Monthly (24/7): $0.024 × 24 × 30 = ~$17/month** 🎉

---

### 8.4 Recommended Configuration

**For ~$50/month budget with good quality:**

```
┌────────────────────────────────────────────────────────────────┐
│ RECOMMENDED MODEL STACK │
├────────────────────────────────────────────────────────────────┤
│ │
│ HIGH-VOLUME TASKS (cheap, fast) │
│ └── Gemini 2.5 Flash-Lite ($0.075/$0.30 per 1M) │
│ • Entity extraction │
│ • Claim detection │
│ • Trend analysis │
│ • Illustration concepts │
│ │
│ QUALITY-CRITICAL TASKS (balanced) │
│ └── Gemini 2.5 Flash ($0.10/$0.40 per 1M) │
│ • Article summarization │
│ • Fact verification │
│ │
│ CREATIVE TASKS (best output) │
│ └── Gemini 3 Pro ($1.25/$5.00 per 1M) │
│ • Final narrative synthesis │
│ • Story arc descriptions │
│ │
│ TOTAL: ~$0.09/hour = ~$65/month (24/7) │
│ ~$0.09/hour = ~$32/month (12 digests/day) │
│ │
└────────────────────────────────────────────────────────────────┘
```

> [!TIP] > **To upgrade quality later:** Swap Gemini 3 Pro → Claude Opus 4.5 for narrative (+$0.17/hour)
> **To cut costs further:** Use Mistral Nemo for extraction tasks (-$0.01/hour)

### Zero-Trust Verification Loop

1. **Claim Extraction**: Parse draft for check-worthy facts
2. **Evidence Retrieval**: Query Qdrant for source sentences
3. **Faithfulness Check**: Score must be ≥ 0.95
4. **Judge Review**: GPT-4o adversarial audit

### Illustration Concept Output

System generates **illustration concept**, not the image:

```json
{
  "concept": "Diplomatic summit in Brussels, tense atmosphere",
  "style": "Editorial illustration, muted colors",
  "mood": "Somber, high-stakes",
  "key_elements": ["Round table", "Multiple flags", "Documents"],
  "avoid": ["Text", "Specific faces", "Logos"]
}
```

---

## 9. Infrastructure & Cost

### Python Dependencies

```bash
pip install pytrends atproto Mastodon.py trafilatura newspaper4k playwright \
            hdbscan sentence-transformers qdrant-client google-cloud-bigquery
```

### Monthly Cost Breakdown

| Component                    | Cost               |
| ---------------------------- | ------------------ |
| GDELT BigQuery               | $0 (free tier)     |
| Bluesky (atproto)            | $0                 |
| Mastodon (Mastodon.py)       | $0                 |
| Google Trends (pytrends)     | $0                 |
| News scraping (trafilatura)  | $0                 |
| Qdrant Cloud                 | $0 (free 1GB tier) |
| **LLM APIs (6 digests/day)** | **~$16/month**     |
| **TOTAL**                    | **~$16-20/month**  |

### Publishing Schedule (UTC)

| Time  | Edition Name      | Primary Audience               |
| ----- | ----------------- | ------------------------------ |
| 02:00 | Overnight Edition | Asia afternoon, US overnight   |
| 06:00 | Dawn Edition      | Europe morning, US overnight   |
| 10:00 | Morning Brief     | US East morning, Europe midday |
| 14:00 | Afternoon Update  | US afternoon, Europe evening   |
| 18:00 | Evening Digest    | US evening, Europe night       |
| 22:00 | Night Report      | US West evening, Asia morning  |

### Trade-offs vs Paid Stack

| Aspect             | Free Stack       | Paid Stack |
| ------------------ | ---------------- | ---------- |
| Latency            | 5-15 min delay   | Real-time  |
| Trends reliability | May need retries | Stable     |
| Maintenance        | Some required    | Minimal    |

---

## 10. Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                           ZEITGEIST ENGINE v2.0                              │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                         SIGNAL ACQUISITION                              │ │
│  ├─────────────────────────────────────────────────────────────────────────┤ │
│  │   GDELT          Bluesky        Mastodon       Google Trends            │ │
│  │   (BigQuery)     (atproto)      (Mastodon.py)  (pytrends)               │ │
│  │   FREE           FREE           FREE           FREE                     │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                       │
│                                      ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                         PROCESSING LAYER                                │ │
│  ├─────────────────────────────────────────────────────────────────────────┤ │
│  │   3-Stage        HDBSCAN        Story Arc      Contrarian               │ │
│  │   Dedup    →     Cluster   →    Matching  →    Detection                │ │
│  │                                                                         │ │
│  │   Visual         CLIP           Viral                                   │ │
│  │   Collector →    Cluster   →    Scoring                                 │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                       │
│                                      ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                    SEMANTIC MEMORY (Qdrant FREE)                        │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                       │
│                                      ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                       GENERATIVE SYNTHESIS                              │ │
│  ├─────────────────────────────────────────────────────────────────────────┤ │
│  │   Gemini Flash → Claude Sonnet → GPT-4o Judge → Illustration Concept    │ │
│  │   (Extract)      (Synthesize)    (Verify)       (Generate)              │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                       │
│                                      ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                            OUTPUT LAYER                                 │ │
│  ├─────────────────────────────────────────────────────────────────────────┤ │
│  │   Web Dashboard              Social Posts               JSON API        │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

## 11. Deployment & Output Configuration

### 11.1 Decisions Summary

| Setting              | Decision           |
| -------------------- | ------------------ |
| **Language**         | English only       |
| **Geographic Scope** | Global             |
| **Hosting**          | Cloudflare Workers |
| **Database**         | PayloadCMS         |
| **Dashboard**        | Simple static site |
| **Social Platforms** | Bluesky + Mastodon |

---

### 11.2 Infrastructure Stack

```
┌─────────────────────────────────────────────────────────────────┐
│                    CLOUDFLARE DEPLOYMENT                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌─────────────────┐     ┌─────────────────┐                   │
│   │  Cron Trigger   │────▶│ Worker (Python) │                   │
│   │  Every 4 hours  │     │  zeitgeist-engine│                  │
│   └─────────────────┘     └────────┬────────┘                   │
│                                    │                            │
│          ┌────────────────────────┐│┌────────────────────┐     │
│          ▼                        ▼▼                     ▼     │
│   ┌─────────────┐    ┌─────────────────┐    ┌──────────────┐   │
│   │ PayloadCMS  │    │  Qdrant Cloud   │    │ R2 Storage   │   │
│   │  (Digests)  │    │   (Vectors)     │    │  (Images)    │   │
│   └─────────────┘    └─────────────────┘    └──────────────┘   │
│          │                                                      │
│          ▼                                                      │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │               OUTPUT DISTRIBUTION                        │  │
│   ├─────────────────────────────────────────────────────────┤  │
│   │  Static Site     Bluesky API      Mastodon API          │  │
│   │  (CF Pages)      (atproto)        (Mastodon.py)         │  │
│   └─────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

### 11.3 Social Platform Posting

**Primary Platforms (FREE APIs):**

| Platform     | Library       | Auth         | Rate Limit       |
| ------------ | ------------- | ------------ | ---------------- |
| **Bluesky**  | `atproto`     | App password | 1,666 posts/hour |
| **Mastodon** | `Mastodon.py` | OAuth token  | 300 posts/hour   |

**Bluesky Posting:**

```python
from atproto import Client

def post_to_bluesky(text: str, image_url: str = None):
    client = Client()
    client.login('handle.bsky.social', 'app-password')

    if image_url:
        # Upload image first
        with open(image_path, 'rb') as f:
            blob = client.upload_blob(f.read())
        embed = {'$type': 'app.bsky.embed.images', 'images': [{'image': blob, 'alt': ''}]}
        client.post(text=text, embed=embed)
    else:
        client.post(text=text)
```

**Mastodon Posting:**

```python
from mastodon import Mastodon

def post_to_mastodon(text: str, image_path: str = None):
    mastodon = Mastodon(
        access_token='your_token',
        api_base_url='https://mastodon.social'
    )

    if image_path:
        media = mastodon.media_post(image_path, description='Zeitgeist illustration')
        mastodon.status_post(text, media_ids=[media['id']])
    else:
        mastodon.status_post(text)
```

**Post Format:**

```
🌐 Zeitgeist | 14:00 UTC

📰 [Headline]

[2-3 sentence summary with key facts]

🔗 Read full digest: https://zeitgeist.app/digest/2026-01-13-14

#Zeitgeist #News #GlobalNews
```

---

### 11.4 PayloadCMS Schema

```typescript
// collections/Digests.ts
export const Digests: CollectionConfig = {
  slug: "digests",
  fields: [
    { name: "digestId", type: "text", required: true },
    { name: "publishedAt", type: "date", required: true },
    { name: "edition", type: "text" }, // "Morning Brief", etc.
    { name: "headline", type: "text", required: true },
    { name: "summary", type: "textarea", required: true },
    { name: "fullContent", type: "richText" },
    { name: "illustrationConcept", type: "json" },
    {
      name: "sources",
      type: "array",
      fields: [
        { name: "url", type: "text" },
        { name: "title", type: "text" },
        { name: "source", type: "text" },
      ],
    },
    { name: "storyArcs", type: "relationship", relationTo: "story-arcs" },
    { name: "viralityScore", type: "number" },
    {
      name: "topics",
      type: "array",
      fields: [{ name: "topic", type: "text" }],
    },
  ],
};
```

---

### 11.5 Cloudflare Worker Cron

```javascript
// src/index.js
export default {
  async scheduled(event, env, ctx) {
    // Runs every 4 hours: 02:00, 06:00, 10:00, 14:00, 18:00, 22:00 UTC
    ctx.waitUntil(generateDigest(env));
  },

  async fetch(request, env) {
    // Manual trigger endpoint
    if (request.url.includes("/trigger")) {
      await generateDigest(env);
      return new Response("Digest generated");
    }
    return new Response("Zeitgeist Engine");
  },
};

// wrangler.toml
// [triggers]
// crons = ["0 2,6,10,14,18,22 * * *"]
```

---

## 12. Next Steps (Implementation Order)

### Phase 0: Setup (Day 1)

- [ ] Create project repository
- [ ] Set up Python environment with dependencies
- [ ] Configure `.env` with API keys
- [ ] Set up Qdrant Cloud free tier
- [ ] Set up Google Cloud + BigQuery access

### Phase 1: Data Collection (Week 1)

- [ ] Implement GDELT BigQuery ingestion
- [ ] Implement Bluesky Jetstream collector
- [ ] Implement Mastodon multi-instance sampler
- [ ] Implement pytrends with caching
- [ ] Add rate limiting and error handling

### Phase 2: Processing (Week 2)

- [ ] Implement 3-stage deduplication
- [ ] Implement UMAP + HDBSCAN clustering
- [ ] Implement Story Arc Registry
- [ ] Implement viral velocity scoring
- [ ] Add contrarian signal detection

### Phase 3: Generation (Week 3)

- [ ] Set up Gemini API client with circuit breaker
- [ ] Implement entity/claim extraction
- [ ] Implement narrative synthesis
- [ ] Implement multi-layer fact verification
- [ ] Add illustration concept generator

### Phase 4: Output (Week 4)

- [ ] Set up PayloadCMS on Cloudflare
- [ ] Create digest storage logic
- [ ] Implement Bluesky posting
- [ ] Implement Mastodon posting
- [ ] Build static site with CF Pages

### Phase 5: Operations (Week 5)

- [ ] Deploy to Cloudflare Workers
- [ ] Set up cron triggers
- [ ] Add Discord/Slack alerting
- [ ] Create monitoring dashboard
- [ ] Write operational documentation

---

## 13. Project Files Structure

```
zeitgeistai/
├── src/
│   ├── collectors/
│   │   ├── gdelt.py
│   │   ├── bluesky.py
│   │   ├── mastodon.py
│   │   └── trends.py
│   ├── processors/
│   │   ├── dedup.py
│   │   ├── clustering.py
│   │   ├── story_arc.py
│   │   └── scoring.py
│   ├── generators/
│   │   ├── synthesis.py
│   │   ├── verification.py
│   │   └── illustration.py
│   ├── publishers/
│   │   ├── payload.py
│   │   ├── bluesky.py
│   │   └── mastodon.py
│   ├── config.py
│   └── main.py
├── tests/
├── docs/
├── .env.example
├── requirements.txt
├── wrangler.toml
└── README.md
```
