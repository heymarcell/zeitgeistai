# 🌐 Zeitgeist Engine

> AI-powered global news digest that captures the world's attention every 4 hours.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![uv](https://img.shields.io/badge/uv-package%20manager-blueviolet.svg)](https://github.com/astral-sh/uv)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## What is Zeitgeist?

Zeitgeist Engine is an autonomous AI system that:

- 📡 **Ingests** global news from GDELT, Bluesky, Mastodon, and Google Trends
- 🧠 **Analyzes** patterns using HDBSCAN clustering and viral velocity scoring
- ✍️ **Generates** fact-checked narratives with illustration concepts
- 📢 **Publishes** to a web dashboard and social platforms automatically

**Output:** One comprehensive digest + illustration concept every 4 hours (6x daily).

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) package manager
- Google Cloud account (for BigQuery free tier)
- Gemini API key

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/zeitgeistai.git
cd zeitgeistai

# Install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e ".[dev]"

# Copy environment template
cp .env.example .env
# Edit .env with your API keys
```

### Run

```bash
# Generate a single digest
uv run python -m src.main

# Or use the CLI
uv run zeitgeist
```

---

## 📊 Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    ZEITGEIST ENGINE v2.0                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  SIGNAL ACQUISITION                                             │
│  ├── GDELT BigQuery ────────────── Global news themes           │
│  ├── Bluesky Jetstream ─────────── Real-time social signal      │
│  ├── Mastodon API ──────────────── Federated social signal      │
│  └── Google Trends (pytrends) ──── Search intent                │
│                                                                 │
│  PROCESSING                                                     │
│  ├── SHA-256 Deduplication ─────── Exact duplicate removal      │
│  ├── UMAP + HDBSCAN ────────────── Topic clustering             │
│  └── Viral Velocity Scoring ────── Research-calibrated ranking  │
│                                                                 │
│  GENERATION                                                     │
│  ├── Gemini 2.5 Flash-Lite ─────── Entity & claim extraction    │
│  ├── Gemini 2.5 Flash ──────────── Summarization                │
│  └── Gemini 3 Pro ──────────────── Final narrative writing      │
│                                                                 │
│  OUTPUT                                                         │
│  ├── JSON File ─────────────────── Local storage                │
│  ├── Bluesky ───────────────────── Social post                  │
│  └── Mastodon ──────────────────── Social post                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📁 Project Structure

```
zeitgeistai/
├── src/
│   ├── collectors/          # Data ingestion
│   │   ├── gdelt.py         # GDELT BigQuery client
│   │   ├── bluesky.py       # Bluesky API consumer
│   │   ├── mastodon.py      # Mastodon multi-instance sampler
│   │   └── trends.py        # Google Trends with caching
│   ├── processors/          # Signal processing
│   │   ├── dedup.py         # SHA-256 deduplication
│   │   ├── clustering.py    # UMAP + HDBSCAN
│   │   └── scoring.py       # Viral velocity calculation
│   ├── generators/          # Content generation
│   │   └── synthesis.py     # LLM narrative generation
│   ├── publishers/          # Output distribution
│   │   ├── bluesky.py       # Bluesky posting
│   │   └── mastodon.py      # Mastodon posting
│   ├── config.py            # Configuration management
│   └── main.py              # Pipeline orchestrator
├── docs/                    # Documentation
├── tests/                   # Test suite
├── output/                  # Generated digests
├── .env.example             # Environment template
├── pyproject.toml           # Project config (uv)
└── README.md
```

---

## ⚙️ Configuration

Edit `.env` with your credentials:

```env
# Google Cloud (BigQuery for GDELT)
GOOGLE_APPLICATION_CREDENTIALS=path/to/service-account.json

# LLM API
GEMINI_API_KEY=your_key

# Social Platforms
BLUESKY_HANDLE=your.handle.bsky.social
BLUESKY_APP_PASSWORD=your_app_password
MASTODON_ACCESS_TOKEN=your_token
MASTODON_INSTANCE=https://mastodon.social
```

See [.env.example](.env.example) for all options.

---

## 📅 Publishing Schedule

| Time (UTC) | Edition Name      | Primary Audience             |
| ---------- | ----------------- | ---------------------------- |
| 02:00      | Overnight Edition | Asia afternoon, US overnight |
| 06:00      | Dawn Edition      | Europe morning               |
| 10:00      | Morning Brief     | US East morning              |
| 14:00      | Afternoon Update  | US afternoon                 |
| 18:00      | Evening Digest    | US evening                   |
| 22:00      | Night Report      | US West evening              |

---

## 💰 Cost Breakdown

| Component         | Monthly Cost   |
| ----------------- | -------------- |
| GDELT BigQuery    | $0 (free tier) |
| Bluesky API       | $0             |
| Mastodon API      | $0             |
| Google Trends     | $0             |
| LLM APIs (Gemini) | ~$16           |
| **Total**         | **~$16/month** |

---

## 🧪 Development

```bash
# Install with dev dependencies
uv pip install -e ".[dev]"

# Run tests
uv run pytest

# Run with coverage
uv run pytest --cov=src --cov-report=html

# Lint code
uv run ruff check src/

# Type check
uv run mypy src/
```

---

## 📚 Documentation

| Document                                                   | Description                  |
| ---------------------------------------------------------- | ---------------------------- |
| [Technical Specification](docs/technical-specification.md) | Full system design           |
| [MVP Scope](docs/mvp-scope.md)                             | What's in the MVP            |
| [Risk Analysis](docs/risk-analysis.md)                     | Known issues and mitigations |
| [Research Synthesis](docs/research-synthesis.md)           | Background research          |

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.
