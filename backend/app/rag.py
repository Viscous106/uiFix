# Calling API KEY
import os
from dotenv import load_dotenv
load_dotenv()

from langchain_google_genai import ChatGoogleGenerativeAI

from langchain_core.prompts import ChatPromptTemplate
from langchain_community.vectorstores import Chroma
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough


# History section:=>

CHAT_HISTORY_FILE = "user_chat-history.txt"

def load_chat_history():
    if not os.path.exists(CHAT_HISTORY_FILE):
        return ""
    with open(CHAT_HISTORY_FILE, "r", encoding="utf-8") as f:
        return f.read()

def save_chat_history(user_input, ai_output):
    with open(CHAT_HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(f"USER: {user_input}\n")
        f.write(f"AI: {ai_output}\n\n")


#Calling LLM Model
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0.3
)

loader = TextLoader("File_structure.txt") # FILE WILL CHANGE when we will get 
documents = loader.load()

#Splitting the filrd into smaller chuinks
splitter = RecursiveCharacterTextSplitter(
    chunk_size=700,
    chunk_overlap=100
)

chunks = splitter.split_documents(documents)

from langchain_community.embeddings import FakeEmbeddings
embedding_model = FakeEmbeddings(size=384)

#Converting embeddings into vector format
vector = Chroma.from_documents(
    documents=chunks,
    embedding=embedding_model,
    persist_directory="./chroma_db"
)

# Retrieving from vector embedding
retriever = vector.as_retriever(search_kwargs={"k": 3})

# Systen Prompt 
prompt = ChatPromptTemplate.from_template("""
You are UIFix — a senior-level UI/UX Auditor and Frontend Architect.

You MUST use only the provided context as your reference knowledge.
Do not invent rules outside the given context.

=====================
CHAT HISTORY
=====================
{chat_history}

=====================
DESIGN CONTEXT
=====================
{context}

=====================
USER INPUT
=====================
{input}

=====================
OBJECTIVE
=====================

Analyze the UI based on the provided context and user input.

If the input represents:
- A UI structure
- A DOM summary
- A file structure
- A frontend component
- A design description

Then perform a professional evaluation.

=====================
ANALYSIS REQUIREMENTS
=====================

1. Provide a UI Health Score (0–100) if applicable.
2. Identify structural issues.
3. Identify accessibility issues.
4. Identify UX and hierarchy problems.
5. Identify maintainability or architectural weaknesses.
6. Suggest concrete, actionable improvements.
7. If relevant, generate improved frontend code.

Code generation rules:
- Use the most appropriate frontend approach based on the input.
- Do NOT assume a specific framework.
- If no framework is specified, use clean semantic HTML + modern CSS.
- Ensure accessibility best practices.
- Ensure responsive design.
- Ensure production-level cleanliness.

=====================
OUTPUT FORMAT
=====================

UI_HEALTH_SCORE: <number or N/A>

KEY_ISSUES:
- ...
- ...

IMPROVEMENT_RECOMMENDATIONS:
- ...
- ...

ARCHITECTURAL_SUGGESTIONS:
- ...
- ...

IMPROVED_FRONTEND_CODE (if applicable):
<code block here>

=====================
IMPORTANT
=====================
- Be concise but authoritative.
- Do not hallucinate missing context.
- If context is insufficient, clearly state what is missing.
- Think like a senior frontend engineer performing a professional audit.
""")

# Langchain Chain (pipeline)
rag_chain = (
    {
        "context": retriever,
        "input": RunnablePassthrough(),
        "chat_history": lambda x: load_chat_history()
    }
    | prompt
    | llm
    | StrOutputParser()
)

#output
def analyze_ui(user_input: str):
    response = rag_chain.invoke(user_input)
    save_chat_history(user_input, response)
    return response

# Continous chat feature
if __name__ == "__main__":
    print("\nUIFix AI Chat Started")
    print("Type 'exit', 'quit', or 'stop' to end the conversation.\n")

    while True:
        user_input = input("You: ")

        if user_input.lower() in ["exit", "quit", "stop"]:
            print("\nUIFix: Chat ended.\n")
            break

        response = analyze_ui(user_input)

        print("\nUIFix:\n")
        print(response)
        print("\n" + "-" * 60 + "\n")