# 🏗️ NetAI Copilot System Architecture

## Overview

Your NetAI Copilot is a multi-service system with Streamlit frontend, FastAPI backend, MongoDB database, and LangGraph agents.

---

## 📊 System Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     BROWSER / CLIENT                            │
│                  (http://localhost:8501)                        │
└────────────────────────┬────────────────────────────────────────┘
                         │ HTTP (requests library)
                         │
        ┌────────────────▼─────────────────┐
        │   STREAMLIT FRONTEND             │
        │   (python -m streamlit run ...)  │
        │                                  │
        │  • Chat UI                       │
        │  • Session Management            │
        │  • Auto-load chat history        │
        │  • Save messages to API          │
        │  • RAG Integration (FAISS)       │
        │                                  │
        │  Port: 8501                      │
        └────────────────┬─────────────────┘
                         │ HTTP / JSON
                         │ POST /chat/messages
                         │ GET /chat/messages/{session_id}
                         │
        ┌────────────────▼──────────────────────┐
        │   FASTAPI CHAT HISTORY SERVICE       │
        │   (uvicorn main:app --port 8001)     │
        │                                       │
        │  • Save chat messages                │
        │  • Retrieve chat history             │
        │  • Session aggregation               │
        │  • Health checks                     │
        │  • MongoDB Connection Pool           │
        │                                       │
        │  Port: 8001                          │
        └────────────────┬──────────────────────┘
                         │ MongoDB Protocol
                         │ (TCP Port 27017)
                         │
        ┌────────────────▼──────────────────────┐
        │   MONGODB DATABASE                   │
        │   (docker container:27017)          │
        │                                       │
        │  Database: netai_copilot            │
        │  Collection: chat_history           │
        │                                       │
        │  • Stores all chat messages         │
        │  • Indexed for fast queries         │
        │  • Multi-tenant support            │
        │  • Session isolation               │
        │                                       │
        │  Storage Volume: mongodb_data      │
        └─────────────────────────────────────────┘
```

---

## 🔄 Chat Message Flow

### **Sending a Message:**

```
User types in Streamlit
        ↓
┌──────────────────────────────────────────────────┐
│ Frontend (app.py):                               │
│ 1. Get message text from input                   │
│ 2. Create JSON with tenant_id, session_id, role │
│ 3. POST to /chat/messages                         │
└──────────────────────┬───────────────────────────┘
                       ↓
┌──────────────────────────────────────────────────┐
│ API (main.py):                                   │
│ 1. Receive JSON request                          │
│ 2. Validate with Pydantic ChatMessage model     │
│ 3. Add timestamp (current UTC)                   │
│ 4. Insert into MongoDB chat_history collection  │
│ 5. Return success + message ID                   │
└──────────────────────┬───────────────────────────┘
                       ↓
┌──────────────────────────────────────────────────┐
│ MongoDB:                                         │
│ 1. Receive insert request                        │
│ 2. Create document with generated _id            │
│ 3. Store in chat_history collection              │
│ 4. Update indexes automatically                  │
└──────────────────────┬───────────────────────────┘
                       ↓
┌──────────────────────────────────────────────────┐
│ Frontend (app.py):                               │
│ 1. Receive success response                      │
│ 2. Display message in UI                         │
│ 3. Clear input box                               │
│ 4. Update session_state["messages"]              │
└──────────────────────────────────────────────────┘
```

---

### **Loading Chat History:**

```
Frontend loads (streamlit run app.py)
        ↓
┌──────────────────────────────────────────────────┐
│ Frontend (app.py):                               │
│ 1. Check if chat_history loaded already          │
│ 2. If not, load_chat_history_from_db()          │
│ 3. GET /chat/messages/{session_id}               │
└──────────────────────┬───────────────────────────┘
                       ↓
┌──────────────────────────────────────────────────┐
│ API (main.py):                                   │
│ 1. Receive GET request with session_id           │
│ 2. Query MongoDB: find all docs where            │
│    session_id = request param                    │
│ 3. Sort by timestamp (ascending)                 │
│ 4. Return messages array                         │
└──────────────────────┬───────────────────────────┘
                       ↓
┌──────────────────────────────────────────────────┐
│ MongoDB:                                         │
│ 1. Receive find query                            │
│ 2. Use index: {session_id: 1}                    │
│ 3. Fast lookup of all matching documents         │
│ 4. Return sorted by timestamp                    │
└──────────────────────┬───────────────────────────┘
                       ↓
┌──────────────────────────────────────────────────┐
│ Frontend (app.py):                               │
│ 1. Receive messages array                        │
│ 2. Store in session_state["messages"]            │
│ 3. Display in chat box                           │
│ 4. Mark history_loaded = True                    │
└──────────────────────────────────────────────────┘
```

---

## 📦 Key Components

### **1. Frontend (Streamlit)**

**File:** `frontend/app.py`

**Responsibilities:**

- Display chat UI
- Manage user sessions (UUID)
- Load chat history on startup
- Save messages after each exchange
- Show database connection status

**Key Functions:**

```python
get_or_create_session_id()      # UUID session tracking
load_chat_history_from_db()     # GET /chat/messages
save_message_to_db()            # POST /chat/messages
check_db_connection()           # Health check
```

**Dependencies:**

- `streamlit` - UI framework
- `requests` - HTTP calls to API
- `uuid` - Session ID generation

---

### **2. Chat History API (FastAPI)**

**File:** `dummy-api/main.py`

**Port:** 8001

**Responsibilities:**

- Accept chat messages via REST
- Store messages in MongoDB
- Retrieve chat history
- Manage sessions and tenants
- Health checks

**Key Endpoints:**

```
POST   /chat/messages              Save message
GET    /chat/messages/{session_id} Get all messages in session
DELETE /chat/messages/{session_id} Clear session
GET    /chat/sessions/{tenant_id}  Get all sessions for tenant
GET    /health                     Service health
GET    /health/db                  Database health
```

**Key Classes:**

```python
ChatMessage          # Pydantic model for validation
FastAPI app          # Web framework
MongoClient          # Database connection
```

**Dependencies:**

- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `pymongo` - MongoDB driver
- `requests` - HTTP calls (if needed)

---

### **3. MongoDB Database**

**Service:** Containerized MongoDB

**Port:** 27017

**Database:** `netai_copilot`

**Collection:** `chat_history`

**Schema (JSON Schema Validation):**

```javascript
{
  _id: ObjectId,               // Auto-generated
  timestamp: Date,             // ISO 8601 UTC
  tenant_id: String,           // Customer ID
  session_id: String,          // Conversation ID
  role: String,                // "user" | "assistant"
  content: String,             // Message text
  metadata: Object             // Extra data
}
```

**Indexes:**

```javascript
// Primary index for session queries
{tenant_id: 1, session_id: 1, timestamp: -1}

// Fast session lookup
{session_id: 1}

// Chronological ordering
{timestamp: -1}
```

---

## 🔐 Data Model

### **Chat Message**

```python
class ChatMessage(BaseModel):
    tenant_id: str        # Example: "00000000-0000-0000-3029-000000000001"
    session_id: str       # Example: "a1b2c3d4-e5f6-g7h8-i9j0-k1l2m3n4o5p6"
    role: str             # "user" or "assistant"
    content: str          # The actual message
    metadata: dict = {}   # Optional extra fields
```

### **Saved Document (in MongoDB)**

```json
{
  "_id": { "$oid": "65f8a2c1d5e3f9b2c0d1e2f3" },
  "timestamp": { "$date": "2026-03-04T10:15:00.000Z" },
  "tenant_id": "00000000-0000-0000-3029-000000000001",
  "session_id": "a1b2c3d4-e5f6-g7h8-i9j0-k1l2m3n4o5p6",
  "role": "user",
  "content": "Hello, how are you?",
  "metadata": {}
}
```

---

## 🚀 Startup Sequence

```
1. Start MongoDB
   ├─ docker run mongo:latest
   ├─ Exposes port 27017
   └─ Initializes with credentials

2. Start Chat API (waits for MongoDB)
   ├─ cd dummy-api
   ├─ pip install -r requirements.txt
   ├─ python -m uvicorn main:app --port 8001
   ├─ Connects to MongoDB on startup
   ├─ Logs: "✅ Connected to MongoDB"
   └─ Listens for requests

3. Start Frontend (anytime, but needs API)
   ├─ cd frontend
   ├─ pip install -r requirements.txt
   ├─ python -m streamlit run app.py
   ├─ Opens browser to http://localhost:8501
   ├─ Checks API health on load
   └─ Loads previous chat history
```

---

## 🔌 Connections

### **Frontend → API**

- **Protocol:** HTTP
- **Format:** JSON
- **Authentication:** None (local dev)
- **Timeout:** Default requests timeout (30s)
- **Error Handling:** Graceful fallback if API down

Example:

```python
response = requests.post(
    f"{CHAT_API_URL}/chat/messages",
    json={...},
    timeout=5
)
```

---

### **API → MongoDB**

- **Protocol:** MongoDB Wire Protocol (TCP)
- **Port:** 27017
- **Connection String:**
  ```
  mongodb://admin:password123@localhost:27017/netai_copilot?authSource=admin
  ```
- **Pooling:** Automatic via PyMongo
- **Error Handling:** Returns 500 if database unavailable

Example:

```python
mongo_client = MongoClient(mongodb_url)
db = mongo_client.netai_copilot
collection = db.chat_history
```

---

## 📊 Query Patterns

### **Pattern 1: Save Message**

```javascript
db.chat_history.insertOne({
  timestamp: new Date(),
  tenant_id: "...",
  session_id: "...",
  role: "user",
  content: "...",
  metadata: {},
});
```

### **Pattern 2: Get Session History**

```javascript
db.chat_history
  .find({
    session_id: "...",
  })
  .sort({
    timestamp: 1,
  })
  .toArray();
```

### **Pattern 3: Get All Sessions for Tenant**

```javascript
db.chat_history.aggregate([
  {
    $match: { tenant_id: "..." },
  },
  {
    $group: {
      _id: "$session_id",
      message_count: { $sum: 1 },
      last_message: { $max: "$timestamp" },
    },
  },
]);
```

### **Pattern 4: Delete Session**

```javascript
db.chat_history.deleteMany({
  session_id: "...",
});
```

---

## 🔄 State Management

### **Frontend (Streamlit)**

```python
st.session_state = {
    "messages": [],           # Chat history in UI
    "session_id": "uuid",     # Current session
    "db_connected": True,     # DB status
    "history_loaded": False   # Prevent duplicate loads
}
```

**Lifecycle:**

1. First load: `history_loaded = False`
2. Load history from API
3. Set `history_loaded = True`
4. Prevent re-loading on every rerender
5. Clear on logout/new session

---

### **Session ID Management**

```python
# Generate on first load (never changes per browser)
session_id = st.session_state.get(
    "session_id",
    str(uuid.uuid4())
)
st.session_state.session_id = session_id

# Used in every API call
{
    "session_id": session_id,
    ...
}
```

**Result:**

- Same user = Same session ID across reloads
- Different browser/device = Different session ID
- All messages linked to session ID in MongoDB

---

## 🎯 Tenant Isolation

```
Tenant: 00000000-0000-0000-3029-000000000001
├─ Session: uuid-1
│  ├─ Message: "Hello?"
│  ├─ Message: "Hi there!"
│  └─ Message: "How can I help?"
│
└─ Session: uuid-2
   ├─ Message: "What's the weather?"
   └─ Message: "It's sunny!"

MongoDB indexes ensure fast lookup:
- All messages for tenant: O(log n) via {tenant_id: 1, ...}
- All sessions for tenant: O(k) where k = number of sessions
- All messages in session: O(log n) via {session_id: 1}
```

---

## 📈 Scalability

### **Current (Single Instance)**

```
1 Frontend ─┐
            ├─→ 1 API ─→ 1 MongoDB
1 Browser ─┘
```

### **Future (Horizontal)**

```
N Frontends ─┐              N API Instances
             ├──────────────┬──────────────→ 1 MongoDB (or Replica Set)
N Browsers ──┘              │
                    Load Balancer
                            │
                        Sessions persisted
                        in MongoDB, not memory
```

**Key:** Session data in MongoDB means:

- Any API instance can retrieve history
- No session affinity needed
- Stateless API instances
- Easy horizontal scaling

---

## 🐛 Error Handling

### **Frontend**

```python
try:
    response = requests.post(f"{CHAT_API_URL}/chat/messages", ...)
except requests.exceptions.ConnectionError:
    st.warning("Database unavailable, messages won't persist")
    # Continue anyway - show message in UI but don't save
```

### **API**

```python
@app.on_event("startup")
async def startup():
    global db
    try:
        db = mongo_client.netai_copilot
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        db = None

@app.post("/chat/messages")
async def save_chat_message(message: ChatMessage):
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    # ... continue with insert
```

---

## 📝 Environment Configuration

### **Development (Local)**

```
CHAT_API_URL=http://localhost:8001
MONGODB_URL=mongodb://admin:password123@localhost:27017/netai_copilot?authSource=admin
GROQ_API_KEY=your-key-here
```

### **Docker Compose**

```
CHAT_API_URL=http://dummy-api:8001
MONGODB_URL=mongodb://admin:password123@mongodb:27017/netai_copilot?authSource=admin
```

---

## ✅ Health Checks

### **Frontend**

```python
def check_db_connection():
    try:
        response = requests.get(f"{CHAT_API_URL}/health/db", timeout=2)
        return response.status_code == 200
    except:
        return False
```

### **API**

```python
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "netai-copilot-chat-api"}

@app.get("/health/db")
async def db_health_check():
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    return {"status": "healthy", "database": "mongodb"}
```

---

## 🎓 Architecture Decisions

| Decision                     | Rationale                                                              |
| ---------------------------- | ---------------------------------------------------------------------- |
| **FastAPI for chat API**     | Lightweight, async, automatic validation with Pydantic                 |
| **PyMongo (sync)**           | Simpler than Motor, fine for I/O-bound chat app                        |
| **MongoDB for chat history** | Document-oriented fits chat messages, easy scaling                     |
| **Streamlit frontend**       | Fast development, great for data apps, session_state perfect for state |
| **Session ID via UUID**      | Unique per browser, stateless, good for distributed systems            |
| **Graceful fallback**        | App works without database (just won't persist)                        |
| **Tenant ID in schema**      | Future multi-tenant support baked in                                   |
| **Indexes on MongoDB**       | Sub-millisecond queries even with millions of messages                 |

---

## 📚 File Structure

```
netai_copilot/
├── dummy-api/
│   ├── main.py                 ← Chat history API
│   └── requirements.txt         ← API dependencies
│
├── frontend/
│   ├── app.py                  ← Streamlit chat UI
│   └── requirements.txt         ← Frontend dependencies
│
├── knowledge_base/
│   └── faiss_index/
│       ├── index.faiss         ← Vector embeddings
│       └── metadata.json        ← Index metadata
│
├── docker-compose.yml          ← Orchestration
├── CHAT_HISTORY_SETUP.md       ← This system overview
├── TESTING_GUIDE.md            ← Step-by-step testing
└── SYSTEM_ARCHITECTURE.md      ← This document
```

---

## 🚀 Next Steps

1. **Install Dependencies**

   ```powershell
   cd dummy-api && pip install -r requirements.txt
   cd ../frontend && pip install -r requirements.txt
   ```

2. **Start Services** (follow TESTING_GUIDE.md)
3. **Test Full Flow** (messages → API → MongoDB → persistency)

4. **Scale Up** (integrate with agent orchestration later)

---

**Your NetAI Copilot is now architected for production-grade chat history! 🎉**
