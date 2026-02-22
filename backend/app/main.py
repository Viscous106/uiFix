# ==========================================================
# uiFix Backend — Final Production Version
# Gemini Vision + Quota Safe + Session Chat
# ==========================================================

import re
import uuid
import time
from typing import Dict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from models import AuditRequest, AuditResponse, Issue, ChatRequest, ChatResponse
from rag import analyze_ui, chat_with_context

from langchain_google_genai.chat_models import ChatGoogleGenerativeAIError


# ==========================================================
# FASTAPI INIT
# ==========================================================

app = FastAPI(title="uiFix Backend", version="2.0.0")


# ==========================================================
# CORS (Chrome Extension Support)
# ==========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Lock to chrome-extension://<id> in production
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


# ==========================================================
# CONFIG
# ==========================================================

MAX_CHAT_TURNS = 6
sessions: Dict[str, dict] = {}


# ==========================================================
# QUOTA SAFE WRAPPER
# ==========================================================

def safe_analyze_ui(dom_string: str, screenshot_base64: str | None):
    """
    Prevents 429 crashes.
    Retries once after waiting.
    """

    try:
        return analyze_ui(
            dom_string=dom_string,
            screenshot_base64=screenshot_base64,
        )

    except ChatGoogleGenerativeAIError as e:

        if "RESOURCE_EXHAUSTED" in str(e):
            print("\n⚠️ Gemini quota hit. Waiting 20 seconds before retry...\n")
            time.sleep(20)

            return analyze_ui(
                dom_string=dom_string,
                screenshot_base64=screenshot_base64,
            )

        raise e


# ==========================================================
# HEALTH CHECK
# ==========================================================

@app.get("/health")
def health():
    return {"status": "ok"}


# ==========================================================
# AUDIT ENDPOINT (VISION ENABLED)
# ==========================================================

@app.post("/audit", response_model=AuditResponse)
async def audit(request: AuditRequest):

    print(f"\n{'='*60}")
    print(f"[AUDIT] URL      : {request.page_url}")
    print(f"[AUDIT] Title    : {request.page_title}")
    print(f"[AUDIT] DOM size : {len(request.dom_string)} chars")
    print(f"{'='*60}\n")

    dom_context = (
        f"PAGE URL: {request.page_url or 'unknown'}\n"
        f"PAGE TITLE: {request.page_title or 'unknown'}\n\n"
        f"DOM STRUCTURE:\n{request.dom_string[:6000]}"
    )

    # 🔥 Vision multimodal call (DOM + Screenshot)
    raw_response = safe_analyze_ui(
        dom_string=dom_context,
        screenshot_base64=request.screenshot_base64 or None,
    )

    issues = parse_issues(raw_response)
    health_score = parse_health_score(raw_response)

    session_id = str(uuid.uuid4())

    sessions[session_id] = {
        "audit_context": raw_response,
        "history": [],
        "turns_used": 0,
    }

    return AuditResponse(
        issues=issues,
        ui_health_score=health_score,
        page_url=request.page_url,
        page_title=request.page_title,
        session_id=session_id,
    )


# ==========================================================
# CHAT ENDPOINT (6 TURN LIMIT)
# ==========================================================

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):

    session = sessions.get(request.session_id)

    if not session:
        raise HTTPException(
            status_code=404,
            detail="Session not found. Run an audit first."
        )

    if session["turns_used"] >= MAX_CHAT_TURNS:
        return ChatResponse(
            reply="This chat session has ended (6 turn limit reached). Run a new audit.",
            turns_used=session["turns_used"],
            turns_remaining=0,
            session_expired=True,
        )

    history_text = "\n".join(
        f"{msg['role'].upper()}: {msg['content']}"
        for msg in session["history"]
    ) or "No previous messages."

    try:
        reply = chat_with_context(
            audit_context=session["audit_context"],
            user_message=request.message,
        )
    except ChatGoogleGenerativeAIError as e:

        if "RESOURCE_EXHAUSTED" in str(e):
            return ChatResponse(
                reply="Gemini quota exceeded. Please try again later.",
                turns_used=session["turns_used"],
                turns_remaining=MAX_CHAT_TURNS - session["turns_used"],
                session_expired=False,
            )
        raise e

    session["history"].append({"role": "user", "content": request.message})
    session["history"].append({"role": "ai", "content": reply})
    session["turns_used"] += 1

    turns_remaining = MAX_CHAT_TURNS - session["turns_used"]

    return ChatResponse(
        reply=reply,
        turns_used=session["turns_used"],
        turns_remaining=turns_remaining,
        session_expired=(turns_remaining == 0),
    )


# ==========================================================
# OUTPUT PARSERS
# ==========================================================

def parse_health_score(text: str) -> int | None:
    match = re.search(r"UI_HEALTH_SCORE[:\s]+(\d+)", text, re.IGNORECASE)
    if match:
        return max(0, min(100, int(match.group(1))))
    return None


def parse_issues(text: str) -> list[Issue]:

    issues = []

    key_issues_match = re.search(
        r"KEY_ISSUES[:\s]+(.*?)(?:IMPROVEMENT_RECOMMENDATIONS|$)",
        text,
        re.DOTALL | re.IGNORECASE,
    )

    if not key_issues_match:
        return [Issue(description=text[:300], severity="medium")]

    block = key_issues_match.group(1).strip()

    lines = [
        l.strip()
        for l in block.splitlines()
        if l.strip().startswith("-")
    ]

    severity_map = {
        "critical": "critical",
        "high": "high",
        "medium": "medium",
        "low": "low",
    }

    for line in lines:
        content = line.lstrip("- ").strip()
        severity = "medium"

        sev_match = re.match(r"[\[\(](\w+)[\]\)]\s*", content)

        if sev_match:
            severity = severity_map.get(sev_match.group(1).lower(), "medium")
            content = content[sev_match.end():]

        parts = [p.strip() for p in content.split("|")]

        description = parts[0] if parts else content
        selector = None
        fix = None

        for part in parts[1:]:
            if part.lower().startswith("selector:"):
                selector = part.split(":", 1)[1].strip()
            elif part.lower().startswith("fix:"):
                fix = part.split(":", 1)[1].strip()

        if description:
            issues.append(
                Issue(
                    description=description,
                    severity=severity,
                    selector=selector,
                    fix=fix,
                )
            )

    return issues or [Issue(description=text[:300], severity="medium")]


# ==========================================================
# LOCAL RUN
# ==========================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)