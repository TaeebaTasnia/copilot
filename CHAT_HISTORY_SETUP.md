# 💬 Chat History System - Setup Complete!

## What Changed

Instead of storing error logs, your system now stores **chat messages** in MongoDB. Every conversation is automatically saved!

---

## 🏗️ Architecture

```
Frontend (Streamlit)
    ↓ (saves every message)
Chat History API (port 8001)
    ↓ (stores/retrieves)
MongoDB (port 27017)
```

### **Data Flow:**

1. **User types a message** in Frontend
2. **Frontend sends POST** to `http://localhost:8001/chat/messages`
3. **API saves to MongoDB** with:
   - `tenant_id` (identifies customer)
   - `session_id` (unique per user/session)
   - `role` ("user" or "assistant")
   - `content` (the message text)
   - `timestamp` (when saved)

4. **On page reload**, Frontend sends GET to `http://localhost:8001/chat/messages/{session_id}`
5. **API retrieves all messages** from MongoDB
6. **Frontend displays history** from disk

---

## 📊 MongoDB Collection

### **Collection:** `chat_history`

```javascript
{
  _id: ObjectId("65f8a2c1d5e3f9b2c0d1e2f3"),
  timestamp: ISODate("2026-03-04T10:15:00Z"),
  tenant_id: "00000000-0000-0000-3029-000000000001",
  session_id: "a1b2c3d4-e5f6-g7h8-i9j0-k1l2m3n4o5p6",
  role: "user",
  content: "What is the Maveric platform?",
  metadata: {
    timestamp_saved: "2026-03-04T10:15:00Z"
  }
}
```

### **Indexes (for fast queries):**

- `tenant_id + session_id + timestamp` - Find messages for a session
- `session_id` - Get all messages in a session
- `timestamp` - Sort chronologically

---

## 🚀 API Endpoints

### **1. Save a Message (POST)**

```
POST /chat/messages
Content-Type: application/json

{
  "tenant_id": "00000000-0000-0000-3029-000000000001",
  "session_id": "session-uuid-here",
  "role": "user",
  "content": "Your message here",
  "metadata": {}
}

Response:
{
  "success": true,
  "message": {
    "_id": "mongodb-id",
    "timestamp": "2026-03-04T10:15:00Z",
    ...
  }
}
```

### **2. Get Chat History (GET)**

```
GET /chat/messages/{session_id}?limit=100

Response:
{
  "success": true,
  "session_id": "session-uuid",
  "message_count": 5,
  "messages": [
    {
      "_id": "...",
      "timestamp": "2026-03-04T10:15:00Z",
      "role": "user",
      "content": "..."
    },
    ...
  ]
}
```

### **3. Delete Session (DELETE)**

```
DELETE /chat/messages/{session_id}

Response:
{
  "success": true,
  "messages_deleted": 5
}
```

### **4. Get All Sessions for Tenant (GET)**

```
GET /chat/sessions/{tenant_id}

Response:
{
  "success": true,
  "tenant_id": "...",
  "session_count": 3,
  "sessions": [
    {
      "_id": "session-uuid-1",
      "message_count": 10,
      "last_message": "2026-03-04T10:15:00Z"
    },
    ...
  ]
}
```

---

## 🧪 Test Your Setup

### **Step 1: Start MongoDB**

```powershell
docker run -d `
  --name netai-mongodb `
  -p 27017:27017 `
  -e MONGO_INITDB_ROOT_USERNAME=admin `
  -e MONGO_INITDB_ROOT_PASSWORD=password123 `
  mongo:latest

Start-Sleep -Seconds 5
```

### **Step 2: Start API**

```powershell
cd dummy-api
pip install -r requirements.txt
python -m uvicorn main:app --port 8001
```

### **Step 3: Test API**

```powershell
# Check MongoDB connection
curl http://localhost:8001/health/db

# Save a message
$body = @{
    tenant_id = "00000000-0000-0000-3029-000000000001"
    session_id = "test-session-123"
    role = "user"
    content = "Hello, how are you?"
} | ConvertTo-Json

curl -X POST `
  -H "Content-Type: application/json" `
  -d $body `
  http://localhost:8001/chat/messages

# Retrieve messages
curl http://localhost:8001/chat/messages/test-session-123
```

### **Step 4: Start Frontend**

```powershell
python -m streamlit run frontend/app.py
```

---

## 📱 Frontend Features

1. **Auto-saves messages** - Every message saved to MongoDB
2. **Loads history** - Previous messages shown on reload
3. **Session ID** - Unique per browser (UUID)
4. **DB status indicator** - Shows if MongoDB is connected
5. **Graceful fallback** - Works even if MongoDB is down (messages won't persist, but won't crash)

---

## 🔍 View Data in MongoDB

### **Using Docker Shell:**

```powershell
docker exec -it netai-mongodb mongosh -u admin -p password123 netai_copilot

# Inside MongoDB:
db.chat_history.find().pretty()          # View all messages
db.chat_history.find({role: "user"}).pretty()  # Only user messages
db.chat_history.countDocuments()         # Total messages
db.chat_history.find({session_id: "your-session-id"}).pretty()  # Single session
exit
```

### **Using MongoDB Compass:**

1. Download: https://www.mongodb.com/products/tools/compass
2. Connect: `mongodb://admin:password123@localhost:27017/?authSource=admin`
3. Navigate: `netai_copilot` → `chat_history`
4. View/edit messages visually

---

## 🎯 What's Stored

| Field        | Purpose                            |
| ------------ | ---------------------------------- |
| `_id`        | Auto-generated MongoDB ID          |
| `timestamp`  | When message was saved             |
| `tenant_id`  | Which customer/organization        |
| `session_id` | Which conversation session         |
| `role`       | Who said it: "user" or "assistant" |
| `content`    | The actual message text            |
| `metadata`   | Extra info (timestamps, etc.)      |

---

## ✅ Complete Setup Steps

1. **Delete old MongoDB container** (if running)

   ```powershell
   docker stop netai-mongodb
   docker rm netai-mongodb
   ```

2. **Start fresh MongoDB**

   ```powershell
   docker run -d --name netai-mongodb -p 27017:27017 -e MONGO_INITDB_ROOT_USERNAME=admin -e MONGO_INITDB_ROOT_PASSWORD=password123 mongo:latest
   ```

3. **Start API (Terminal 2)**

   ```powershell
   cd dummy-api
   pip install requests
   python -m uvicorn main:app --port 8001
   ```

4. **Start Frontend (Terminal 3)**

   ```powershell
   cd frontend
   pip install requests
   python -m streamlit run app.py
   ```

5. **Use it!**
   - Open http://localhost:8501
   - Type messages
   - All saved automatically to MongoDB
   - Reload page → messages persist!

---

## 🐛 Troubleshooting

| Issue                        | Solution                                                                    |
| ---------------------------- | --------------------------------------------------------------------------- |
| **Messages not saving**      | Check if API is running: `curl http://localhost:8001/health/db`             |
| **Can't connect to MongoDB** | Verify container running: `docker ps`                                       |
| **Chat history not loading** | Make sure CHAT_API_URL is correct in frontend                               |
| **Port 8001 already in use** | Kill process: `netstat -ano \| findstr :8001` then `taskkill /PID <pid> /F` |

---

## 📝 Environment Variables

Set these in `.env` for local development:

```
CHAT_API_URL=http://localhost:8001
MONGODB_URL=mongodb://admin:password123@localhost:27017/netai_copilot?authSource=admin
GROQ_API_KEY=your_key_here
```

---

## 🎉 You're All Set!

Your NetAI Copilot now has:

- ✅ Full chat history in MongoDB
- ✅ Auto-save on every message
- ✅ Persistent conversations across page reloads
- ✅ Multi-tenant support (via `tenant_id`)
- ✅ Session tracking (via `session_id`)
- ✅ Queryable message history

**Ready to chat!** 🚀
