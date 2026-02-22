# uiFix — AI UI Debugger

> **Instant, multimodal UI audits powered by Gemini Vision.**
> uiFix is a Chrome Extension that captures your page's DOM and screenshot, sends them to a local AI backend, and returns actionable UI/UX findings — plus an interactive chat for follow-up questions.

---

## Features

- 🖼️ **Gemini Vision Audit** — screenshot + DOM sent together in one multimodal call
- 📊 **Weighted Health Score** — scored across 5 factors (Accessibility, Visual Design, UX, Semantic HTML, Performance)
- 🔍 **Click-to-Highlight** — click any issue to scroll and highlight the offending element on the page
- 📋 **Copy Fix** — one-click to copy the suggested fix to clipboard
- 💬 **Follow-up Chat** — 6-turn AI chat session tied to each audit
- ⚡ **Zero Cloud Infra** — runs entirely locally (FastAPI + Gemini API key)

---

## Quick Start

### 1. Clone and install

```bash
git clone <repo-url>
cd Kartikeya
python -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
```

### 2. Set your Gemini API key

```bash
echo "GOOGLE_API_KEY='your-key-here'" > .env
```

Get a free key at [aistudio.google.com/apikey](https://aistudio.google.com/apikey)

### 3. Start the backend

```bash
python backend/app/main.py
```

Server runs at `http://localhost:8000`

### 4. Load the Chrome extension

1. Open `chrome://extensions`
2. Enable **Developer Mode**
3. Click **Load unpacked** → select the `extension/` folder
4. Click the uiFix icon on any page → **Run Page Audit**

---

## Project Structure

```
Kartikeya/
├── extension/              # Chrome Extension (frontend)
│   ├── manifest.json       # Extension manifest (permissions, background)
│   ├── popup.html          # Extension popup UI
│   ├── popup.js            # Audit logic, score rendering, chat
│   ├── content.js          # Injected DOM scraper
│   ├── styles.css          # Popup styles
│   └── icons/              # Extension icons
│
└── backend/                # Python FastAPI backend
    ├── requirements.txt
    └── app/
        ├── main.py         # API routes, scoring, parsers
        ├── rag.py          # Gemini Vision prompt + chat engine
        └── models.py       # Pydantic request/response models
```

---

## How the Score Works

Each audit produces a **UI Health Score (0–100)** computed from real issues — not a number Gemini guesses.

| Factor | Weight | What it checks |
|---|---|---|
| Accessibility | 35% | Contrast, alt text, ARIA, labels, keyboard nav |
| Visual Design | 25% | Font sizes, spacing, colour hierarchy, tap targets |
| UX / Usability | 20% | Hover/focus states, navigation, error handling |
| Semantic HTML | 12% | Heading order, landmark roles, no divs-as-buttons |
| Performance | 8% | Image optimisation, DOM depth, render-blocking |

**Deductions per issue:** Critical −20 · High −12 · Medium −6 · Low −2

Each issue deducts from its specific factor. A site with no issues scores 100.

---

## API Reference

### `POST /audit`

Runs a full UI audit.

**Request**
```json
{
  "screenshot_base64": "<base64 PNG>",
  "dom_string": "<pruned HTML>",
  "page_url": "https://example.com",
  "page_title": "Example"
}
```

**Response**
```json
{
  "session_id": "uuid",
  "ui_health_score": 72,
  "issues": [
    {
      "description": "Low contrast on body text",
      "severity": "high",
      "selector": "p.body",
      "fix": "Change color to #222"
    }
  ],
  "page_url": "...",
  "page_title": "..."
}
```

### `POST /chat`

Follow-up question within an audit session (max 6 turns).

**Request**
```json
{ "session_id": "uuid", "message": "How do I fix the contrast issue?" }
```

**Response**
```json
{
  "reply": "...",
  "turns_used": 1,
  "turns_remaining": 5,
  "session_expired": false
}
```

### `GET /health`

Returns `{ "status": "ok" }` — use to check if backend is running.

---

## Environment Variables

| Variable | Description |
|---|---|
| `GOOGLE_API_KEY` | Gemini API key (saved to `.env`) |

---

## Requirements

- Python 3.11+
- Google Chrome
- Gemini API key (free tier works)