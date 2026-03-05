"""
Chat History API
================
Stores and retrieves chat messages from MongoDB.

The frontend calls this API to save user messages and AI responses.

Flow:
    Frontend (Streamlit)
        → saves messages to this API
        → this API stores in MongoDB
        → frontend can retrieve history anytime

Run locally (with MongoDB):
    docker run -d --name netai-mongodb -p 27017:27017 -e MONGO_INITDB_ROOT_USERNAME=admin -e MONGO_INITDB_ROOT_PASSWORD=password123 mongo:latest
    python -m uvicorn main:app --reload --port 8001

Run locally (without MongoDB - messages won't persist):
    uvicorn main:app --port 8001
"""

import json
import logging
import os
from pathlib import Path
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# MongoDB connection settings
MONGODB_URL = os.environ.get("MONGODB_URL", "mongodb://admin:password123@localhost:27017/netai_copilot?authSource=admin")

# Global MongoDB client and database
mongo_client = None
db = None


# Pydantic models for request/response
class ChatMessage(BaseModel):
    """Schema for a chat message"""
    tenant_id: str
    session_id: str
    role: str  # "user" or "assistant"
    content: str
    metadata: Optional[dict] = None


class ChatMessageResponse(BaseModel):
    """Response with message and MongoDB ID"""
    _id: str
    timestamp: str
    tenant_id: str
    session_id: str
    role: str
    content: str
    metadata: Optional[dict] = None


def connect_to_mongodb():
    """Try to connect to MongoDB"""
    global mongo_client, db
    
    try:
        mongo_client = MongoClient(MONGODB_URL, serverSelectionTimeoutMS=5000)
        # Verify connection works
        mongo_client.admin.command('ping')
        db = mongo_client.netai_copilot
        logger.info("✅ Connected to MongoDB")
        return True
    except (ConnectionFailure, ServerSelectionTimeoutError, Exception) as e:
        logger.warning(f"⚠️  Could not connect to MongoDB: {e}")
        logger.info("Chat history will NOT persist without MongoDB")
        db = None
        return False


# Create FastAPI app
app = FastAPI(title="NetAI Copilot Chat History API")


# Connect to MongoDB on startup
@app.on_event("startup")
async def startup_event():
    """Connect to MongoDB when app starts"""
    connect_to_mongodb()


@app.on_event("shutdown")
async def shutdown_event():
    """Close MongoDB connection when app stops"""
    global mongo_client
    if mongo_client:
        mongo_client.close()
        logger.info("MongoDB connection closed")


@app.post("/chat/messages")
def save_chat_message(message: ChatMessage) -> dict:
    """
    Save a chat message to MongoDB.
    
    Args:
        message: ChatMessage with tenant_id, session_id, role (user/assistant), content
    
    Returns:
        Saved message with _id and timestamp
    """
    
    if db is None:
        raise HTTPException(
            status_code=503, 
            detail="MongoDB not available - chat history not persisted"
        )
    
    try:
        # Create document with timestamp
        doc = {
            "tenant_id": message.tenant_id,
            "session_id": message.session_id,
            "role": message.role,
            "content": message.content,
            "timestamp": datetime.utcnow(),
            "metadata": message.metadata or {}
        }
        
        logger.info(f"Saving {message.role} message for session {message.session_id}")
        
        result = db.chat_history.insert_one(doc)
        doc["_id"] = str(result.inserted_id)
        doc["timestamp"] = doc["timestamp"].isoformat()
        
        return {
            "success": True,
            "message": doc
        }
    
    except Exception as e:
        logger.error(f"Error saving message: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/chat/messages/{session_id}")
def get_chat_history(session_id: str, limit: int = 100) -> dict:
    """
    Get all messages for a session.
    
    Args:
        session_id: The unique session ID
        limit: Maximum messages to return (default 100)
    
    Returns:
        List of chat messages in chronological order
    """
    
    if db is None:
        logger.warning("MongoDB not available - cannot retrieve chat history")
        return {"messages": [], "note": "MongoDB not available"}
    
    try:
        logger.info(f"Fetching chat history for session {session_id}")
        
        messages = list(db.chat_history.find(
            {"session_id": session_id}
        ).sort("timestamp", 1).limit(limit))
        
        # Convert MongoDB objects for JSON serialization
        for msg in messages:
            msg["_id"] = str(msg["_id"])
            if isinstance(msg.get("timestamp"), datetime):
                msg["timestamp"] = msg["timestamp"].isoformat()
        
        logger.info(f"Found {len(messages)} messages in session {session_id}")
        return {
            "success": True,
            "session_id": session_id,
            "message_count": len(messages),
            "messages": messages
        }
    
    except Exception as e:
        logger.error(f"Error fetching chat history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/chat/messages/{session_id}")
def delete_session_history(session_id: str) -> dict:
    """
    Delete all messages for a session.
    
    Args:
        session_id: The unique session ID
    
    Returns:
        Number of messages deleted
    """
    
    if db is None:
        raise HTTPException(status_code=503, detail="MongoDB not available")
    
    try:
        logger.info(f"Deleting chat history for session {session_id}")
        
        result = db.chat_history.delete_many({"session_id": session_id})
        
        return {
            "success": True,
            "session_id": session_id,
            "messages_deleted": result.deleted_count
        }
    
    except Exception as e:
        logger.error(f"Error deleting session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/chat/sessions/{tenant_id}")
def get_tenant_sessions(tenant_id: str) -> dict:
    """
    Get all unique sessions for a tenant.
    
    Args:
        tenant_id: The tenant UUID
    
    Returns:
        List of session IDs and message counts
    """
    
    if db is None:
        return {"sessions": [], "note": "MongoDB not available"}
    
    try:
        logger.info(f"Fetching sessions for tenant {tenant_id}")
        
        # Group by session_id and count messages
        pipeline = [
            {"$match": {"tenant_id": tenant_id}},
            {"$group": {
                "_id": "$session_id",
                "message_count": {"$sum": 1},
                "last_message": {"$max": "$timestamp"}
            }},
            {"$sort": {"last_message": -1}}
        ]
        
        sessions = list(db.chat_history.aggregate(pipeline))
        
        # Convert timestamps to ISO format
        for session in sessions:
            if isinstance(session.get("last_message"), datetime):
                session["last_message"] = session["last_message"].isoformat()
        
        return {
            "success": True,
            "tenant_id": tenant_id,
            "session_count": len(sessions),
            "sessions": sessions
        }
    
    except Exception as e:
        logger.error(f"Error fetching sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
def health():
    """Health check endpoint"""
    status = "connected" if db is not None else "disconnected"
    return {
        "status": "ok",
        "mongodb": status,
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/health/db")
def health_db():
    """Check MongoDB connection specifically"""
    if db is None:
        return {
            "status": "not_connected",
            "message": "MongoDB is not available"
        }
    
    try:
        mongo_client.admin.command('ping')
        return {
            "status": "healthy",
            "database": "MongoDB",
            "connection": "active"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }



