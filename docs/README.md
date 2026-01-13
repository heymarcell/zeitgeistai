# Zeitgeist Engine Documentation

Welcome to the Zeitgeist Engine documentation. This folder contains all technical documentation for the project.

## Documents

| Document                                                | Description                                    |
| ------------------------------------------------------- | ---------------------------------------------- |
| [Technical Specification](./technical-specification.md) | Complete system architecture and design        |
| [MVP Scope](./mvp-scope.md)                             | Minimum Viable Product definition and timeline |
| [Risk Analysis](./risk-analysis.md)                     | Known issues, gaps, and mitigations            |
| [Research Synthesis](./research-synthesis.md)           | Background research and findings               |
| [Original Blueprint](./original-blueprint.md)           | Initial design document                        |

## Quick Links

- **Getting Started**: See [README.md](../README.md)
- **Configuration**: See [.env.example](../.env.example)
- **Source Code**: See [src/](../src/)

## Architecture Overview

```
GDELT + Bluesky + Mastodon + Trends
           ↓
    Dedup → Cluster → Score
           ↓
    Gemini LLM Synthesis
           ↓
    JSON + Bluesky + Mastodon
```

## Key Decisions

- **Frequency**: Every 4 hours (6 digests/day)
- **LLM Stack**: Gemini 2.5 Flash-Lite → Flash → 3 Pro
- **Social**: Bluesky + Mastodon (both free APIs)
- **Hosting**: Cloudflare Workers (planned)
- **Cost Target**: ~$16/month
