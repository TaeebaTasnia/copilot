# ⚡ Quick Reference Card

## 🚀 Start Everything

### Terminal 1: MongoDB

```powershell
docker run -d --name netai-mongodb `
  -p 27017:27017 `
  -e MONGO_INITDB_ROOT_USERNAME=admin `
  -e MONGO_INITDB_ROOT_PASSWORD=password123 `
  mongo:latest
```

### Terminal 2: Chat API

```powershell
cd dummy-api
pip install -r requirements.txt
python -m uvicorn main:app --port 8001
```

### Terminal 3: Frontend

```powershell
cd frontend
pip install -r requirements.txt
python -m streamlit run app.py
```

Open: **http://localhost:8501**

---

## 📍 Ports

| Service  | Port  | URL                       |
| -------- | ----- | ------------------------- |
| Frontend | 8501  | http://localhost:8501     |
| Chat API | 8001  | http://localhost:8001     |
| MongoDB  | 27017 | mongodb://localhost:27017 |

---

## 🔐 Database Credentials

```
Username: admin
Password: password123
Database: netai_copilot
Collection: chat_history
```

---

## 📤 API Endpoints

### Save Message

```bash
POST /chat/messages
Content-Type: application/json

{
  "tenant_id": "00000000-0000-0000-3029-000000000001",
  "session_id": "uuid",
  "role": "user",
  "content": "Hello"
}
```

### Get History

```bash
GET /chat/messages/{session_id}
```

### Delete Session

```bash
DELETE /chat/messages/{session_id}
```

### Get All Sessions

```bash
GET /chat/sessions/{tenant_id}
```

### Health Checks

```bash
GET /health
GET /health/db
```

---

## 🔍 View Data in MongoDB

### Via Command Line

```powershell
docker exec -it netai-mongodb mongosh -u admin -p password123 netai_copilot

# In MongoDB shell:
db.chat_history.find().pretty()
db.chat_history.countDocuments()
exit
```

### Via MongoDB Compass

1. Download: https://www.mongodb.com/products/tools/compass
2. Connect: `mongodb://admin:password123@localhost:27017/?authSource=admin`
3. Browse: `netai_copilot` → `chat_history`

---

## 🧪 Quick Tests

### Test API Health

```powershell
curl http://localhost:8001/health/db
```

### Test Save Message

```powershell
$body = @{
    tenant_id = "00000000-0000-0000-3029-000000000001"
    session_id = "test"
    role = "user"
    content = "Hello"
} | ConvertTo-Json

curl -X POST `
  -H "Content-Type: application/json" `
  -d $body `
  http://localhost:8001/chat/messages
```

### Test Retrieve Messages

```powershell
curl http://localhost:8001/chat/messages/test
```

---

## 🐛 Troubleshooting

| Problem                | Solution                                                  |
| ---------------------- | --------------------------------------------------------- |
| Port 8001 in use       | `netstat -ano \| findstr :8001` then kill process         |
| MongoDB not connecting | `docker ps` to verify container running                   |
| Modules not found      | `pip install -r requirements.txt` in correct directory    |
| Messages not saving    | Check API running: `curl http://localhost:8001/health/db` |
| History not loading    | Check CHAT_API_URL in environment                         |

---

## 📚 Documentation Files

| File                       | Purpose                           |
| -------------------------- | --------------------------------- |
| **CHAT_HISTORY_SETUP.md**  | System overview & architecture    |
| **CODE_REFERENCE.md**      | Code changes & API details        |
| **SYSTEM_ARCHITECTURE.md** | Detailed architecture diagrams    |
| **TESTING_GUIDE.md**       | Step-by-step testing instructions |
| **QUICK_REFERENCE.md**     | This card!                        |

---

## 🎯 Data Model

```json
{
  "_id": "mongodb-id",
  "timestamp": "2026-03-04T10:15:00Z",
  "tenant_id": "00000000-0000-0000-3029-000000000001",
  "session_id": "uuid-here",
  "role": "user",
  "content": "Your message here",
  "metadata": {}
}
```

---

## ✅ Success Indicators

| Check            | Expected                                          |
| ---------------- | ------------------------------------------------- |
| MongoDB running  | `docker ps` shows container                       |
| API started      | Console: `✅ Connected to MongoDB`                |
| API health       | `curl /health` → `"status": "healthy"`            |
| DB connected     | `curl /health/db` → `"status": "healthy"`         |
| Message saved    | `curl /chat/messages` → returns `"success": true` |
| Frontend loaded  | Browser shows chat interface                      |
| Messages persist | Reload page → history appears                     |

---

## 🎯 Tenant ID

```
00000000-0000-0000-3029-000000000001
```

(Same for all users in development)

---

## 🎯 Common Session ID (Example)

```
a1b2c3d4-e5f6-g7h8-i9j0-k1l2m3n4o5p6
```

(Generated automatically per browser)

---

## 📝 Environment Variables

```powershell
# Set before running frontend
$env:CHAT_API_URL = "http://localhost:8001"

# Or in .env file
CHAT_API_URL=http://localhost:8001
MONGODB_URL=mongodb://admin:password123@localhost:27017/netai_copilot?authSource=admin
```

---

## 🔄 Message Flow

```
User Typing
    ↓
Frontend Sends POST /chat/messages
    ↓
API Saves to MongoDB
    ↓
Message Displayed in Chat
    ↓
Page Reload
    ↓
Frontend Sends GET /chat/messages/{session_id}
    ↓
API Retrieves from MongoDB
    ↓
History Appears in Chat
```

---

## 💾 Basic Queries

### Find all messages in a session

```javascript
db.chat_history.find({ session_id: "test" });
```

### Find user messages only

```javascript
db.chat_history.find({ role: "user" });
```

### Count all messages

```javascript
db.chat_history.countDocuments();
```

### Delete a session

```javascript
db.chat_history.deleteMany({ session_id: "test" });
```

### Find latest messages

```javascript
db.chat_history.find().sort({ timestamp: -1 }).limit(5);
```

---

## 🔗 Connection Strings

### Local Development

```
mongodb://admin:password123@localhost:27017/netai_copilot?authSource=admin
```

### Docker Compose

```
mongodb://admin:password123@mongodb:27017/netai_copilot?authSource=admin
```

---

## 📊 Collection Indexes

```javascript
Indexes created:
1. {tenant_id: 1, session_id: 1, timestamp: -1}
2. {session_id: 1}
3. {timestamp: -1}

Benefits:
- Fast session lookups
- Quick message retrieval
- Chronological ordering
```

---

## 🎓 Key Concepts

| Term           | Meaning                           |
| -------------- | --------------------------------- |
| **tenant_id**  | Which customer (for multi-tenant) |
| **session_id** | Which conversation (UUID)         |
| **role**       | "user" or "assistant"             |
| **timestamp**  | When message was saved (UTC)      |
| **metadata**   | Extra data (timestamps, etc.)     |

---

## 🔒 Authentication

**Local Development:** None required

- MongoDB: Username/password but local only
- API: No authentication
- Frontend: No authentication

**Production:** Add authentication layer before deploying

---

## 🚀 Next Steps

1. ✅ Start MongoDB (Terminal 1)
2. ✅ Start API (Terminal 2)
3. ✅ Start Frontend (Terminal 3)
4. ✅ Open http://localhost:8501
5. ✅ Send a message
6. ✅ Reload page
7. ✅ Verify message persists

---

**That's it! You're ready to chat! 🎉**

For more details, see:

- TESTING_GUIDE.md for step-by-step instructions
- SYSTEM_ARCHITECTURE.md for deep dive
- CODE_REFERENCE.md for code details
