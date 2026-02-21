from pydantic import BaseModel
from typing import List, Optional


class AuditRequest(BaseModel):
    screenshot_base64: str      # PNG screenshot from chrome.tabs.captureVisibleTab
    dom_string: str             # Pruned DOM HTML from content.js
    page_url: Optional[str] = None
    page_title: Optional[str] = None


class Issue(BaseModel):
    description: str            # Human-readable description of the issue
    severity: str               # "low" | "medium" | "high" | "critical"
    selector: Optional[str] = None   # CSS selector of the offending element
    fix: Optional[str] = None        # Suggested fix


class AuditResponse(BaseModel):
    issues: List[Issue]
    ui_health_score: Optional[int] = None   # 0–100
    page_url: Optional[str] = None
    page_title: Optional[str] = None
    session_id: str                         # UUID — used for follow-up /chat calls


class ChatRequest(BaseModel):
    session_id: str             # Must match the session_id from /audit
    message: str                # User's follow-up question


class ChatResponse(BaseModel):
    reply: str                  # AI's response
    turns_used: int             # How many of the 6 turns have been used
    turns_remaining: int        # How many turns are left
    session_expired: bool = False  # True when all 6 turns are exhausted
