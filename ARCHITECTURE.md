# 🏗️ NetAI Copilot System Architecture

## 📋 What Was Done

### **1. Added MongoDB Service to docker-compose.yml**

- Pulls latest Alpine MongoDB image
- Runs initialization script (`init-mongo.js`) on startup
- Creates sample error logs automatically
- Persists data in `mongodb_data` volume

### **2. Updated dummy-api to Use MongoDB**

- Replaced file-based log reading with MongoDB queries
- Added async support (`motor` - MongoDB async driver)
- Can now READ and CREATE logs in database
- Includes fallback to JSON files if MongoDB isn't available

### **3. Created MongoDB Initialization Script**

- **Location:** `scripts/init-mongo.js`
- Runs automatically when MongoDB container starts
- Creates `error_logs` collection with schema validation
- Inserts 3 sample error logs (BDT timeout, missing CSV, worker crash)
- Creates database indexes for fast queries

### **4. Fixed All Paths**

- Changed `knowledge/` → `knowledge_base/` everywhere
- Updated docker-compose.yml volumes
- Updated Dockerfile.ingest
- Updated .env file

### **5. Created Documentation**

- **QUICKSTART.md** - Get running in 5 minutes
- **MONGODB_GUIDE.md** - Learn MongoDB concepts & commands

---

## 🔄 How Everything Works Together

### **Data Flow: Ask About Errors**

```
User in Frontend
  │
  ├─ Types: "What worker is crashing?"
  │
  ▼
Router Agent
  │
  ├─ Detects: "This is an error question"
  │
  ▼
Debugger Agent (LLM with tool access)
  │
  ├─ Calls: fetch_error_logs tool
  │
  ▼
MCP Server (http://localhost:8002)
  │
  ├─ Receives: Tool call request
  │
  ▼
Dummy API (http://localhost:8001)
  │
  ├─ Executes: MongoDB query
  │   db.error_logs.find({ tenant_id: "..." })
  │
  ▼
MongoDB Container (port 27017)
  │
  ├─ Returns: 3 error log documents
  │   - __id: ObjectId
  │   - timestamp: 2026-03-03T...
  │   - error_code: WORKER_CRASH
  │   - context: { worker_id: "worker_03", ... }
  │   - stack_trace: MemoryError: Unable to allocate...
  │
  ▼
Dummy API
  │
  ├─ Converts: ObjectId → string, timestamp → ISO string
  ├─ Returns: JSON array of logs
  │
  ▼
MCP Server
  │
  ├─ Returns: Tool result to debugger agent
  │
  ▼
Debugger Agent (LLM)
  │
  ├─ Analyzes: Error logs
  ├─ Uses: Groq model to reason about them
  ├─ Generates: "Worker_03 crashed due to MemoryError..."
  │
  ▼
Frontend
  │
  └─ Displays: Agent's analysis to user
```

---

## 🐳 Docker Networking

When using `docker-compose`, all services can talk to each other using service names:

```
dummy-api → mongodb:27017     (MongoDB driver connection)
mcp-server → http://dummy-api:8001   (HTTP calls)
frontend → http://mcp-server:8002    (HTTP calls)
```

This means:

- ✅ Services don't need to know local IP addresses
- ✅ Works the same on any machine
- ✅ No localhost issues
- ✅ Perfect for demos and production

---

## 📊 MongoDB Structure

### **Database:** `netai_copilot`

### **Collection:** `error_logs`

```javascript
{
  _id: ObjectId("65f8a2c1d5e3f9b2c0d1e2f3"),

  // Required fields
  timestamp: ISODate("2026-03-03T10:15:00Z"),
  tenant_id: "00000000-0000-0000-3029-000000000001",
  error_code: "WORKER_CRASH",
  message: "Worker process crashed unexpectedly",

  // Optional fields
  severity: "CRITICAL",
  context: {
    session_id: "sess_125",
    dataset_id: "process_batch_2026",
    worker_id: "worker_03",
    component: "scheduler"
  },

  stack_trace: "MemoryError: Unable to allocate 8 GB RAM...",
  metadata: {
    process_pid: 12345,
    memory_used_gb: 7.8,
    memory_limit_gb: 8
  }
}
```

### **Indexes (for fast queries):**

```javascript
{ tenant_id: 1, timestamp: -1 }  // Find recent logs for a tenant
{ error_code: 1 }                // Find logs by error type
{ severity: 1 }                  // Find critical errors
```

---

## 🚀 How to Run

### **Full Containerized (Recommended)**

```powershell
docker-compose up -d
# All 4 services start automatically:
# - MongoDB (port 27017)
# - dummy-api (port 8001)
# - mcp-server (port 8002)
# - frontend (port 8501)
```

### **Step by Step (For debugging)**

```powershell
# Terminal 1: MongoDB
docker-compose up -d mongodb

# Terminal 2: Dummy API
cd dummy-api && uvicorn main:app --port 8001

# Terminal 3: MCP Server
cd mcp-server && python server.py

# Terminal 4: Frontend
python -m streamlit run frontend/app.py
```

---

## 🧪 How to Verify It Works

### **1. MongoDB is Running**

```powershell
curl http://localhost:8001/health/db
# Returns: {"status": "healthy", "database": "MongoDB", "connection": "active"}
```

### **2. API Can Query MongoDB**

```powershell
curl http://localhost:8001/v1/tenants/00000000-0000-0000-3029-000000000001/baselines/logs/errors
# Returns: Array of 3 error logs as JSON
```

### **3. Frontend Can Talk to MCP Server**

```powershell
# Open http://localhost:8501
# Type: "What errors are in my system?"
# Should return analysis of logs
```

### **4. Connect to MongoDB Shell**

```powershell
docker-compose exec mongodb mongosh -u admin -p password123 netai_copilot
# Then: db.error_logs.find().pretty()
# Shows all logs in the database
```

---

## 🎯 Key Improvements Over Previous Setup

| Aspect               | Before               | Now                   |
| -------------------- | -------------------- | --------------------- |
| **Data Source**      | Static JSON files    | Live MongoDB database |
| **Add Logs**         | Manual file creation | API endpoint (POST)   |
| **Update Logs**      | Not possible         | Possible via MongoDB  |
| **Scale**            | Limited to file size | Millions of documents |
| **Persistence**      | Depends on files     | Guaranteed in DB      |
| **Production Ready** | Not really           | Yes!                  |

---

## 🔐 Production Considerations

For **production**, you'd want to:

1. **Change default credentials**

   ```
   MONGO_INITDB_ROOT_USERNAME: admin → your_real_user
   MONGO_INITDB_ROOT_PASSWORD: password123 → strong_password
   ```

2. **Use secrets management** (not env vars)
   - Docker Secrets
   - Kubernetes Secrets
   - Azure Key Vault
   - HashiCorp Vault

3. **Enable authentication**

   ```javascript
   // In init-mongo.js, create restricted users:
   db.createUser({
     user: "app_user",
     pwd: "app_password",
     roles: [{ role: "readWrite", db: "netai_copilot" }],
   });
   ```

4. **Setup replication/backup**
   - MongoDB Atlas (managed service)
   - Manual replication
   - Regular backups to S3

5. **Monitor and log**
   - Enable MongoDB audit log
   - Setup alerts for failures
   - Track query performance

---

## 📚 File Reference

| File                         | Purpose                              |
| ---------------------------- | ------------------------------------ |
| `docker-compose.yml`         | Orchestrates all services + MongoDB  |
| `scripts/init-mongo.js`      | Initializes MongoDB with sample data |
| `dummy-api/main.py`          | API that queries MongoDB             |
| `dummy-api/requirements.txt` | Added `pymongo`, `motor`             |
| `Dockerfile.ingest`          | Fixed path to `knowledge_base/`      |
| `docker-compose.ingest.yml`  | Fixed volume path                    |
| `.env`                       | Fixed FAISS_INDEX_PATH               |
| `QUICKSTART.md`              | Get started guide                    |
| `MONGODB_GUIDE.md`           | Learn MongoDB                        |

---

## 🎉 You're All Set!

Your NetAI Copilot now has:

- ✅ Real MongoDB database (not just files)
- ✅ Full Docker orchestration
- ✅ Automatic initialization
- ✅ Production-ready architecture
- ✅ Easy to scale and modify

**Next:** Run `docker-compose up -d` and enjoy!
