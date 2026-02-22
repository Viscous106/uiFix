# uiFix — Architecture

## Overview

uiFix is a Chrome Extension + Python backend. The extension captures the active tab (DOM + screenshot) and sends it to a local FastAPI server, which runs a Gemini Vision audit and returns structured findings.

```
Browser Tab
    │
    │  (DOM + Screenshot)
    ▼
Chrome Extension (popup.js)
    │
    │  POST /audit  (JSON over HTTP)
    ▼
FastAPI Backend (main.py)
    │
    ├─► Gemini 2.5 Flash (rag.py)   ← multimodal: image + text
    │       │
    │       └─► Raw audit text
    │
    ├─► parse_issues()              ← extract [SEVERITY][CATEGORY] tags
    ├─► compute_scores_from_issues()← deterministic weighted score
    │
    └─► AuditResponse (JSON)
            │
            ▼
    Chrome Extension (popup.js)
        │
        ├─► renderIssues()          ← issue cards with click-to-highlight
        └─► renderScore()           ← health score + factor bars
```

---

## Components

### Chrome Extension

| File | Role |
|---|---|
| `manifest.json` | Declares permissions: `activeTab`, `scripting`, `tabs` |
| `content.js` | Injected into the page — scrapes and prunes DOM to ~400 elements |
| `popup.js` | Orchestrates audit: captures screenshot, calls `/audit`, renders results, handles `/chat` |
| `popup.html` | Extension UI: welcome → loading → results → chat |
| `styles.css` | Dark glassmorphism theme |

#### DOM Scraping (`content.js`)

The DOM is pruned before sending:
- Removes `script`, `style`, `iframe`, `svg`, `canvas`, `video`
- Strips all attributes except: `id`, `class`, `role`, `aria-*`, `type`, `name`, `placeholder`, `href`, `src`, `alt`
- Truncates text nodes to 50 chars
- Returns raw `innerHTML` string

#### Audit Flow (`popup.js`)

```
auditBtn.click
    │
    ├─ chrome.scripting.executeScript(content.js)  → domString
    ├─ chrome.tabs.captureVisibleTab()             → screenshotDataUrl
    │
    └─ fetch POST /audit { dom_string, screenshot_base64, page_url, page_title }
            │
            └─ on response:
                ├─ renderIssues(data.issues)
                ├─ renderScore(data.ui_health_score, data.factor_scores)
                └─ store session_id for /chat
```

---

### Python Backend

| File | Role |
|---|---|
| `main.py` | FastAPI routes, CORS, session store, parsers, scoring |
| `rag.py` | Gemini LLM setup, audit prompt, `analyze_ui()`, `chat_with_context()` |
| `models.py` | Pydantic models: `AuditRequest`, `AuditResponse`, `Issue`, `ChatRequest`, `ChatResponse` |

#### Audit Endpoint (`POST /audit`)

```python
1. Build dom_context string (URL + title + DOM)
2. safe_analyze_ui(dom_context, screenshot_base64)
       └─ analyze_ui() in rag.py
            └─ HumanMessage([text=prompt, image_url=screenshot])
            └─ llm.invoke([message])  → raw text
3. parse_issues(raw_text)
       └─ regex extracts [SEVERITY][CATEGORY] tags per issue
4. compute_scores_from_issues(issues)
       └─ deduct per severity from each factor (starts at 100)
       └─ weighted sum → overall score
5. Return AuditResponse
```

#### Gemini Vision Call (`rag.py`)

```python
message = HumanMessage(content=[
    {"type": "text",      "text": audit_prompt},
    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{screenshot}"}},
])
response = llm.invoke([message])
```

Model: `gemini-2.5-flash` (multimodal, handles image + text natively)

#### Scoring Algorithm (`main.py`)

```
FACTOR_WEIGHTS = {
    accessibility: 0.35,
    visual_design:  0.25,
    ux_usability:   0.20,
    semantic_html:  0.12,
    performance:    0.08,
}

SEVERITY_DEDUCTION = { critical: 20, high: 12, medium: 6, low: 2 }

for each issue:
    factor_scores[issue.category] -= SEVERITY_DEDUCTION[issue.severity]
    factor_scores[issue.category] = max(0, factor_scores[issue.category])

overall = Σ (factor_scores[k] × FACTOR_WEIGHTS[k])
```

#### Chat Session (`POST /chat`)

- Sessions stored in-memory dict (`sessions: Dict[str, dict]`)
- Each session holds `audit_context` (full raw audit output) + `history` + `turns_used`
- Max 6 turns per session (`MAX_CHAT_TURNS = 6`)
- `chat_with_context()` in `rag.py` uses `ChatPromptTemplate` with audit context + chat history

---

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────┐
│                    Chrome Extension                      │
│                                                          │
│  content.js ──► DOM string                               │
│  captureVisibleTab() ──► base64 PNG                      │
│                    │                                     │
│                    └──► POST /audit ──────────────────┐  │
└───────────────────────────────────────────────────────┼──┘
                                                        │
┌───────────────────────────────────────────────────────▼──┐
│                    FastAPI Backend                        │
│                                                          │
│  /audit                                                  │
│    ├─ analyze_ui(dom, screenshot)                        │
│    │     └─ Gemini 2.5 Flash ◄── [text + image]         │
│    │           └─ raw audit text                         │
│    ├─ parse_issues()  ◄── [SEVERITY][CATEGORY] regex     │
│    ├─ compute_scores_from_issues()                       │
│    └─ AuditResponse ──────────────────────────────────┐  │
│                                                       │  │
│  /chat                                                │  │
│    ├─ sessions[session_id]                            │  │
│    ├─ chat_with_context(audit_ctx, history, msg)      │  │
│    │     └─ Gemini 2.5 Flash ◄── chat prompt          │  │
│    └─ ChatResponse                                    │  │
└───────────────────────────────────────────────────────┼──┘
                                                        │
┌───────────────────────────────────────────────────────▼──┐
│                    Chrome Extension                      │
│                                                          │
│  renderIssues() ──► issue cards + click-to-highlight     │
│  renderScore()  ──► health score + factor bars           │
│  chat UI        ──► appendMessage() per turn             │
└─────────────────────────────────────────────────────────┘
```

---

## Key Design Decisions

| Decision | Rationale |
|---|---|
| **Direct Gemini Vision call** (no RAG/vector store) | Single multimodal call is faster, more accurate, and simpler than embedding → retrieval → generation |
| **Deterministic scoring** (not Gemini's self-reported number) | Gemini arithmetic is inconsistent; computing from parsed issues gives reproducible, explainable scores |
| **In-memory session store** | Simple, zero-dependency; sessions are short-lived (6 turns, single audit) |
| **DOM pruning in content.js** | Reduces payload from MBs to ~50KB; removes noise (scripts, SVGs, hidden elements) |
| **Quota-safe wrapper** (`safe_analyze_ui`) | Catches `RESOURCE_EXHAUSTED` from Gemini, waits 20s and retries once |

---

## Extension Permissions

```json
"permissions": ["activeTab", "scripting", "tabs"],
"host_permissions": ["http://localhost:8000/*"]
```

- `activeTab` — access current tab URL/title
- `scripting` — inject `content.js` to scrape DOM
- `tabs` — call `captureVisibleTab()` for screenshot
