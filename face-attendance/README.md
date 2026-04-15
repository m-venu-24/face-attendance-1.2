# 🎓 FaceAttend — Face Recognition Attendance System

A complete, offline-capable **face recognition attendance system** for laptops. Built with Python FastAPI + React. No internet needed after setup.

---

## 📦 What's Inside

```
face-attendance/
├── backend/              ← Python FastAPI server
│   ├── main.py           ← All API routes
│   ├── database.py       ← SQLite models & seed data
│   ├── face_utils.py     ← Face recognition utilities
│   ├── requirements.txt
│   └── uploads/          ← Student photos (auto-created)
│
├── frontend/             ← React + Vite + Tailwind
│   └── src/
│       ├── pages/
│       │   ├── Login.jsx
│       │   ├── Dashboard.jsx
│       │   ├── Students.jsx   ← Add students
│       │   ├── Enroll.jsx     ← Webcam face enrollment
│       │   ├── Attendance.jsx ← Live recognition
│       │   ├── Sessions.jsx
│       │   └── Reports.jsx
│       └── components/
│
├── setup.sh   ← Linux/Mac setup
├── setup.bat  ← Windows setup
├── start.sh   ← Linux/Mac launcher
└── start.bat  ← Windows launcher
```

---

## 🖥️ Prerequisites

| Tool | Version | Download |
|------|---------|----------|
| Python | 3.13 | https://python.org |
| Node.js | 18+ | https://nodejs.org |
| CMake | any | See below |

Note: The backend now uses lightweight local image matching and does not require CMake or dlib.
If you add a YOLO face model, it will improve detection quality before embedding matching.

### Native packages

No extra native build tools are required for the default setup.

### Optional YOLO face model

1. Install `ultralytics` in the backend environment.
2. Place a face-trained weights file at `backend/models/yolov8n-face.pt`.
3. Or set `YOLO_FACE_MODEL_PATH` to the model file path.

If the weights file is missing, the app falls back to the built-in center-crop detector.

---

## 🚀 Quick Start

### Linux / macOS

```bash
# 1. Make scripts executable
chmod +x setup.sh start.sh

# 2. Run setup (one time only — installs everything)
./setup.sh

# 3. Start the system
./start.sh

# 4. Open browser
# http://localhost:5173
```

### Windows

```batch
# 1. Run setup (double-click or in CMD)
setup.bat

# 2. Start the system
start.bat
```

---

## 🔑 Default Login Credentials

| Role | Username | Password |
|------|----------|----------|
| Admin | `admin` | `admin123` |
| Faculty | `faculty` | `faculty123` |

---

## 📋 How to Use

### Step 1 — Register Students
1. Go to **Students** → click **Add Student**
2. Fill in Name, Register Number, Department, Year, Section
3. Click **Enroll Face** button next to the student
4. Allow camera access in browser
5. **Capture 5+ face samples** (different angles for better accuracy)
6. Repeat for all students

### Step 2 — Take Attendance
1. Go to **Live Attendance**
2. Select Subject, Department, Year, Section
3. Click **Start Session & Open Camera**
4. Click **Start Scanning** — system auto-detects faces every 2.5 seconds
5. Recognized students are marked present automatically
6. Click **End Session** when done

### Step 3 — View Reports
- **Sessions** page: View attendance list for any session
- **Reports** page: Charts, student-wise records, subject analytics

---

## 🧠 Face Recognition Details

| Component | Library | Notes |
|-----------|---------|-------|
| Face Detection | `face_recognition` (HOG model) | Fast on CPU |
| Face Encoding | dlib 128-d embeddings | Industry standard |
| Matching | Euclidean distance | Threshold: 0.5 |
| Storage | SQLite (JSON) | No GPU needed |

**Accuracy tips:**
- Capture 5–10 samples per student
- Use good, even lighting
- Avoid extreme angles during enrollment
- Tolerance of 0.5 works well; lower = stricter, higher = more lenient

---

## 🛠️ Manual Start (without scripts)

**Terminal 1 — Backend:**
```bash
cd backend
python -m venv venv

# Linux/Mac:
source venv/bin/activate
# Windows:
venv\Scripts\activate

pip install -r requirements.txt
python main.py
# → Running on http://localhost:8000
```

**Terminal 2 — Frontend:**
```bash
cd frontend
npm install
npm run dev
# → Running on http://localhost:5173
```

---

## 🔌 API Reference (FastAPI)

The backend auto-generates interactive API docs:
- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

Key endpoints:
```
POST /api/login              — Authenticate
GET  /api/students           — List all students
POST /api/students           — Add student
POST /api/enroll-face        — Enroll face (base64 image)
POST /api/sessions           — Start attendance session
GET  /api/sessions/active    — Get active session
POST /api/recognize          — Recognize face & mark attendance
GET  /api/reports/session/:id — Session report
GET  /api/dashboard/stats    — Dashboard statistics
```

---

## ⚙️ Configuration

Backend (env vars override defaults in `backend/main.py`):
```bash
FACE_TOLERANCE=0.5
ACCESS_TOKEN_EXPIRE_MINUTES=480
FACEATTEND_SECRET_KEY=change-me
```

Frontend scan interval:
- `frontend/src/pages/Attendance.jsx` (default 2500ms)

---

## 🐛 Troubleshooting

**"dlib install failed" / CMake error**
→ Install CMake + build tools (see Prerequisites above)
→ On Windows, install Visual Studio Build Tools

**"No face detected"**
→ Ensure good lighting; face must be clearly visible
→ Camera resolution affects detection quality

**"Camera access denied"**
→ Browser must be on localhost (not IP) for camera access
→ Check browser permissions: chrome://settings/content/camera

**"Unknown face" even after enrollment**
→ Enroll more samples (aim for 8–10)
→ Ensure same lighting conditions as during enrollment
→ Check department/year/section matches between student and session

**Frontend shows "Network Error"**
→ Make sure backend is running on port 8000
→ Check that `vite.config.js` proxy is pointing to correct port

---

## 📚 Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, Vite, Tailwind CSS, Recharts |
| Backend | Python 3.11, FastAPI, Uvicorn |
| Database | SQLite (via SQLAlchemy) |
| AI/ML | face_recognition, dlib, OpenCV |
| Auth | JWT (python-jose) |

---

## 🎯 Project Architecture

```
Browser (React)
    │  HTTP (localhost:5173 → proxy → 8000)
    ▼
FastAPI Backend
    │  SQLAlchemy ORM
    ├─▶ SQLite Database (attendance.db)
    │
    │  face_recognition library
    └─▶ dlib 128-d face embeddings
```

---

Made for college prototype demonstration. All processing is local — no cloud, no data sent anywhere.
