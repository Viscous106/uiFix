# ==========================================================
# UIFix AI — Final Version (Gemini Vision + Chat History)
# ==========================================================

# -------------------------
# API KEY SETUP
# -------------------------

import os
from dotenv import load_dotenv, set_key

load_dotenv()

DOTENV_PATH = os.path.join(os.path.dirname(__file__), "../../.env")


def ensure_api_key():
    key = os.getenv("GOOGLE_API_KEY")

    if not key or key.strip() == "":
        print("\n⚠️  No Gemini API key found.")
        key = input("🔑 Enter your Google Gemini API key: ").strip()

        if not key:
            raise ValueError(
                "API key is required. Get one at https://aistudio.google.com/apikey"
            )

        set_key(DOTENV_PATH, "GOOGLE_API_KEY", key)
        os.environ["GOOGLE_API_KEY"] = key
        print("✅ API key saved to .env\n")
    else:
        print("✅ Gemini API key loaded.\n")


ensure_api_key()

# -------------------------
# IMPORTS
# -------------------------

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import HumanMessage


# -------------------------
# CONFIG
# -------------------------

MAX_TURNS = 6
CHAT_HISTORY_FILE = "chat-history.txt"


# -------------------------
# CHAT HISTORY FUNCTIONS
# -------------------------

def load_chat_history():
    if not os.path.exists(CHAT_HISTORY_FILE):
        return ""

    with open(CHAT_HISTORY_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()

    exchanges = []
    temp = []

    for line in lines:
        temp.append(line)
        if line.strip() == "":
            exchanges.append("".join(temp))
            temp = []

    exchanges = exchanges[-MAX_TURNS:]
    return "\n".join(exchanges)


def save_chat_history(user_input, ai_output):
    with open(CHAT_HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(f"USER: {user_input}\n")
        f.write(f"AI: {ai_output}\n\n")


def get_turn_count():
    if not os.path.exists(CHAT_HISTORY_FILE):
        return 0

    with open(CHAT_HISTORY_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    return content.count("USER:")


# -------------------------
# MODEL (Gemini Vision)
# -------------------------

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0.3,
)


# -------------------------
# MAIN AUDIT FUNCTION
# -------------------------

def analyze_ui(dom_string: str, screenshot_base64: str = None) -> str:
    """
    Analyzes UI using:
    - DOM string
    - Optional screenshot (base64 PNG)

    Uses Gemini 2.5 Flash (Vision-enabled).
    """

    chat_history = load_chat_history()

    audit_prompt = f"""
You are UIFix — a senior-level UI/UX Auditor and Frontend Architect.

=====================
CHAT HISTORY
=====================
{chat_history}

=====================
DOM STRUCTURE
=====================
{dom_string[:6000]}

=====================
OBJECTIVE
=====================

Analyze this UI using BOTH:
- The DOM structure
- The screenshot image (if provided)

=====================
ANALYSIS REQUIREMENTS
=====================

1. Provide a UI Health Score (0–100).
2. Identify accessibility issues.
3. Identify UX and hierarchy problems.
4. Identify structural / semantic issues.
5. Suggest concrete, actionable fixes.

=====================
OUTPUT FORMAT (STRICT)
=====================

UI_HEALTH_SCORE: <number>

KEY_ISSUES:
- [SEVERITY] Description | selector: <css selector if identifiable> | fix: <short fix>

IMPROVEMENT_RECOMMENDATIONS:
- ...
"""

    # -------------------------
    # MULTIMODAL MESSAGE
    # -------------------------

    if screenshot_base64:
        print(
            f"\n🖼️  [VISION MODE] Screenshot received — {len(screenshot_base64)} chars\n"
        )

        message = HumanMessage(
            content=[
                {"type": "text", "text": audit_prompt},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{screenshot_base64}"
                    },
                },
            ]
        )
    else:
        message = HumanMessage(content=audit_prompt)

    response = llm.invoke([message])
    result = response.content if hasattr(response, "content") else str(response)

    print(f"\n🤖 Gemini Response Preview:\n{result[:300]}")
    print("=" * 60)

    save_chat_history(dom_string[:200], result)

    return result


# -------------------------
# FOLLOW-UP CHAT MODE
# -------------------------

chat_prompt = ChatPromptTemplate.from_template("""
You are UIFix — a senior-level UI/UX Auditor and Frontend Architect.

=====================
AUDIT RESULTS
=====================
{audit_context}

=====================
CONVERSATION HISTORY
=====================
{chat_history}

=====================
USER QUESTION
=====================
{question}

Be concise, practical, and direct.
""")


def chat_with_context(audit_context: str, user_message: str) -> str:
    chat_history = load_chat_history()

    chain = chat_prompt | llm | StrOutputParser()

    response = chain.invoke(
        {
            "audit_context": audit_context,
            "chat_history": chat_history,
            "question": user_message,
        }
    )

    save_chat_history(user_message, response)

    return response


# -------------------------
# CLI MODE
# -------------------------

if __name__ == "__main__":

    print("\n🚀 UIFix AI Chat Started")
    print("Type 'exit', 'quit', or 'stop' to end.\n")

    while True:

        if get_turn_count() >= MAX_TURNS:
            print("\n🚫 Session limit reached (6 interactions).")
            print("👉 Open a new tab for a fresh session.\n")
            break

        user_input = input("You: ")

        if user_input.lower() in ["exit", "quit", "stop"]:
            print("\nUIFix: Chat ended.\n")
            break

        # For CLI we treat input as DOM (no screenshot)
        response = analyze_ui(user_input)

        print("\nUIFix:\n")
        print(response)
        print("\n" + "-" * 60 + "\n")