# 🎯 COMPLETE SETUP GUIDE - from ZERO to WORKING

This guide walks you through EVERYTHING step-by-step.

---

## 📍 **STEP 0: Clean Up (if something is already running)**

```powershell
# Stop all Docker containers
docker-compose down

# Kill any Python processes (Streamlit, uvicorn)
# Just close all open terminals and start fresh

# Clear any old builds
docker system prune -a
```

---

## 🚀 **STEP 1: Start MongoDB (in Docker)**

**Open Terminal 1** and run:

```powershell
cd e:\CLOUDLY\copilot_lite\netai_copilot

# Start ONLY MongoDB in Docker
docker run -d `
  --name netai-mongodb `
  -p 27017:27017 `
  -e MONGO_INITDB_ROOT_USERNAME=admin `
  -e MONGO_INITDB_ROOT_PASSWORD=password123 `
  mongo:latest

# Wait 5 seconds for it to start
Start-Sleep -Seconds 5

# Check if it's running
docker ps
```

✅ **You should see:** A container named `netai-mongodb` with status `Up`

---

## 🔌 **STEP 2: Start Dummy API (locally)**

**Open Terminal 2** and run:

```powershell
cd e:\CLOUDLY\copilot_lite\netai_copilot\dummy-api

# Install dependencies
pip install -r requirements.txt

# Start the API
uvicorn main:app --reload --port 8001
```

✅ **You should see:** `Uvicorn running on http://127.0.0.1:8001`

---

## 🛠️ **STEP 3: Start MCP Server (locally)**

**Open Terminal 3** and run:

```powershell
cd e:\CLOUDLY\copilot_lite\netai_copilot\mcp-server

# Install dependencies (if not already done)
pip install -r requirements.txt

# Start the server
python server.py
```

✅ **You should see:** `Starting MCP Server on 0.0.0.0:8002`

---

## 💬 **STEP 4: Start Frontend (locally)**

**Open Terminal 4** and run:

```powershell
cd e:\CLOUDLY\copilot_lite\netai_copilot

# Start Streamlit
python -m streamlit run frontend/app.py
```

✅ **You should see:** `Local URL: http://localhost:8501`

---

## ✅ **STEP 5: Verify Everything is Connected**

**In Terminal 2 (dummy-api), you should see:**

```
INFO:     Uvicorn running on http://127.0.0.1:8001
```

**Test the connection:**

```powershell
# Open a NEW terminal 5 and test the API
curl http://localhost:8001/health/db
```

✅ **Expected response:**

```json
{
  "status": "healthy",
  "database": "MongoDB",
  "connection": "active"
}
```

If you see this, **everything is connected!**

---

## 🗄️ **STEP 6: View Data in MongoDB Compass**

### **Step 6a: Download Compass** (if you haven't)

- Go to: https://www.mongodb.com/products/tools/compass
- Download and install it

### **Step 6b: Connect to Your MongoDB**

Open MongoDB Compass and:

1. Click **"New Connection"** or **"Create"**
2. Paste this connection string:
   ```
   mongodb://admin:password123@localhost:27017/?authSource=admin
   ```
3. Click **"Connect"**

✅ **You should now see:**

- Database: `netai_copilot`
- Collection: `error_logs`
- 3 sample error documents inside

### **Step 6c: View the Data**

Click on `netai_copilot` → `error_logs` and you'll see 3 documents:

```json
{
  error_code: "TIMEOUT_BDT",
  message: "BDT Engine timeout after 30 seconds",
  ...
}
```

You can click on each document to expand and see all fields!

---

## 🔍 **STEP 7: View Data in Docker (Alternative to Compass)**

If you don't want to use Compass, you can use the Docker shell:

```powershell
# Connect to MongoDB shell
docker exec -it netai-mongodb mongosh -u admin -p password123 netai_copilot

# Inside the shell, try these commands:
db.error_logs.find().pretty()         # View all logs
db.error_logs.countDocuments()        # Count total
exit
```

✅ **You should see:** 3 error log documents printed

---

## 🎬 **STEP 8: Test the Full System**

### **Test 1: Check API Endpoints**

```powershell
# In a new terminal, test getting logs from API:
curl http://localhost:8001/v1/tenants/00000000-0000-0000-3029-000000000001/baselines/logs/errors
```

✅ Should return 3 error logs as JSON

### **Test 2: Use the Frontend**

1. Open browser: http://localhost:8501
2. Type a message: `"What worker is crashing?"`
3. The Debugger Agent will:
   - Call MCP Server
   - MCP Server calls dummy-api
   - Dummy API queries MongoDB
   - Returns logs to agent
   - Agent analyzes and responds

---

## 📊 **The Complete Flow (Visual)**

```
Your Laptop (Windows)
│
├─ Docker Container (MongoDB on port 27017)
│
├─ Python Scripts (Local):
│  │
│  ├─ Dummy API (port 8001) → talks to MongoDB
│  │
│  ├─ MCP Server (port 8002) → talks to Dummy API
│  │
│  └─ Frontend/Streamlit (port 8501) → talks to MCP Server
│
└─ MongoDB Compass (your GUI) → connects to MongoDB on port 27017
```

---

## 🐛 **Troubleshooting**

### **"MongoDB not connecting"**

```powershell
# Check if Docker container is running
docker ps

# If not running, restart it
docker run -d --name netai-mongodb -p 27017:27017 -e MONGO_INITDB_ROOT_USERNAME=admin -e MONGO_INITDB_ROOT_PASSWORD=password123 mongo:latest
```

### **"Port 8001 already in use"**

```powershell
# Kill the process using that port
netstat -ano | findstr :8001
taskkill /PID <PID_NUMBER> /F

# Or change port in dummy-api startup
uvicorn main:app --port 8002
```

### **"Cannot connect to MongoDB in Compass"**

1. Make sure Docker container is running: `docker ps`
2. Check the connection string: `mongodb://admin:password123@localhost:27017/?authSource=admin`
3. Make sure port 27017 is not blocked

### **"FAISS index not found"**

```powershell
# Run the ingest script
python knowledge_base/ingest.py
```

---

## 📝 **Your Checklist**

- [ ] Terminal 1: MongoDB running in Docker (`docker ps` shows `netai-mongodb`)
- [ ] Terminal 2: Dummy API running (`curl http://localhost:8001/health/db` returns healthy)
- [ ] Terminal 3: MCP Server running (`Starting MCP Server on 0.0.0.0:8002`)
- [ ] Terminal 4: Frontend running (`Local URL: http://localhost:8501`)
- [ ] MongoDB Compass: Connected and showing `netai_copilot` database
- [ ] Browser: http://localhost:8501 loads Streamlit chat interface
- [ ] Test: Ask the chatbot a question about errors

Once ALL are checked, you're fully set up! ✅

---

## 🎯 **Once Everything Works**

### **See Data in Compass:**

- Shows database structure visually
- Can edit documents directly
- Great for debugging

### **Use the Frontend:**

- Type: `"What errors are happening?"`
- The system fetches from MongoDB
- Analyzes with AI
- Returns insights

### **View Logs in Terminal:**

- See what each service is doing
- Debug any issues
- Monitor data flow

---

## 🚀 **Next: Full Docker Deployment**

Once you're comfortable with this setup, you can deploy everything in Docker:

```powershell
# All 4 services in Docker with one command
docker-compose up -d

# Everything runs in isolation
# Perfect for production
```

But for now, **stick with MongoDB in Docker + local services** - easier to develop and debug!

---

## ❓ **Questions?**

- **"How do I see MongoDB data?"** → Use Compass (Step 6) or Docker shell (Step 7)
- **"How do I know if API is working?"** → Test with `curl` (Step 8, Test 1)
- **"How do I know if everything is connected?"** → Use the frontend (Step 8, Test 2)
- **"Where are error logs stored?"** → In MongoDB database (viewed in Compass)

**Start with Step 0 and follow in order!**
