# Calling AI-Key
import os
from dotenv import load_dotenv, set_key
load_dotenv()

# --- API Key Guard ---
DOTENV_PATH = os.path.join(os.path.dirname(__file__), "../../.env")

def ensure_api_key():
    key = os.getenv("GOOGLE_API_KEY")
    if not key or key.strip() == "":
        print("\n⚠️  No Gemini API key found.")
        key = input("🔑 Enter your Google Gemini API key: ").strip()
        if not key:
            raise ValueError("API key is required. Get one at https://aistudio.google.com/apikey")
        set_key(DOTENV_PATH, "GOOGLE_API_KEY", key)
        os.environ["GOOGLE_API_KEY"] = key
        print("✅ API key saved to .env\n")
    else:
        print("✅ Gemini API key loaded.\n")

ensure_api_key()

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import FakeEmbeddings

# History limit (USED ONLY FOR CLI MODE)
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
# MODEL
# -------------------------

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0.3
)

# -------------------------
# AUDIT PROMPT
# -------------------------

rag_chain_template = ChatPromptTemplate.from_template("""
You are UIFix — a senior-level UI/UX Auditor and Frontend Architect.

=====================
CHAT HISTORY
=====================
{chat_history}

=====================
DOM CONTEXT
=====================
{context}

=====================
USER INPUT
=====================
{input}

=====================
OBJECTIVE
=====================

Analyze the UI based on the provided DOM context and user input.

=====================
ANALYSIS REQUIREMENTS
=====================

1. Provide a UI Health Score (0–100).
2. Identify structural issues.
3. Identify accessibility issues.
4. Identify UX and hierarchy problems.
5. Suggest concrete, actionable improvements.

=====================
OUTPUT FORMAT
=====================

UI_HEALTH_SCORE: <number or N/A>

KEY_ISSUES:
- [SEVERITY] Description | selector: <css selector if known> | fix: <short fix suggestion>

IMPROVEMENT_RECOMMENDATIONS:
- ...
""")


# -------------------------
# MAIN AUDIT FUNCTION
# -------------------------

def analyze_ui(dom_string: str) -> str:

    # 🚀 REMOVED SESSION LIMIT CHECK HERE
    # Audit should NEVER be blocked

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=700,
        chunk_overlap=100
    )

    docs = splitter.create_documents([dom_string])

    embedding_model = FakeEmbeddings(size=384)
    vector = Chroma.from_documents(documents=docs, embedding=embedding_model)
    retriever = vector.as_retriever(search_kwargs={"k": 3})

    rag_chain = (
        {
            "context": retriever,
            "input": RunnablePassthrough(),
            "chat_history": lambda x: load_chat_history()
        }
        | rag_chain_template
        | llm
        | StrOutputParser()
    )

    response = rag_chain.invoke(dom_string)

    # Save history ONLY for CLI mode
    save_chat_history(dom_string[:200], response)

    return response


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


def chat_with_context(audit_context: str, chat_history: str, user_message: str) -> str:
    chain = chat_prompt | llm | StrOutputParser()
    response = chain.invoke({
        "audit_context": audit_context,
        "chat_history": chat_history,
        "question": user_message,
    })
    return response


# -------------------------
# CLI MODE ONLY
# -------------------------

if __name__ == "__main__":

    print("\nUIFix AI Chat Started")
    print("Type 'exit', 'quit', or 'stop' to end the conversation.\n")

    while True:

        if get_turn_count() >= MAX_TURNS:
            print("\n🚫 UIFix: Session limit reached (6 interactions).")
            print("👉 Please open a NEW browser tab to start a fresh audit session.\n")
            break

        user_input = input("You: ")

        if user_input.lower() in ["exit", "quit", "stop"]:
            print("\nUIFix: Chat ended.\n")
            break

        response = analyze_ui(user_input)

        print("\nUIFix:\n")
        print(response)
        print("\n" + "-" * 60 + "\n")