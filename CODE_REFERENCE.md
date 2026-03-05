# 📖 Code Reference - What Changed

## Quick Summary

You now have a **chat history system** that:

- ✅ Saves every message to MongoDB
- ✅ Loads chat history on page reload
- ✅ Shows database connection status
- ✅ Handles errors gracefully

---

## 🔍 File-by-File Changes

### **1. Frontend Chat UI - `frontend/app.py`**

#### **What Changed:**

Added MongoDB integration to save/load chat messages.

#### **Key New Functions:**

```python
def get_or_create_session_id():
    """Generate unique session ID (UUID) per browser"""
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
    return st.session_state.session_id

def load_chat_history_from_db():
    """Load previous messages from API on startup"""
    if not st.session_state.get("history_loaded", False):
        try:
            response = requests.get(
                f"{CHAT_API_URL}/chat/messages/{session_id}",
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                for msg in data.get("messages", []):
                    st.session_state.messages.append({
                        "role": msg["role"],
                        "content": msg["content"]
                    })
            st.session_state.history_loaded = True
        except:
            st.warning("Could not load chat history")
            st.session_state.history_loaded = True

def save_message_to_db(role: str, content: str):
    """Save message to MongoDB via API"""
    try:
        response = requests.post(
            f"{CHAT_API_URL}/chat/messages",
            json={
                "tenant_id": TENANT_ID,
                "session_id": st.session_state.session_id,
                "role": role,
                "content": content,
            },
            timeout=5
        )
        if response.status_code != 200:
            st.error(f"Failed to save message: {response.text}")
    except requests.exceptions.ConnectionError:
        st.warning("Cannot save message - database may be offline")

def check_db_connection():
    """Display connection status"""
    try:
        response = requests.get(f"{CHAT_API_URL}/health/db", timeout=2)
        if response.status_code == 200:
            st.session_state.db_connected = True
    except:
        st.session_state.db_connected = False
```

#### **How It's Used:**

```python
# In main app logic:
st.set_page_config(...)

CHAT_API_URL = os.getenv("CHAT_API_URL", "http://localhost:8001")
TENANT_ID = "00000000-0000-0000-3029-000000000001"

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "db_connected" not in st.session_state:
    st.session_state.db_connected = False
if "history_loaded" not in st.session_state:
    st.session_state.history_loaded = False

# Get/create session ID
session_id = get_or_create_session_id()

# Load history on first load
load_chat_history_from_db()

# Check DB status
check_db_connection()

# Display status
if st.session_state.db_connected:
    st.success("✅ Database Connected")
else:
    st.warning("⚠️ Database Disconnected - Messages won't persist")

# Chat loop
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# User input
if prompt := st.chat_input("Your message..."):
    st.session_state.messages.append({
        "role": "user",
        "content": prompt
    })

    # Call agent/LLM here
    response = get_agent_response(prompt)

    st.session_state.messages.append({
        "role": "assistant",
        "content": response
    })

    # Save both messages to database
    save_message_to_db("user", prompt)
    save_message_to_db("assistant", response)

    st.rerun()
```

#### **Dependencies Added:**

```python
import requests
import uuid
import os
```

#### **Environment Variables:**

```
CHAT_API_URL=http://localhost:8001
```

---

### **2. Chat History API - `dummy-api/main.py`**

#### **What Changed:**

Complete rewrite from error log API to chat message API.

#### **Key New Classes:**

```python
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List

class ChatMessage(BaseModel):
    """Incoming message from frontend"""
    tenant_id: str
    session_id: str
    role: str  # "user" or "assistant"
    content: str
    metadata: Optional[dict] = None

class ChatMessageResponse(BaseModel):
    """Outgoing message from database"""
    _id: str
    timestamp: str
    tenant_id: str
    session_id: str
    role: str
    content: str
    metadata: dict
```

#### **Key New Endpoints:**

```python
@app.post("/chat/messages")
def save_chat_message(message: ChatMessage) -> dict:
    """Save message to database"""
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    doc = {
        "tenant_id": message.tenant_id,
        "session_id": message.session_id,
        "role": message.role,
        "content": message.content,
        "timestamp": datetime.utcnow(),
        "metadata": message.metadata or {}
    }

    result = db.chat_history.insert_one(doc)

    return {
        "success": True,
        "message": {
            "_id": str(result.inserted_id),
            "timestamp": doc["timestamp"].isoformat(),
            **doc
        }
    }

@app.get("/chat/messages/{session_id}")
def get_chat_messages(session_id: str, limit: int = 100) -> dict:
    """Retrieve all messages in a session"""
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    messages = list(
        db.chat_history
        .find({"session_id": session_id})
        .sort("timestamp", 1)
        .limit(limit)
    )

    return {
        "success": True,
        "session_id": session_id,
        "message_count": len(messages),
        "messages": [
            {
                "_id": str(msg["_id"]),
                "timestamp": msg["timestamp"].isoformat(),
                "role": msg["role"],
                "content": msg["content"],
                **{k: v for k, v in msg.items()
                   if k not in ["_id", "timestamp", "role", "content"]}
            }
            for msg in messages
        ]
    }

@app.delete("/chat/messages/{session_id}")
def delete_session(session_id: str) -> dict:
    """Clear all messages in a session"""
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    result = db.chat_history.delete_many({"session_id": session_id})

    return {
        "success": True,
        "messages_deleted": result.deleted_count
    }

@app.get("/chat/sessions/{tenant_id}")
def get_tenant_sessions(tenant_id: str) -> dict:
    """Get all sessions for a tenant with message counts"""
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    sessions = list(
        db.chat_history.aggregate([
            {"$match": {"tenant_id": tenant_id}},
            {
                "$group": {
                    "_id": "$session_id",
                    "message_count": {"$sum": 1},
                    "last_message": {"$max": "$timestamp"}
                }
            }
        ])
    )

    return {
        "success": True,
        "tenant_id": tenant_id,
        "session_count": len(sessions),
        "sessions": [
            {
                "_id": s["_id"],
                "message_count": s["message_count"],
                "last_message": s["last_message"].isoformat() if s["last_message"] else None
            }
            for s in sessions
        ]
    }
```

#### **Health Checks:**

```python
@app.get("/health")
def health_check() -> dict:
    """Service health"""
    return {
        "status": "healthy",
        "service": "netai-copilot-chat-api"
    }

@app.get("/health/db")
def db_health_check() -> dict:
    """Database health"""
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    try:
        db.client.admin.command("ping")
        return {
            "status": "healthy",
            "database": "mongodb"
        }
    except:
        raise HTTPException(status_code=503, detail="Database unavailable")
```

#### **MongoDB Connection:**

```python
from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError

# Connection setup
MONGODB_URL = os.getenv(
    "MONGODB_URL",
    "mongodb://admin:password123@localhost:27017/netai_copilot?authSource=admin"
)

mongo_client = None
db = None

@app.on_event("startup")
def startup_db_client():
    global db
    try:
        mongo_client = MongoClient(MONGODB_URL, serverSelectionTimeoutMS=5000)
        db = mongo_client.netai_copilot
        mongo_client.admin.command("ping")
        print("✅ Connected to MongoDB")
    except ServerSelectionTimeoutError:
        print("❌ Failed to connect to MongoDB")
        db = None

@app.on_event("shutdown")
def shutdown_db_client():
    if mongo_client is not None:
        mongo_client.close()
```

#### **Important: PyMongo Boolean Check**

```python
# ❌ WRONG - This will fail!
if not db:
    raise HTTPException(status_code=503)

# ✅ CORRECT - Check for None explicitly
if db is None:
    raise HTTPException(status_code=503)
```

---

### **3. MongoDB Initialization - `scripts/init-mongo.js`**

#### **What Changed:**

Switched from error_logs collection to chat_history collection.

#### **Full Script:**

```javascript
db = db.getSiblingDB("netai_copilot");

// Drop existing collection if present
db.chat_history.drop();

// Create collection with validation
db.createCollection("chat_history", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["tenant_id", "role", "content"],
      properties: {
        _id: { bsonType: "objectId" },
        timestamp: { bsonType: "date" },
        tenant_id: { bsonType: "string" },
        session_id: { bsonType: "string" },
        role: {
          bsonType: "string",
          enum: ["user", "assistant"],
        },
        content: { bsonType: "string" },
        metadata: { bsonType: "object" },
      },
    },
  },
});

// Create indexes for fast queries
db.chat_history.createIndex({ tenant_id: 1, session_id: 1, timestamp: -1 });

db.chat_history.createIndex({ session_id: 1 });

db.chat_history.createIndex({ timestamp: -1 });

print("✅ chat_history collection created with indexes");
```

#### **What It Does:**

1. Creates `chat_history` collection
2. Adds JSON schema validation
3. Creates 3 performance indexes
4. Ensures required fields present

#### **Run Command:**

```powershell
docker exec netai-mongodb mongosh -u admin -p password123 < scripts/init-mongo.js
```

---

### **4. Requirements Files**

#### **`frontend/requirements.txt`**

**Added:**

```
requests==2.31.0  # For API calls
```

**Why:** Need to make HTTP POST/GET requests to chat API.

---

#### **`dummy-api/requirements.txt`**

**No changes needed, but verify you have:**

```
fastapi==0.115.0
uvicorn[standard]==0.30.0
pymongo==4.6.0
requests==2.31.0
```

**Removed (if present):**

- ❌ `motor==3.3.2` (async driver, not needed)

---

### **5. Docker Configuration - `docker-compose.yml`**

#### **What Changed:**

Added `CHAT_API_URL` environment variable to frontend.

#### **Frontend Service Update:**

```yaml
frontend:
  build:
    context: .
    dockerfile: Dockerfile.frontend
  ports:
    - "8501:8501"
  environment:
    - CHAT_API_URL=http://dummy-api:8001 # NEW
    - GROQ_API_KEY=${GROQ_API_KEY}
  volumes:
    - ./knowledge_base/faiss_index:/app/knowledge_base/faiss_index:ro
  depends_on:
    - dummy-api
```

#### **Why:** Frontend needs to know where to find the chat API.

---

## 🔗 Data Flow Diagram

### **Saving a Message**

```
Frontend (app.py)
    ↓
save_message_to_db("user", "Hello!")
    ↓
requests.post(
    "http://localhost:8001/chat/messages",
    json={
        "tenant_id": "00000000-0000-0000-3029-000000000001",
        "session_id": "uuid-here",
        "role": "user",
        "content": "Hello!",
        "metadata": {}
    }
)
    ↓
API (main.py)
    ↓
@app.post("/chat/messages")
def save_chat_message(message: ChatMessage)
    ↓
Validate with Pydantic
    ↓
db.chat_history.insert_one({
    "timestamp": datetime.utcnow(),
    "tenant_id": "...",
    "session_id": "...",
    "role": "user",
    "content": "Hello!",
    "metadata": {}
})
    ↓
MongoDB
    ↓
INSERT into chat_history collection
    ↓
Return inserted_id to API
    ↓
API returns success response
    ↓
Frontend receives response
    ↓
Display in chat UI
```

### **Loading Chat History**

```
Frontend (app.py)
    ↓
load_chat_history_from_db()
    ↓
requests.get(
    "http://localhost:8001/chat/messages/uuid-here"
)
    ↓
API (main.py)
    ↓
@app.get("/chat/messages/{session_id}")
def get_chat_messages(session_id: str)
    ↓
db.chat_history.find({"session_id": session_id})
              .sort("timestamp", 1)
              .limit(100)
    ↓
MongoDB
    ↓
FIND documents matching session_id
    ↓
Sort by timestamp ascending
    ↓
Return list to API
    ↓
API formats response
    ↓
Frontend receives messages list
    ↓
For each message:
    st.session_state.messages.append(message)
    ↓
Display in chat UI
```

---

## 💡 Common Tasks

### **Add a New Message Type**

```python
# In dummy-api/main.py, update ChatMessage:

class ChatMessage(BaseModel):
    tenant_id: str
    session_id: str
    role: str  # "user", "assistant", "system"
    content: str
    message_type: str = "text"  # NEW: "text", "command", etc.
    metadata: Optional[dict] = None
```

### **Query Messages with Role**

```python
# In dummy-api/main.py, add new endpoint:

@app.get("/chat/messages/{session_id}/role/{role}")
def get_messages_by_role(session_id: str, role: str):
    messages = db.chat_history.find({
        "session_id": session_id,
        "role": role
    }).sort("timestamp", 1)
    # ...return
```

### **Export Chat to File**

```python
# In dummy-api/main.py, add new endpoint:

@app.get("/chat/export/{session_id}")
def export_session(session_id: str):
    messages = db.chat_history.find({
        "session_id": session_id
    }).sort("timestamp", 1)

    # Format as text or JSON
    text = "\n".join([
        f"{msg['role']}: {msg['content']}"
        for msg in messages
    ])

    return {
        "content": text,
        "filename": f"chat_{session_id}.txt"
    }
```

---

## 🧪 Test Individual Functions

### **Test Frontend Save Function**

```python
# In Python REPL:
import requests
response = requests.post(
    "http://localhost:8001/chat/messages",
    json={
        "tenant_id": "00000000-0000-0000-3029-000000000001",
        "session_id": "test",
        "role": "user",
        "content": "Hello",
        "metadata": {}
    }
)
print(response.json())
```

### **Test Frontend Load Function**

```python
# In Python REPL:
import requests
response = requests.get(
    "http://localhost:8001/chat/messages/test"
)
print(response.json())
```

### **Test MongoDB Directly**

```javascript
// In MongoDB shell:
db.chat_history.find().pretty();
db.chat_history.countDocuments();
db.chat_history.find({ role: "user" }).pretty();
```

---

## 📊 Database Schema Quick Reference

```
Collection: chat_history

Document Structure:
{
  _id: ObjectId,              // Unique ID
  timestamp: Date,            // UTC timestamp
  tenant_id: String,          // Required
  session_id: String,         // Required
  role: String,               // Required: "user" | "assistant"
  content: String,            // Required: message text
  metadata: Object            // Optional: extra fields
}

Indexes:
1. {tenant_id: 1, session_id: 1, timestamp: -1}
2. {session_id: 1}
3. {timestamp: -1}
```

---

## ✅ Validation Checklist

Before deploying, verify:

- [ ] MongoDB running: `docker ps | findstr mongo`
- [ ] API started: `curl http://localhost:8001/health`
- [ ] API connected to DB: `curl http://localhost:8001/health/db`
- [ ] Can save message: `curl -X POST ... /chat/messages`
- [ ] Can retrieve messages: `curl ... /chat/messages/{session_id}`
- [ ] Frontend loads: `http://localhost:8501`
- [ ] Messages persist on reload

---

**That's it! You now have a complete chat history system! 🎉**
