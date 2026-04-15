#!/bin/bash
set -e

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   FaceAttend — Setup Script              ║"
echo "║   Face Recognition Attendance System     ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# ── Check Python ──────────────────────────────
if ! command -v python3 &>/dev/null; then
  echo "❌ Python 3 not found. Install Python 3.9+ from https://python.org"
  exit 1
fi

PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "✅ Python $PYTHON_VERSION found"

# ── Check Node ────────────────────────────────
if ! command -v node &>/dev/null; then
  echo "❌ Node.js not found. Install from https://nodejs.org"
  exit 1
fi
echo "✅ Node $(node --version) found"

# ── Check CMake (needed by dlib/face_recognition) ──
if ! command -v cmake &>/dev/null; then
  echo ""
  echo "⚠️  CMake not found (required for face_recognition/dlib)."
  echo "   Install it:"
  echo "   Ubuntu/Debian: sudo apt-get install cmake build-essential"
  echo "   Mac:           brew install cmake"
  echo "   Then re-run this script."
  exit 1
fi
echo "✅ CMake found"

# ── Backend Setup ─────────────────────────────
echo ""
echo "📦 Setting up Python backend..."
cd backend

python3 -m venv venv
source venv/bin/activate

echo "   Installing Python packages (this takes a few minutes for dlib)..."
pip install --upgrade pip -q
pip install -r requirements.txt

echo "✅ Backend ready"
deactivate
cd ..

# ── Frontend Setup ────────────────────────────
echo ""
echo "📦 Installing frontend packages..."
cd frontend
npm install --silent
echo "✅ Frontend ready"
cd ..

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   ✅ Setup Complete!                     ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "To start the system, run:  ./start.sh"
echo ""
echo "Or start manually in two terminals:"
echo "  Terminal 1 (Backend):  cd backend && source venv/bin/activate && python main.py"
echo "  Terminal 2 (Frontend): cd frontend && npm run dev"
echo ""
echo "Then open: http://localhost:5173"
echo "Login:     admin / admin123"
echo ""
