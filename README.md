# seoscout

> **From keywords to structured content — in one command.**

seoscout is a CLI tool for SEO professionals and content creators. Feed it a list of keywords, and it will:

- 🔍 **Search** YouTube (via yt-dlp) and Google (via Serper API) in parallel
- 📥 **Extract** YouTube video transcripts and full web page text (via Jina Reader)
- 📦 **Output** per-keyword JSON files you can use for article writing, competitive analysis, or content gap research

No more manually opening every search result and copy-pasting.

## Features

- **Parallel search** — YouTube + Google at the same time
- **Smart filtering** — filter by duration, topic relevance, and block competitor/spam domains
- **Caching** — each source is only extracted once; re-runs skip cached content
- **Proxy support** — rotating proxy for YouTube transcript extraction when IP-blocked
- **Content cleaning** — strips navigation, ads, breadcrumbs, and footer junk from web pages
- **Configurable** — control concurrency, rate limits, results per keyword via `.env`

## Quick Start

### Prerequisites

- Python 3.10+
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) installed (`pip install yt-dlp`)
- A [Serper API](https://serper.dev/) key (free tier available)
- A [Jina AI](https://jina.ai/) API key (optional, but recommended)

### Install

```bash
git clone https://github.com/Claire1940/seoscout.git
cd seoscout
pip install -e .
```

### Configure

```bash
cp .env.example .env
# Edit .env — at minimum, add your SERPER_API_KEY
```

### Prepare your keywords file

Create a JSON file with your keywords:

```json
{
  "topic_name": "My Game",
  "keywords": [
    "My Game beginner guide",
    "My Game best characters tier list",
    "My Game tips and tricks",
    "My Game walkthrough",
    "My Game how to level up fast"
  ]
}
```

> `topic_name` is optional. When set, search results that don't mention the topic in their title or snippet are automatically filtered out.

### Run

```bash
# Step 1: Search keywords → output/pending_review.json
seoscout search --keywords keywords.json

# Step 2 (optional): Review and edit pending_review.json
# Set "selected": false on items you don't want extracted

# Step 3: Extract content from selected items
seoscout extract --keywords keywords.json
```

Or do it all in one command:

```bash
seoscout run --keywords keywords.json
```

The project name is auto-derived from `topic_name` in your keywords file (lowercased, spaces replaced with `_`). If no `topic_name` is set, the filename is used instead.

You can also use it as a Python module:

```bash
python -m seoscout run --keywords keywords.json
```

## How It Works

```
keywords.json
     │
     ▼
┌─────────────────────────────┐
│  seoscout search             │  ← auto project name from topic_name
│  ┌───────────┐ ┌──────────┐ │
│  ┌───────────┐ ┌──────────┐ │
│  │  YouTube   │ │  Google  │ │
│  │  (yt-dlp)  │ │ (Serper) │ │
│  └─────┬─────┘ └────┬─────┘ │
│        └──────┬──────┘       │
│               ▼              │
│    pending_review.json       │
│    (review & filter)         │
└─────────────────────────────┘
              │
              ▼
┌─────────────────────────────┐
│  seoscout extract            │
│  ┌───────────┐ ┌──────────┐ │
│  │  YouTube   │ │   Web    │ │
│  │ transcripts│ │  (Jina)  │ │
│  └─────┬─────┘ └────┬─────┘ │
│        └──────┬──────┘       │
│               ▼              │
│     merged/*.json            │
│     (per-keyword content)    │
└─────────────────────────────┘
```

## Output Format

### pending_review.json (Step 1 output)

```json
{
  "version": "2.0",
  "created_at": "2026-06-10T12:00:00",
  "keywords": [
    {
      "keyword": "My Game beginner guide",
      "youtube": {
        "count": 2,
        "items": [
          {
            "title": "My Game Beginner Guide 2026",
            "url": "https://youtube.com/watch?v=xxx",
            "video_id": "xxx",
            "channel": "Gamer",
            "duration": "15:30",
            "duration_seconds": 930,
            "view_count": 50000,
            "selected": true
          }
        ]
      },
      "web": {
        "count": 5,
        "items": [
          {
            "title": "Complete Beginner Guide - My Game Wiki",
            "url": "https://example.com/guide",
            "domain": "example.com",
            "snippet": "Everything you need to know...",
            "selected": true
          }
        ]
      }
    }
  ]
}
```

Set `"selected": false` on items you don't want, then run `seoscout extract`.

### merged/*.json (Step 2 output)

One file per keyword (e.g. `my_game_beginner_guide.json`):

```json
{
  "keyword": "My Game beginner guide",
  "merged_at": "2026-06-10T12:05:00",
  "sources": {
    "youtube": {
      "count": 1,
      "videos": [
        {
          "type": "youtube",
          "title": "My Game Beginner Guide 2026",
          "url": "https://youtube.com/watch?v=xxx",
          "content": "Full transcript text here..."
        }
      ]
    },
    "web": {
      "count": 1,
      "pages": [
        {
          "type": "web",
          "title": "Complete Beginner Guide",
          "url": "https://example.com/guide",
          "content": "Cleaned web page content here..."
        }
      ]
    }
  },
  "total_sources": 2
}
```

## Configuration Reference

All settings go in `.env` (copy from `.env.example`).

### Required

| Variable | Description |
|----------|-------------|
| `SERPER_API_KEY` | Your [Serper.dev](https://serper.dev/) API key for Google search |

### Recommended

| Variable | Description |
|----------|-------------|
| `JINA_API_KEY` | Your [Jina AI](https://jina.ai/) API key for web page extraction (higher rate limits) |

### Output

| Variable | Default | Description |
|----------|---------|-------------|
| `OUTPUT_DIR` | `./output` | Root directory for all project data |

### YouTube Tuning

| Variable | Default | Description |
|----------|---------|-------------|
| `YOUTUBE_INITIAL_SEARCH_RESULTS` | `2` | Videos to fetch per keyword |
| `YOUTUBE_MAX_RESULTS_AFTER_FILTER` | `1` | Max videos to keep after filtering |
| `YOUTUBE_MAX_DURATION` | `3600` | Skip videos longer than this (seconds) |
| `YOUTUBE_EXTRACT_TOP_K` | `1` | How many transcripts to extract per keyword |
| `YOUTUBE_SEARCH_WORKERS` | `10` | Parallel search workers |
| `YOUTUBE_TRANSCRIPT_WORKERS` | `15` | Parallel transcript workers |

### Web Tuning

| Variable | Default | Description |
|----------|---------|-------------|
| `WEB_SEARCH_TOP_N` | `10` | Google results per keyword |
| `WEB_EXTRACT_TOP_K` | `1` | Pages to extract per keyword |
| `WEB_SEARCH_CONCURRENCY` | `5` | Serper API concurrency |
| `JINA_RPM` | `200` | Jina rate limit (requests/min) |
| `JINA_CONCURRENCY` | `20` | Jina parallel requests |
| `WEB_EXTRACT_RETRIES` | `3` | Retries for web extraction |

### Proxy (optional)

| Variable | Default | Description |
|----------|---------|-------------|
| `USE_PROXY` | `false` | Enable proxy |
| `TUNNEL_HOST` | _(empty)_ | Proxy host |
| `TUNNEL_PORT` | `18866` | Proxy port |
| `TUNNEL_USER` | _(empty)_ | Proxy username |
| `TUNNEL_PASS` | _(empty)_ | Proxy password |
| `TUNNEL_PROXY_FORMAT` | `standard` | `standard` or `tagged` (rotating proxy) |

### General

| Variable | Default | Description |
|----------|---------|-------------|
| `SEARCH_MAX_RETRIES` | `3` | Search retry attempts |
| `SEARCH_RETRY_DELAY` | `2` | Seconds between retries |
| `BLOCKED_DOMAINS` | `youtube.com,youtu.be,...` | Domains excluded from web results |

## FAQ

### yt-dlp not found

Make sure yt-dlp is installed and on your PATH:

```bash
pip install yt-dlp
yt-dlp --version
```

### YouTube transcript extraction fails

YouTube sometimes blocks IPs that make too many requests. Solutions:
1. Wait a few minutes and retry
2. Enable proxy in `.env` with a rotating proxy service
3. Reduce `YOUTUBE_TRANSCRIPT_WORKERS` to lower concurrency

### Serper API returns errors

- Check your API key is correct
- Free tier has rate limits; reduce `WEB_SEARCH_CONCURRENCY`
- Check your account balance at [serper.dev](https://serper.dev/)

### Web content is too short or empty

Some pages block automated extraction. Try:
- Reducing `JINA_CONCURRENCY` to avoid rate limits
- Adding a `JINA_API_KEY` for higher rate limits

## License

[MIT](LICENSE)
