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
from langchain_community.vectorstores import Chroma
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_community.embeddings import FakeEmbeddings

# History will be saved for 6 prompts only after then u have to work on new chat
MAX_TURNS = 6

CHAT_HISTORY_FILE = "chat-history.txt"

# Chat - History
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

# model
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0.3
)


rag_chain_template = ChatPromptTemplate.from_template("""
You are UIFix — a senior-level UI/UX Auditor and Frontend Architect.

You MUST use only the provided context as your reference knowledge.
Do not invent rules outside the given context.

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

=====================
IMPORTANT
=====================
- Be concise but authoritative.
- Do not hallucinate missing context.
- Think like a senior frontend engineer performing a professional audit.
""")


def analyze_ui(dom_string: str) -> str:
    """
    Build a fresh in-memory RAG chain from the live DOM string
    and run it through Gemini. Rebuilt per-request so every audit
    uses the actual page's content as context — not a stale file.

    TODO: Once VLM is implemented by the other team member, this
    function will also accept a vlm_description: str parameter and
    combine both DOM + visual context before embedding.
    """


    splitter = RecursiveCharacterTextSplitter(chunk_size=700, chunk_overlap=100)
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
    save_chat_history(dom_string[:200], response)
    return response


# Chat prompt — used for follow-up questions after an audit
chat_prompt = ChatPromptTemplate.from_template("""
You are UIFix — a senior-level UI/UX Auditor and Frontend Architect.

You previously audited a page and found these issues:

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

=====================
INSTRUCTIONS
=====================
Answer the user's question about the UI issues found.
You can explain issues in more depth, suggest code fixes, discuss backend connectivity
problems, UX trade-offs, or anything related to the audit results.
Be concise, practical, and direct. Think like a senior engineer pair-programming with the user.
""")


def chat_with_context(audit_context: str, chat_history: str, user_message: str) -> str:
    """
    Follow-up chat after an audit. Uses the original audit results as grounding
    context so the AI can answer questions about specific bugs found.

    audit_context: The issues + DOM summary from the initial /audit call
    chat_history:  Previous turns in this session (managed by main.py)
    user_message:  The user's current question
    """
    chain = chat_prompt | llm | StrOutputParser()
    response = chain.invoke({
        "audit_context": audit_context,
        "chat_history": chat_history,
        "question": user_message,
    })
    return response


# Chat Options 
if __name__ == "__main__":
    print("\nUIFix AI Chat Started")
    print("Type 'exit', 'quit', or 'stop' to end the conversation.\n")

    while True:
        if get_turn_count() >= MAX_TURNS:
            print("\nUIFix: Chat session limit reached (6 turns). Please start a new session.\n")
            break

        user_input = input("You: ")

        if user_input.lower() in ["exit", "quit", "stop"]:
            print("\nUIFix: Chat ended.\n")
            break

        response = analyze_ui(user_input)

        print("\nUIFix:\n")
        print(response)
        print("\n" + "-" * 60 + "\n")