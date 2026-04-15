#!/bin/bash
echo ""
echo "🚀 Starting FaceAttend..."
echo ""

# Kill existing processes on our ports
kill $(lsof -t -i:8000) 2>/dev/null || true
kill $(lsof -t -i:5173) 2>/dev/null || true

# Start backend
echo "▶  Starting backend on http://localhost:8000"
cd backend
source venv/bin/activate
python main.py &
BACKEND_PID=$!
cd ..

# Wait for backend to be ready
sleep 3

# Start frontend
echo "▶  Starting frontend on http://localhost:5173"
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   FaceAttend is running!                 ║"
echo "║                                          ║"
echo "║   Open: http://localhost:5173            ║"
echo "║   Admin: admin / admin123                ║"
echo "║   Faculty: faculty / faculty123          ║"
echo "║                                          ║"
echo "║   Press Ctrl+C to stop                  ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# Wait and cleanup on Ctrl+C
trap "echo ''; echo 'Stopping...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT
wait
