from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

DATABASE_URL = "sqlite:///./attendance.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password_hash = Column(String)
    role = Column(String, default="faculty")  # admin / faculty


class Student(Base):
    __tablename__ = "students"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    register_no = Column(String, unique=True, index=True)
    department = Column(String)
    year = Column(String)
    section = Column(String)
    photo_path = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    embeddings = relationship("FaceEmbedding", back_populates="student")
    attendances = relationship("Attendance", back_populates="student")


class FaceEmbedding(Base):
    __tablename__ = "face_embeddings"
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"))
    embedding_json = Column(Text)  # JSON string of 128-d vector
    created_at = Column(DateTime, default=datetime.utcnow)
    student = relationship("Student", back_populates="embeddings")


class Subject(Base):
    __tablename__ = "subjects"
    id = Column(Integer, primary_key=True, index=True)
    subject_name = Column(String)
    subject_code = Column(String, unique=True)
    department = Column(String)


class Session(Base):
    __tablename__ = "sessions"
    id = Column(Integer, primary_key=True, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"))
    faculty_id = Column(Integer, ForeignKey("users.id"))
    department = Column(String)
    year = Column(String)
    section = Column(String)
    date = Column(String)
    start_time = Column(DateTime, default=datetime.utcnow)
    end_time = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    subject = relationship("Subject")
    attendances = relationship("Attendance", back_populates="session")


class Attendance(Base):
    __tablename__ = "attendance"
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"))
    session_id = Column(Integer, ForeignKey("sessions.id"))
    timestamp = Column(DateTime, default=datetime.utcnow)
    confidence = Column(Float)
    status = Column(String, default="present")
    student = relationship("Student", back_populates="attendances")
    session = relationship("Session", back_populates="attendances")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    # Seed default admin
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
    admin = db.query(User).filter(User.username == "admin").first()
    if not admin:
        db.add(User(username="admin", password_hash=pwd_context.hash("admin123"), role="admin"))
    elif not admin.password_hash.startswith("$pbkdf2-sha256$"):
        admin.password_hash = pwd_context.hash("admin123")
    faculty = db.query(User).filter(User.username == "faculty").first()
    if not faculty:
        db.add(User(username="faculty", password_hash=pwd_context.hash("faculty123"), role="faculty"))
    elif not faculty.password_hash.startswith("$pbkdf2-sha256$"):
        faculty.password_hash = pwd_context.hash("faculty123")
    # Seed subjects
    if db.query(Subject).count() == 0:
        subjects = [
            Subject(subject_name="Data Structures", subject_code="CS301", department="CSE"),
            Subject(subject_name="Operating Systems", subject_code="CS302", department="CSE"),
            Subject(subject_name="Database Management", subject_code="CS303", department="CSE"),
            Subject(subject_name="Computer Networks", subject_code="CS304", department="CSE"),
            Subject(subject_name="Machine Learning", subject_code="CS401", department="CSE"),
        ]
        db.add_all(subjects)
    db.commit()
    db.close()
