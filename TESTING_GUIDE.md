# ✅ Quick Start Testing Guide

## 1️⃣ Start MongoDB

```powershell
# Stop any existing container
docker stop netai-mongodb 2>$null
docker rm netai-mongodb 2>$null

# Start fresh MongoDB
docker run -d `
  --name netai-mongodb `
  -p 27017:27017 `
  -e MONGO_INITDB_ROOT_USERNAME=admin `
  -e MONGO_INITDB_ROOT_PASSWORD=password123 `
  mongo:latest

# Wait for startup
Start-Sleep -Seconds 5

# Verify running
docker ps | findstr netai-mongodb
```

✅ **Success criteria:** Container listed as running

---

## 2️⃣ Start Chat History API

```powershell
# Terminal 2 - Navigate to api
cd dummy-api

# Install dependencies
pip install -r requirements.txt

# Start API
python -m uvicorn main:app --port 8001

# Expected output:
# INFO:     Started server process [XXXX]
# INFO:     Waiting for application startup.
# ✅ Connected to MongoDB
# INFO:     Application startup complete [uvicorn]
# INFO:     Uvicorn running on http://0.0.0.0:8001
```

✅ **Success criteria:** See "✅ Connected to MongoDB"

---

## 3️⃣ Test API Health

```powershell
# Terminal 3 - Test health endpoints
curl http://localhost:8001/health
curl http://localhost:8001/health/db
```

Expected response:

```json
{"status": "healthy", "service": "netai-copilot-chat-api"}
{"status": "healthy", "database": "mongodb"}
```

✅ **Success criteria:** Both return `"status": "healthy"`

---

## 4️⃣ Test Chat Message Endpoints

### **Test 1: Save a message**

```powershell
$body = @{
    tenant_id = "00000000-0000-0000-3029-000000000001"
    session_id = "test-session-001"
    role = "user"
    content = "Hello, how are you?"
} | ConvertTo-Json

curl -X POST `
  -H "Content-Type: application/json" `
  -d $body `
  http://localhost:8001/chat/messages
```

Expected response:

```json
{
  "success": true,
  "message": {
    "_id": "...",
    "timestamp": "2026-03-04T...",
    "tenant_id": "00000000-0000-0000-3029-000000000001",
    "session_id": "test-session-001",
    "role": "user",
    "content": "Hello, how are you?",
    "metadata": {}
  }
}
```

✅ **Success criteria:** `"success": true` and message ID returned

---

### **Test 2: Retrieve messages**

```powershell
curl http://localhost:8001/chat/messages/test-session-001
```

Expected response:

```json
{
  "success": true,
  "session_id": "test-session-001",
  "message_count": 1,
  "messages": [
    {
      "_id": "...",
      "timestamp": "...",
      "role": "user",
      "content": "Hello, how are you?"
    }
  ]
}
```

✅ **Success criteria:** Your message appears in the list

---

### **Test 3: Save another message**

```powershell
$body = @{
    tenant_id = "00000000-0000-0000-3029-000000000001"
    session_id = "test-session-001"
    role = "assistant"
    content = "I'm doing great! How can I help?"
} | ConvertTo-Json

curl -X POST `
  -H "Content-Type: application/json" `
  -d $body `
  http://localhost:8001/chat/messages
```

---

### **Test 4: Retrieve both messages**

```powershell
curl http://localhost:8001/chat/messages/test-session-001
```

✅ **Success criteria:** Should now show `"message_count": 2` with both messages

---

## 5️⃣ Start Frontend

```powershell
# Terminal 4 - Navigate to frontend
cd frontend

# Install dependencies (if needed)
pip install -r requirements.txt

# Start Streamlit
python -m streamlit run app.py

# Expected output:
# You can now view your Streamlit app in your browser.
# URL: http://localhost:8501
```

✅ **Success criteria:** Streamlit page opens at http://localhost:8501

---

## 6️⃣ Test Frontend

### **In Streamlit:**

1. **Check database status**
   - Look for indicator: Either ✅ **Connected** or ⚠️ **Database disconnected**

2. **Load existing chat history**
   - Should show previous messages from `test-session-001`
   - Should display:
     - ℹ️ User: "Hello, how are you?"
     - 🤖 Assistant: "I'm doing great! How can I help?"

3. **Send a new message**
   - Type in chat box: "This is a new message"
   - Press Enter
   - Message should:
     - Appear immediately in chat
     - Save to database
     - Persist on page reload

4. **Reload page**
   - Press F5 or Cmd+R
   - Should see:
     - All 3 previous messages
     - Session ID unchanged
     - Database indicator: ✅ **Connected**

✅ **Success criteria:**

- Messages persist across page reloads
- New messages auto-save
- DB status shows connected

---

## 🔍 Verify Data in MongoDB

```powershell
# View all messages using MongoDB shell
docker exec -it netai-mongodb mongosh -u admin -p password123 netai_copilot

# Inside MongoDB:
db.chat_history.find().pretty()

# Exit
exit
```

You should see all 3 messages with:

- Timestamps
- Your tenant_id
- Your session_id
- role + content

---

## 📊 Test Session Aggregation

```powershell
curl http://localhost:8001/chat/sessions/00000000-0000-0000-3029-000000000001
```

Expected response:

```json
{
  "success": true,
  "tenant_id": "00000000-0000-0000-3029-000000000001",
  "session_count": 1,
  "sessions": [
    {
      "_id": "test-session-001",
      "message_count": 3,
      "last_message": "2026-03-04T..."
    }
  ]
}
```

✅ **Success criteria:** Shows your test session with 3 messages

---

## 🧹 Cleanup (Optional)

```powershell
# Delete test session
curl -X DELETE http://localhost:8001/chat/messages/test-session-001

# Verify it's gone
curl http://localhost:8001/chat/messages/test-session-001

# Check session aggregation is empty
curl http://localhost:8001/chat/sessions/00000000-0000-0000-3029-000000000001
```

---

## 🐛 If Something Goes Wrong

| Problem                            | Solution                                                      |
| ---------------------------------- | ------------------------------------------------------------- |
| **"Failed to connect to MongoDB"** | Check MongoDB running: `docker ps`                            |
| **API port 8001 in use**           | Kill process: `netstat -ano \| findstr :8001`                 |
| **Can't POST message**             | Check Content-Type header: `"Content-Type: application/json"` |
| **Messages don't load on reload**  | Check browser console for errors (F12)                        |
| **Timestamps weird in MongoDB**    | Normal - stored as ISO format with UTC                        |

---

## ✨ Expected Final State

```
✅ MongoDB running on port 27017
✅ Chat API running on port 8001
✅ Frontend running on port 8501
✅ Messages persist in MongoDB
✅ Reload page → history appears
✅ New messages auto-save
✅ Session tracking works
✅ DB status indicator shows "Connected"
```

**You're done!** 🎉
