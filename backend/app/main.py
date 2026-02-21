import re
import uuid
from typing import Dict, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from models import AuditRequest, AuditResponse, Issue, ChatRequest, ChatResponse
from rag import analyze_ui, chat_with_context

app = FastAPI(title="uiFix Backend", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["Content-Type"],
)

# ---------------------------------------------------------------------------
# In-memory session store
# Each session holds:
#   - audit_context : str  → the original audit result (issues text) used as
#                           grounding for the follow-up chat
#   - history       : list → list of {"role": "user"/"ai", "content": str}
#   - turns_used    : int  → number of follow-up turns consumed (max 6)
# Sessions live only as long as the server is running (fine for the demo).
# ---------------------------------------------------------------------------
MAX_CHAT_TURNS = 6
sessions: Dict[str, dict] = {}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/audit", response_model=AuditResponse)
async def audit(request: AuditRequest):
    # ── DEBUG ─────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"[AUDIT] URL      : {request.page_url}")
    print(f"[AUDIT] Title    : {request.page_title}")
    print(f"[AUDIT] DOM size : {len(request.dom_string)} chars")
    print(f"[AUDIT] DOM preview:\n{request.dom_string[:500]}")
    print(f"{'='*60}\n")
    # ── END DEBUG ──────────────────────────────────────────────────────────

    # Build DOM context string for the RAG chain.
    # TODO: Once VLM is wired in, append vlm_description here.
    dom_context = (
        f"PAGE URL: {request.page_url or 'unknown'}\n"
        f"PAGE TITLE: {request.page_title or 'unknown'}\n\n"
        f"DOM STRUCTURE:\n{request.dom_string[:6000]}"
    )

    raw_response = analyze_ui(dom_context)

    issues = parse_issues(raw_response)
    health_score = parse_health_score(raw_response)

    # Create a new chat session pre-loaded with the audit results
    session_id = str(uuid.uuid4())
    sessions[session_id] = {
        "audit_context": raw_response,   # full LLM output as grounding context
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


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    session = sessions.get(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found. Run an audit first.")

    if session["turns_used"] >= MAX_CHAT_TURNS:
        return ChatResponse(
            reply="This chat session has ended (6 turn limit reached). Please run a new audit to start a fresh session.",
            turns_used=session["turns_used"],
            turns_remaining=0,
            session_expired=True,
        )

    # Format history as readable text for the prompt
    history_text = "\n".join(
        f"{msg['role'].upper()}: {msg['content']}"
        for msg in session["history"]
    ) or "No previous messages."

    reply = chat_with_context(
        audit_context=session["audit_context"],
        chat_history=history_text,
        user_message=request.message,
    )

    # Save this turn to session history
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


# ---------------------------------------------------------------------------
# Output parsers
# ---------------------------------------------------------------------------

def parse_health_score(text: str) -> int | None:
    match = re.search(r"UI_HEALTH_SCORE[:\s]+(\d+)", text, re.IGNORECASE)
    if match:
        return max(0, min(100, int(match.group(1))))
    return None


def parse_issues(text: str) -> list[Issue]:
    issues = []
    key_issues_match = re.search(
        r"KEY_ISSUES[:\s]+(.*?)(?:IMPROVEMENT_RECOMMENDATIONS|ARCHITECTURAL|$)",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if not key_issues_match:
        return [Issue(description=text[:300], severity="medium")]

    block = key_issues_match.group(1).strip()
    lines = [l.strip() for l in block.splitlines() if l.strip().startswith("-")]

    severity_map = {"critical": "critical", "high": "high", "medium": "medium", "low": "low"}

    for line in lines:
        content = line.lstrip("- ").strip()
        severity = "medium"
        sev_match = re.match(r"[\[\(](\w+)[\]\)]\s*", content)
        if sev_match:
            severity = severity_map.get(sev_match.group(1).lower(), "medium")
            content = content[sev_match.end():]

        parts = [p.strip() for p in content.split("|")]
        description = parts[0] if parts else content
        selector = fix = None
        for part in parts[1:]:
            if part.lower().startswith("selector:"):
                selector = part.split(":", 1)[1].strip()
            elif part.lower().startswith("fix:"):
                fix = part.split(":", 1)[1].strip()

        if description:
            issues.append(Issue(description=description, severity=severity, selector=selector, fix=fix))

    return issues or [Issue(description=text[:300], severity="medium")]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
