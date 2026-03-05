"""
Generic Agent
=============
Answers platform knowledge questions using RAG (FAISS search).

Flow:
    User question
        → rag_search tool called
        → FaissRetriever searches knowledge/faiss_index/
        → returns relevant doc chunks
        → Groq LLM reads chunks and answers
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())
from langchain_groq import ChatGroq
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

# Make sure rag/ folder is importable
sys.path.insert(0, str(Path(__file__).parent.parent))
from rag.faiss_retriever import FaissRetriever

SYSTEM_PROMPT = """You are a helpful assistant for the Maveric O-RAN platform.

When answering questions:
1. Always use the rag_search tool to find relevant documentation first
2. Base your answer on what the search returns
3. If search returns nothing useful, say so honestly

Never guess or make up platform details."""


def create_generic_agent():
    """Build the Generic Agent with rag_search tool."""

    # Create retriever once — loads FAISS index from disk
    retriever = FaissRetriever()

    @tool
    def rag_search(query: str) -> str:
        """
        Search the Maveric platform knowledge base for relevant documentation.
        Use this for any question about the platform, components, or concepts.

        Args:
            query: Plain text search query describing what you need to know.

        Returns:
            Relevant documentation excerpts with source information.
        """
        results = retriever.search(query)
        return retriever.format_results(results)

    llm = ChatGroq(
        model=os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant"),
        temperature=0.0,
    )

    return create_react_agent(
        model=llm,
        tools=[rag_search],
        prompt=SYSTEM_PROMPT,
    )


async def run_generic_agent(query: str) -> str:
    """Run the Generic Agent and return the final response string."""
    agent = create_generic_agent()
    result = await agent.ainvoke({
        "messages": [{"role": "user", "content": query}]
    })
    # Walk messages in reverse to find the last real text response
    for msg in reversed(result.get("messages", [])):
        if hasattr(msg, "content") and msg.content:
            if not getattr(msg, "tool_calls", None):
                return msg.content
    return "No response generated."