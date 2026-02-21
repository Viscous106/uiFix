# Calling API KEY
import os
from dotenv import load_dotenv
load_dotenv()

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.vectorstores import Chroma
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

llm = ChatGoogleGenerativeAI(
    model="gemini-1.5-flash",
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

embedding_model = GoogleGenerativeAIEmbeddings(
    model="models/embedding-001"
)

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
        "input": RunnablePassthrough()
    }
    | prompt
    | llm
    | StrOutputParser()
)

#output
def analyze_ui(user_input: str):
    return rag_chain.invoke(user_input)