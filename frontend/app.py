"""
Streamlit Frontend
==================
Chat interface for NetAI Copilot with MongoDB chat history.

Features:
- Saves all messages to MongoDB
- Retrieves chat history on startup
- Unique session per browser

Run locally:
    streamlit run frontend/app.py
"""

import asyncio
import os
import sys
import requests
import uuid
from pathlib import Path
from datetime import datetime

import streamlit as st

# Make agents/ and rag/ importable from the project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.router import route
from agents.generic_agent import run_generic_agent
from agents.debugger_agent import run_debugger_agent

# Configuration
CHAT_API_URL = os.environ.get("CHAT_API_URL", "http://localhost:8001")
TENANT_ID = "00000000-0000-0000-3029-000000000001"  # Default tenant

# Page config
st.set_page_config(page_title="NetAI Copilot", page_icon="🤖")
st.title("🤖 NetAI Copilot")
st.caption(
    "Ask me anything about the Maveric platform. "
    
)


def get_or_create_session_id():
    """Get or create a unique session ID for this user"""
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
    return st.session_state.session_id


def save_message_to_db(role: str, content: str):
    """Save a message to MongoDB via the API"""
    try:
        session_id = get_or_create_session_id()
        
        response = requests.post(
            f"{CHAT_API_URL}/chat/messages",
            json={
                "tenant_id": TENANT_ID,
                "session_id": session_id,
                "role": role,
                "content": content,
                "metadata": {
                    "timestamp_saved": datetime.utcnow().isoformat()
                }
            },
            timeout=5
        )
        
        if response.status_code == 200:
            st.session_state.db_connected = True
            return True
        else:
            st.session_state.db_connected = False
            st.warning(f"⚠️ Could not save message to database: {response.text}")
            return False
    
    except requests.exceptions.ConnectionError:
        st.session_state.db_connected = False
        st.warning("⚠️ Chat API not available - messages won't be saved to database")
        return False
    except Exception as e:
        st.session_state.db_connected = False
        st.warning(f"⚠️ Error saving message: {str(e)}")
        return False


def load_chat_history_from_db():
    """Load chat history from MongoDB for this session"""
    try:
        session_id = get_or_create_session_id()
        
        response = requests.get(
            f"{CHAT_API_URL}/chat/messages/{session_id}",
            timeout=5
        )
        
        if response.status_code == 200:
            st.session_state.db_connected = True
            data = response.json()
            messages = data.get("messages", [])
            
            # Convert MongoDB format to Streamlit format
            for msg in messages:
                st.session_state.messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
            
            return len(messages)
        else:
            st.session_state.db_connected = False
            return 0
    
    except requests.exceptions.ConnectionError:
        st.session_state.db_connected = False
        return 0
    except Exception as e:
        st.session_state.db_connected = False
        return 0


# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.db_connected = False
    st.session_state.history_loaded = False

# Load chat history from MongoDB on first load
if not st.session_state.history_loaded:
    with st.spinner("Loading chat history..."):
        message_count = load_chat_history_from_db()
        st.session_state.history_loaded = True
        
        if message_count > 0:
            st.success(f"✅ Loaded {message_count} messages from history")

# Show DB connection status
session_id = get_or_create_session_id()
if st.session_state.db_connected:
    st.info(f"✅ Connected to database | Session: {session_id[:8]}...")
else:
    st.info(f"⚠️ Database disconnected | Messages won't persist | Session: {session_id[:8]}...")

# Display all previous messages
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# Chat input
if user_input := st.chat_input("Type your message..."):

    # Append user message to session state
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    # Save to database
    save_message_to_db("user", user_input)
    
    # Show user message
    with st.chat_message("user"):
        st.write(user_input)

    # Get agent response
    agent_type = route(user_input)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                if agent_type == "debugger":
                    response = asyncio.run(run_debugger_agent(user_input))
                else:
                    response = asyncio.run(run_generic_agent(user_input))
            except Exception as e:
                response = f"Sorry, I encountered an error: {str(e)}"
        
        st.write(response)

    # Append assistant message to session state
    st.session_state.messages.append({"role": "assistant", "content": response})
    
    # Save to database
    save_message_to_db("assistant", response)

