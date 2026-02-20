# uiFix — Suggested Path & Architecture

## What We're Building

An AI-powered Chrome Extension that audits any webpage in one click — capturing a screenshot and intercepting network failures, then sending everything to a Python backend where **Gemini Vision** analyzes and returns structured UX + backend issues.

---

## Proposed Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     CHROME BROWSER                          │
│                                                             │
│  ┌──────────────────┐      ┌───────────────────────────┐   │
│  │   popup.html/js  │◄────►│     background.js         │   │
│  │  (Audit UI)      │      │  (Service Worker)         │   │
│  │                  │      │  • Intercepts network reqs │   │
│  │  • Trigger audit │      │  • Stores 4xx/5xx errors   │   │
│  │  • Show results  │      │  • captureVisibleTab()     │   │
│  └────────┬─────────┘      └───────────────────────────┘   │
│           │                                                  │
│  ┌────────▼─────────┐                                       │
│  │   content.js     │                                       │
│  │  (Page context)  │                                       │
│  │  • page URL      │                                       │
│  │  • page title    │                                       │
│  └──────────────────┘                                       │
│                                                             │
└─────────────────────────┬───────────────────────────────────┘
                          │  POST /audit
                          │  { screenshot_base64, network_errors,
                          │    page_url, page_title }
                          ▼
┌─────────────────────────────────────────────────────────────┐
│               PYTHON FASTAPI BACKEND                        │
│                                                             │
│  main.py                                                    │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  POST /audit                                        │   │
│  │  • Validate request (Pydantic)                      │   │
│  │  • Call ai_engine.run_audit()                       │   │
│  │  • Return AuditResponse JSON                        │   │
│  └──────────────────┬──────────────────────────────────┘   │
│                     │                                       │
│  ai_engine.py       ▼                                       │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Gemini 1.5 Flash (Vision)                          │   │
│  │  • Builds prompt: screenshot + network error log    │   │
│  │  • Forces JSON output via response schema           │   │
│  │  • Returns: ux_issues[], network_issues[], summary  │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                          │
                          │  AuditResponse JSON
                          ▼
             Rendered as cards in popup.html
```

---

## Data Flow (Step by Step)

1. User opens a broken webpage → background.js silently logs all 4xx/5xx requests
2. User clicks **"Audit Page"** in the popup
3. `popup.js` asks `background.js` for the captured network errors
4. `background.js` also calls `chrome.tabs.captureVisibleTab()` → returns base64 PNG
5. `popup.js` POSTs `{ screenshot_base64, network_errors, page_url }` to `localhost:8000/audit`
6. FastAPI validates the payload via Pydantic
7. `ai_engine.py` sends the screenshot + error log to Gemini 1.5 Flash
8. Gemini returns structured JSON → parsed into `AuditResponse`
9. Backend returns the JSON to the extension
10. `popup.js` renders UX issue cards + network error cards

---

## Proposed File Structure

```
uiFix/
├── extension/                   # Chrome Extension (MV3)
│   ├── manifest.json
│   ├── popup.html               # Audit UI — dark theme, Tailwind CDN
│   ├── popup.js                 # Audit trigger + result rendering
│   ├── background.js            # Service worker: network monitor + screenshot
│   ├── content.js               # Page context provider
│   └── icons/
│       ├── icon16.png
│       ├── icon48.png
│       └── icon128.png
│
├── backend/                     # Python FastAPI
│   ├── main.py                  # FastAPI app, CORS, /audit route
│   ├── models.py                # Pydantic request/response models
│   ├── ai_engine.py             # Gemini Vision integration
│   ├── requirements.txt
│   ├── .env.example             # GEMINI_API_KEY=
│   └── run.sh                   # uvicorn main:app --reload
│
├── dummy_site/                  # Deliberately broken test website
│   ├── index.html               # "TechStore" — bad contrast, broken images
│   ├── style.css                # UX anti-patterns baked in
│   └── app.js                   # fetch() calls that 404/500 on load
│
├── suggestedPath.md             # ← This file
├── stacks.md
└── README.md                    # Setup + demo guide
```

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| Extension UI | Vanilla HTML/JS + Tailwind CDN | Zero build step, fast |
| Extension APIs | Chrome MV3 (webRequest, scripting, tabs) | Required for network capture |
| Backend Framework | FastAPI + Uvicorn | Async, minimal boilerplate |
| Data Validation | Pydantic v2 | Forces structured AI output |
| AI Model | Gemini 1.5 Flash (Vision) | Free tier, multimodal, fast |
| AI SDK | `google-generativeai` (Python) | Official SDK |
| CORS | FastAPI CORSMiddleware | Allow `chrome-extension://*` |

---

## Implementation Plan

### Phase 1 — Backend (Hours 1–3)
- [ ] `models.py` — Define all Pydantic schemas
- [ ] `ai_engine.py` — Gemini prompt + structured JSON response
- [ ] `main.py` — FastAPI app with `/audit` and `/health`
- [ ] Test with `curl` + a sample base64 image

### Phase 2 — Extension (Hours 3–6)
- [ ] `manifest.json` — Permissions + service worker registration
- [ ] `background.js` — `webRequest` listener + `captureVisibleTab`
- [ ] `popup.html` — Dark-themed audit dashboard UI
- [ ] `popup.js` — Wire everything together, render results

### Phase 3 — Dummy Site (Hours 6–7)
- [ ] `index.html/style.css` — Broken UX for demo
- [ ] `app.js` — Intentional network failures

### Phase 4 — Integration & Polish (Hours 7–10)
- [ ] End-to-end test on dummy site
- [ ] README + demo script
- [ ] Final UI polish

---

## Key Design Decisions

- **Gemini over OpenAI/Anthropic**: The stack already specifies a Gemini key. Gemini 1.5 Flash is vision-capable and has a generous free tier — ideal for a hackathon.
- **No database**: All state is ephemeral (tab-level in background.js memory). Zero infra overhead.
- **Forced JSON**: Using Gemini's `response_mime_type="application/json"` with an explicit schema prevents hallucinated/malformed responses from crashing the extension.
- **Dummy site is the demo**: Build the broken TechStore page first, tune the prompts against it, then the live demo is a guaranteed pass.
