from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta
from passlib.context import CryptContext
from jose import JWTError, jwt
import json, os
from PIL import Image

from database import get_db, init_db, Student, FaceEmbedding, Subject, Session as AttSession, Attendance, User
from face_utils import decode_base64_image, get_face_embedding, get_face_embedding_candidates, compare_faces

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    try:
        return float(value)
    except ValueError:
        return default

def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default

SECRET_KEY = os.getenv("FACEATTEND_SECRET_KEY", "face-attendance-secret-2024")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = _env_int("ACCESS_TOKEN_EXPIRE_MINUTES", 60 * 8)
FACE_TOLERANCE = _env_float("FACE_TOLERANCE", 0.5)

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
app = FastAPI(title="Face Attendance System")
auth_scheme = HTTPBearer(auto_error=False)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")


# ─── AUTH ────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str

def create_token(data: dict):
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({**data, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(auth_scheme),
    db: Session = Depends(get_db),
):
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    credentials_exception = HTTPException(
        status_code=401,
        detail="Invalid credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        user = db.query(User).filter(User.username == username).first()
        if not user:
            raise credentials_exception
        return user
    except JWTError:
        raise credentials_exception

def require_admin(current_user: User):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user

@app.post("/api/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == req.username).first()
    if not user or not pwd_context.verify(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_token({"sub": user.username, "role": user.role})
    return {"access_token": token, "token_type": "bearer", "role": user.role, "username": user.username}


@app.get("/api/me")
def read_current_user(current_user: User = Depends(get_current_user)):
    return {"id": current_user.id, "username": current_user.username, "role": current_user.role}


# ─── STUDENTS ────────────────────────────────────────────────────────────────

class StudentCreate(BaseModel):
    name: str
    register_no: str
    department: str
    year: str
    section: str

@app.get("/api/students")
def list_students(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    students = db.query(Student).all()
    result = []
    for s in students:
        emb_count = db.query(FaceEmbedding).filter(FaceEmbedding.student_id == s.id).count()
        result.append({
            "id": s.id,
            "name": s.name,
            "register_no": s.register_no,
            "department": s.department,
            "year": s.year,
            "section": s.section,
            "photo_path": s.photo_path,
            "face_enrolled": emb_count > 0,
            "embedding_count": emb_count,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        })
    return result

@app.post("/api/students")
def create_student(student: StudentCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    existing = db.query(Student).filter(Student.register_no == student.register_no).first()
    if existing:
        raise HTTPException(status_code=400, detail="Register number already exists")
    new_student = Student(**student.dict())
    db.add(new_student)
    db.commit()
    db.refresh(new_student)
    return {"id": new_student.id, "message": "Student created successfully"}

@app.delete("/api/students/{student_id}")
def delete_student(student_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_admin(current_user)
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    db.query(FaceEmbedding).filter(FaceEmbedding.student_id == student_id).delete()
    db.query(Attendance).filter(Attendance.student_id == student_id).delete()
    db.delete(student)
    db.commit()
    return {"message": "Student deleted"}

@app.get("/api/students/{student_id}")
def get_student(student_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Not found")
    return student


# ─── FACE ENROLLMENT ─────────────────────────────────────────────────────────

class FaceEnrollRequest(BaseModel):
    student_id: int
    image_base64: str  # base64 encoded image from webcam

@app.post("/api/enroll-face")
def enroll_face(req: FaceEnrollRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    student = db.query(Student).filter(Student.id == req.student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    try:
        image_array = decode_base64_image(req.image_base64)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image: {str(e)}")

    embedding = get_face_embedding(image_array)
    if embedding is None:
        raise HTTPException(status_code=400, detail="No face detected in image. Please ensure face is clearly visible.")

    # Save photo if first enrollment
    if not student.photo_path:
        photo_filename = f"student_{student.id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.jpg"
        photo_path = f"uploads/{photo_filename}"
        img = Image.fromarray(image_array)
        img.save(photo_path)
        student.photo_path = photo_filename
        db.commit()

    # Store embedding
    emb_record = FaceEmbedding(
        student_id=student.id,
        embedding_json=json.dumps(embedding)
    )
    db.add(emb_record)
    db.commit()

    count = db.query(FaceEmbedding).filter(FaceEmbedding.student_id == student.id).count()
    return {"message": "Face enrolled successfully", "total_samples": count}

@app.delete("/api/students/{student_id}/embeddings")
def clear_embeddings(student_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.query(FaceEmbedding).filter(FaceEmbedding.student_id == student_id).delete()
    db.commit()
    return {"message": "Face data cleared"}


# ─── SUBJECTS ────────────────────────────────────────────────────────────────

@app.get("/api/subjects")
def list_subjects(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Subject).all()

class SubjectCreate(BaseModel):
    subject_name: str
    subject_code: str
    department: str

@app.post("/api/subjects")
def create_subject(subject: SubjectCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    s = Subject(**subject.dict())
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


# ─── SESSIONS ────────────────────────────────────────────────────────────────

class SessionCreate(BaseModel):
    subject_id: int
    department: str
    year: str
    section: str

@app.post("/api/sessions")
def start_session(req: SessionCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # End any previous active sessions
    active = db.query(AttSession).filter(AttSession.is_active == True).all()
    for s in active:
        s.is_active = False
        s.end_time = datetime.utcnow()

    session = AttSession(
        subject_id=req.subject_id,
        faculty_id=current_user.id,
        department=req.department,
        year=req.year,
        section=req.section,
        date=datetime.utcnow().strftime("%Y-%m-%d"),
        is_active=True,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return {"session_id": session.id, "message": "Session started"}

@app.get("/api/sessions/active")
def get_active_session(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session = db.query(AttSession).filter(AttSession.is_active == True).first()
    if not session:
        return None
    subject = db.query(Subject).filter(Subject.id == session.subject_id).first()
    return {
        "id": session.id,
        "subject_name": subject.subject_name if subject else "Unknown",
        "subject_code": subject.subject_code if subject else "",
        "department": session.department,
        "year": session.year,
        "section": session.section,
        "date": session.date,
        "start_time": session.start_time.isoformat(),
    }

@app.post("/api/sessions/{session_id}/end")
def end_session(session_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session = db.query(AttSession).filter(AttSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    session.is_active = False
    session.end_time = datetime.utcnow()
    db.commit()
    return {"message": "Session ended"}

@app.get("/api/sessions")
def list_sessions(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sessions = db.query(AttSession).order_by(AttSession.start_time.desc()).limit(20).all()
    result = []
    for s in sessions:
        subject = db.query(Subject).filter(Subject.id == s.subject_id).first()
        count = db.query(Attendance).filter(Attendance.session_id == s.id).count()
        result.append({
            "id": s.id,
            "subject_name": subject.subject_name if subject else "Unknown",
            "department": s.department,
            "year": s.year,
            "section": s.section,
            "date": s.date,
            "start_time": s.start_time.isoformat(),
            "is_active": s.is_active,
            "present_count": count,
        })
    return result


# ─── FACE RECOGNITION / ATTENDANCE ───────────────────────────────────────────

class RecognizeRequest(BaseModel):
    image_base64: str
    session_id: int

@app.post("/api/recognize")
def recognize_and_mark(req: RecognizeRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session = db.query(AttSession).filter(AttSession.id == req.session_id, AttSession.is_active == True).first()
    if not session:
        raise HTTPException(status_code=400, detail="No active session found")

    try:
        image_array = decode_base64_image(req.image_base64)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image: {str(e)}")

    # Get students matching this class
    students = db.query(Student).filter(
        Student.department == session.department,
        Student.year == session.year,
        Student.section == session.section,
    ).all()

    if not students:
        return {"status": "no_students", "message": "No students registered for this class"}

    # Load embeddings
    known_embeddings = []
    for student in students:
        embs = db.query(FaceEmbedding).filter(FaceEmbedding.student_id == student.id).all()
        for emb in embs:
            known_embeddings.append({
                "student_id": student.id,
                "embedding": json.loads(emb.embedding_json)
            })

    if not known_embeddings:
        return {"status": "no_embeddings", "message": "No face data enrolled for this class"}

    # Get embedding candidates from live frame
    unknown_embeddings = get_face_embedding_candidates(image_array)
    if not unknown_embeddings:
        return {"status": "no_face", "message": "No face detected in frame"}

    # Compare against all candidates and keep the strongest result
    match = None
    for candidate in unknown_embeddings:
        candidate_match = compare_faces(known_embeddings, candidate, tolerance=FACE_TOLERANCE)
        if candidate_match and (match is None or candidate_match["confidence"] > match["confidence"]):
            match = candidate_match

    if not match:
        return {"status": "unknown", "message": "Face not recognized", "confidence": 0}

    if not match.get("matched", False):
        return {
            "status": "unknown",
            "message": "Face not recognized",
            "confidence": round(match["confidence"], 2),
        }

    student_id = match["student_id"]
    confidence = match["confidence"]

    # Check duplicate attendance in this session
    existing = db.query(Attendance).filter(
        Attendance.student_id == student_id,
        Attendance.session_id == req.session_id,
    ).first()

    if existing:
        student = db.query(Student).filter(Student.id == student_id).first()
        return {
            "status": "duplicate",
            "message": f"{student.name} already marked present",
            "student_name": student.name,
            "register_no": student.register_no,
            "confidence": confidence,
        }

    # Mark attendance
    att = Attendance(
        student_id=student_id,
        session_id=req.session_id,
        confidence=confidence,
        status="present",
    )
    db.add(att)
    db.commit()

    student = db.query(Student).filter(Student.id == student_id).first()
    return {
        "status": "marked",
        "message": f"Attendance marked for {student.name}",
        "student_name": student.name,
        "register_no": student.register_no,
        "confidence": confidence,
    }


# ─── REPORTS ─────────────────────────────────────────────────────────────────

@app.get("/api/reports/session/{session_id}")
def session_report(session_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session = db.query(AttSession).filter(AttSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    subject = db.query(Subject).filter(Subject.id == session.subject_id).first()

    # All students in class
    students = db.query(Student).filter(
        Student.department == session.department,
        Student.year == session.year,
        Student.section == session.section,
    ).all()

    # Present students
    attended = db.query(Attendance).filter(Attendance.session_id == session_id).all()
    present_ids = {a.student_id for a in attended}

    result = []
    for s in students:
        att = next((a for a in attended if a.student_id == s.id), None)
        result.append({
            "student_id": s.id,
            "name": s.name,
            "register_no": s.register_no,
            "status": "present" if s.id in present_ids else "absent",
            "confidence": att.confidence if att else None,
            "time": att.timestamp.strftime("%H:%M:%S") if att else None,
        })

    return {
        "session": {
            "id": session.id,
            "subject": subject.subject_name if subject else "",
            "date": session.date,
            "department": session.department,
            "year": session.year,
            "section": session.section,
        },
        "total": len(students),
        "present": len(present_ids),
        "absent": len(students) - len(present_ids),
        "attendance": result,
    }

@app.get("/api/reports/student/{student_id}")
def student_attendance_report(student_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Not found")

    records = db.query(Attendance).filter(Attendance.student_id == student_id).all()
    result = []
    for r in records:
        session = db.query(AttSession).filter(AttSession.id == r.session_id).first()
        subject = db.query(Subject).filter(Subject.id == session.subject_id).first() if session else None
        result.append({
            "date": session.date if session else "",
            "subject": subject.subject_name if subject else "",
            "time": r.timestamp.strftime("%H:%M:%S"),
            "confidence": r.confidence,
        })
    return {"student": {"name": student.name, "register_no": student.register_no}, "records": result}

@app.get("/api/dashboard/stats")
def dashboard_stats(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    total_students = db.query(Student).count()
    enrolled = db.query(Student).join(FaceEmbedding, Student.id == FaceEmbedding.student_id).distinct().count()
    total_sessions = db.query(AttSession).count()
    today = datetime.utcnow().strftime("%Y-%m-%d")
    today_sessions = db.query(AttSession).filter(AttSession.date == today).count()
    today_attendance = db.query(Attendance).join(AttSession).filter(AttSession.date == today).count()
    active_session = db.query(AttSession).filter(AttSession.is_active == True).first()

    return {
        "total_students": total_students,
        "face_enrolled": enrolled,
        "total_sessions": total_sessions,
        "today_sessions": today_sessions,
        "today_attendance": today_attendance,
        "has_active_session": active_session is not None,
    }


@app.on_event("startup")
def startup():
    init_db()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
