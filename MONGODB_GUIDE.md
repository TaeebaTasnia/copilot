# MongoDB Setup & Testing Guide for NetAI Copilot

## 🗄️ **What is MongoDB?**

MongoDB is a **NoSQL database** that stores data as **JSON-like documents** instead of traditional tables. Here's a breakdown:

### **Relational Database (SQL)** vs **MongoDB (NoSQL)**

```
SQL (Traditional):
┌─────────────────────────────────────┐
│ error_logs table                    │
├─────────────────────────────────────┤
│ id  │ tenant_id │ message │ time    │
├─────────────────────────────────────┤
│ 1   │ tenant-1  │ timeout │ 2026... │
└─────────────────────────────────────┘

MongoDB (Document):
{
  _id: ObjectId("..."),
  tenant_id: "tenant-1",
  message: "timeout",
  timestamp: ISODate("2026-03-03T10:15:00Z"),
  context: {
    worker_id: "worker_01",
    component: "bdt_engine"
  }
}
```

### **MongoDB Key Concepts:**

| Term           | Meaning                                                       |
| -------------- | ------------------------------------------------------------- |
| **Database**   | Container for collections (like a schema in SQL)              |
| **Collection** | Group of documents (like a table in SQL)                      |
| **Document**   | Single record with flexible fields (like a row, but can vary) |
| **Field**      | Key-value pair (like a column)                                |
| **ObjectId**   | Auto-generated unique ID (\_id)                               |

---

## 🚀 **How to Run Everything**

### **Option 1: Full Docker Setup (Recommended)**

```powershell
cd e:\CLOUDLY\copilot_lite\netai_copilot

# Start all services with Docker
docker-compose up -d

# Check services are running
docker-compose ps

# View logs
docker-compose logs -f
```

**What happens:**

1. MongoDB starts and runs `init-mongo.js` (inserts sample data)
2. Dummy API starts and connects to MongoDB
3. MCP Server starts
4. Frontend starts

---

### **Option 2: Local Development (MongoDB in Docker, other services local)**

```powershell
# Terminal 1: Start MongoDB only
docker-compose up -d mongodb

# Terminal 2: Start dummy-api
cd dummy-api
pip install -r requirements.txt
uvicorn main:app --reload --port 8001

# Terminal 3: Start MCP server
cd mcp-server
python server.py

# Terminal 4: Start frontend
python -m streamlit run frontend/app.py
```

---

## 🧪 **How to Test MongoDB**

### **1. Install MongoDB Client (mongosh)**

```powershell
# Option A: Using Docker (easiest)
docker-compose exec mongodb mongosh -u admin -p password123

# Option B: Install locally
# Download from: https://www.mongodb.com/try/download/shell
# Then run: mongosh "mongodb://admin:password123@localhost:27017" --authenticationDatabase admin
```

### **2. Basic MongoDB Commands**

Once you're in the MongoDB shell (`>`), try these:

```javascript
// Show all databases
show dbs

// Switch to our database
use netai_copilot

// Show all collections
show collections

// View all error logs
db.error_logs.find().pretty()

// Find logs with a specific error code
db.error_logs.find({ error_code: "TIMEOUT_BDT" }).pretty()

// Find logs for a specific tenant
db.error_logs.find({ tenant_id: "00000000-0000-0000-3029-000000000001" }).pretty()

// Count total logs
db.error_logs.countDocuments()

// Find only CRITICAL severity logs
db.error_logs.find({ severity: "CRITICAL" }).pretty()

// Get latest log (sorted by timestamp)
db.error_logs.findOne({}, { sort: { timestamp: -1 } })

// Update a log (add a field)
db.error_logs.updateOne(
  { error_code: "TIMEOUT_BDT" },
  { $set: { resolved: true } }
)

// Delete a log (don't do this in production!)
db.error_logs.deleteOne({ error_code: "WORKER_CRASH" })

// Create an index for faster queries
db.error_logs.createIndex({ tenant_id: 1, timestamp: -1 })

// Exit mongosh
exit
```

---

## 🔍 **How to Test the Dummy API**

### **Test 1: Check if MongoDB is Connected**

```powershell
curl http://localhost:8001/health/db
```

**Expected response:**

```json
{
  "status": "healthy",
  "database": "MongoDB",
  "connection": "active"
}
```

---

### **Test 2: Fetch Error Logs from API**

```powershell
curl http://localhost:8001/v1/tenants/00000000-0000-0000-3029-000000000001/baselines/logs/errors
```

**Expected response:**

```json
[
  {
    "_id": "65f8a2c1d5e3f9b2c0d1e2f3",
    "timestamp": "2026-03-03T10:15:00",
    "tenant_id": "00000000-0000-0000-3029-000000000001",
    "severity": "CRITICAL",
    "error_code": "TIMEOUT_BDT",
    "message": "BDT Engine timeout after 30 seconds",
    "context": { ... }
  },
  ...
]
```

---

### **Test 3: Create a New Error Log**

```powershell
$body = @{
    error_code = "NEW_ERROR"
    message = "This is a test error"
    severity = "ERROR"
    context = @{
        worker_id = "test_worker"
        component = "test_component"
    }
} | ConvertTo-Json

curl -X POST `
  -H "Content-Type: application/json" `
  -d $body `
  http://localhost:8001/v1/tenants/00000000-0000-0000-3029-000000000001/baselines/logs/errors
```

---

## 📊 **What Data is Stored?**

Your MongoDB has **3 sample error logs** (from `init-mongo.js`):

1. **BDT Timeout** - BDT Engine timed out after 30 seconds
2. **Missing CSV** - Input CSV file not found
3. **Worker Crash** - Worker process ran out of memory

When your Debugger Agent asks for logs, it fetches these from MongoDB and analyzes them!

---

## 🔧 **Troubleshooting**

### **Q: MongoDB won't connect**

```powershell
# Check if MongoDB container is running
docker-compose ps

# View MongoDB logs
docker-compose logs mongodb

# Restart MongoDB
docker-compose restart mongodb
```

### **Q: How do I see what the Dummy API got from MongoDB?**

```powershell
# Check API logs
docker-compose logs dummy-api

# Or run locally and watch the terminal
```

### **Q: How do I inspect the raw MongoDB data?**

```powershell
# Connect to MongoDB shell
docker-compose exec mongodb mongosh -u admin -p password123 netai_copilot

# Then run MongoDB commands above
```

### **Q: Can I delete all logs and start fresh?**

```javascript
// In mongosh:
use netai_copilot
db.error_logs.deleteMany({})  // Delete all
db.error_logs.drop()           // Delete collection entirely

// Then restart the container to re-initialize from init-mongo.js
```

---

## 📝 **Your Architecture Now**

```
Frontend (Streamlit)
    ↓
Generic Agent (RAG search) + Debugger Agent
    ↓
MCP Server → Dummy API
    ↓
MongoDB (Docker Container)
```

**The flow:**

1. User asks about an error in the frontend
2. Debugger Agent calls MCP Server's `fetch_error_logs` tool
3. MCP Server calls Dummy API at `http://dummy-api:8001`
4. Dummy API queries MongoDB for error logs
5. Logs are returned and analyzed by the agent

---

## 🎯 **Next Steps**

1. Run `docker-compose up -d` to start everything
2. Test with `curl` commands above
3. Use the frontend to ask the Debugger Agent about errors
4. Connect to MongoDB shell to inspect data
5. Later: Add real error logs from your platform!
