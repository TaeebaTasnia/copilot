# 🚀 NetAI Copilot - Quick Start Guide

## ✅ What's Been Done

Your system is now **fully containerized with MongoDB**:

- ✅ MongoDB service added to `docker-compose.yml`
- ✅ Dummy API updated to read/write error logs from MongoDB
- ✅ `init-mongo.js` creates database and sample data automatically
- ✅ All paths updated from `knowledge/` to `knowledge_base/`
- ✅ FAISS index paths fixed everywhere

---

## 🎯 Quick Start (5 Minutes)

### **Option 1: Full Docker (Recommended) - Easiest**

```powershell
cd e:\CLOUDLY\copilot_lite\netai_copilot

# Start everything with one command
docker-compose up -d

# Wait 10 seconds for MongoDB to initialize
Start-Sleep -Seconds 10

# Check everything is running
docker-compose ps

# View logs to see what's happening
docker-compose logs -f
```

Then open: **http://localhost:8501**

---

### **Option 2: Docker + Local (If you're debugging)**

```powershell
# Terminal 1: Start MongoDB only
docker-compose up -d mongodb

# Wait for MongoDB to be ready (check health)
docker-compose ps

# Terminal 2: Start dummy-api
cd dummy-api
pip install -r requirements.txt
uvicorn main:app --reload --port 8001

# Terminal 3: Start MCP server
cd ..\mcp-server
python server.py

# Terminal 4: Start frontend
cd ..
python -m streamlit run frontend/app.py
```

---

## 🧪 Test It Works

### **Step 1: Check MongoDB is running**

```powershell
curl http://localhost:8001/health/db
```

Should return: `"status": "healthy"`

### **Step 2: Get error logs from API**

```powershell
curl http://localhost:8001/v1/tenants/00000000-0000-0000-3029-000000000001/baselines/logs/errors
```

Should return 3 error logs from MongoDB

### **Step 3: Try the frontend**

1. Open http://localhost:8501
2. Type: `"I'm seeing worker crash errors"`
3. It should fetch logs from MongoDB and analyze them!

---

## 📊 All Services Explained

| Service        | Port  | Purpose                        |
| -------------- | ----- | ------------------------------ |
| **MongoDB**    | 27017 | Stores all error logs          |
| **Dummy API**  | 8001  | Serves error logs from MongoDB |
| **MCP Server** | 8002  | Routes tool calls to dummy-api |
| **Frontend**   | 8501  | Chat interface (Streamlit)     |

---

## 🔧 Common Commands

### **View MongoDB Data**

```powershell
# Connect to MongoDB shell
docker-compose exec mongodb mongosh -u admin -p password123

# Then in the shell:
use netai_copilot
db.error_logs.find().pretty()
exit
```

### **View Container Logs**

```powershell
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f dummy-api
docker-compose logs -f mongodb
```

### **Restart a Service**

```powershell
docker-compose restart mongodb
docker-compose restart dummy-api
```

### **Stop Everything**

```powershell
docker-compose down

# Also remove volumes (deletes MongoDB data)
docker-compose down -v
```

---

## 🎓 What Just Happened

### **Before (Without MongoDB):**

```
Error request
  → Dummy API reads from mock JSON files
  → Returns static data
```

### **Now (With MongoDB):**

```
Error request
  → Dummy API queries MongoDB
  → Can add/update/delete logs programmatically
  → Data persists between requests
  → Can scale to millions of logs
```

---

## 📚 Learn More

- **MONGODB_GUIDE.md** - Detailed MongoDB concepts & commands
- **docker-compose.yml** - See how services are connected
- **mcp-server/server.py** - How MCP Server calls dummy-api
- **dummy-api/main.py** - How dummy-api connects to MongoDB

---

## ❓ Troubleshooting

| Issue                         | Solution                                          |
| ----------------------------- | ------------------------------------------------- |
| **502 Bad Gateway**           | Make sure MongoDB is running: `docker-compose ps` |
| **FAISS index not found**     | Run: `python knowledge_base/ingest.py`            |
| **Cannot connect to MongoDB** | Check: `docker-compose logs mongodb`              |
| **Port already in use**       | Change port in docker-compose.yml                 |

---

## 🎬 Demo Script

Here's what you'd say when demoing:

> _"This is NetAI Copilot with MongoDB integration. I have error logs stored in a MongoDB database. When I ask the system about errors, it queries the database, analyzes the logs, and gives me insights._"
>
> **Type in chat:** `"What worker is crashing and why?"`
>
> _"Notice it fetched real logs from MongoDB and identified the root cause: out-of-memory error in worker_03. It even told me the exact numerical values."_

---

**You're all set!** Run `docker-compose up -d` and enjoy your containerized system. 🎉
