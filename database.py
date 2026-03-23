import os
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime

from sqlalchemy.pool import NullPool

# Database URL: use env var for Vercel/Neon PostgreSQL, fallback to SQLite for local dev
DATABASE_URL = os.environ.get("DATABASE_URL", "DATABASE_URL")

# Fix for Neon/Supabase URLs that start with "postgres://" (SQLAlchemy needs "postgresql://")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# SQLite needs check_same_thread=False, PostgreSQL needs NullPool for serverless
connect_args = {}
pool_kwargs = {}

if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
else:
    # Use NullPool for PostgreSQL on Vercel serverless to prevent connection limit exhaustion
    pool_kwargs = {"poolclass": NullPool}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    **pool_kwargs
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, index=True)
    password = Column(String(200))
    role = Column(String(50))
    name = Column(String(200))

class NotificationSetting(Base):
    __tablename__ = "notification_settings"

    id = Column(Integer, primary_key=True, index=True)
    condition = Column(String(200), unique=True, index=True)
    is_active = Column(Boolean, default=True)

class PushSubscription(Base):
    __tablename__ = "push_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    endpoint = Column(String(500), unique=True, index=True)
    p256dh = Column(String(200))
    auth = Column(String(200))
    user_role = Column(String(50), default="guest")
    
    def to_dict(self):
        return {
            "endpoint": self.endpoint,
            "keys": {
                "p256dh": self.p256dh,
                "auth": self.auth
            },
            "user_role": self.user_role
        }

class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    message = Column(String(500))
    condition_matched = Column(String(200))

class TaskTemplate(Base):
    __tablename__ = "task_templates"

    id = Column(Integer, primary_key=True, index=True)
    status_level = Column(String(50), index=True)
    title = Column(String(200))
    description = Column(String(500), nullable=True)
    requires_photo = Column(Boolean, default=True)

class EmergencyEvent(Base):
    __tablename__ = "emergency_events"

    id = Column(Integer, primary_key=True, index=True)
    status_level = Column(String(50), index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)

    tasks = relationship("EmergencyTask", back_populates="event")

class EmergencyTask(Base):
    __tablename__ = "emergency_tasks"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("emergency_events.id"))
    template_id = Column(Integer, ForeignKey("task_templates.id"))
    title = Column(String(200))
    
    is_completed = Column(Boolean, default=False)
    photo_path = Column(Text, nullable=True)  # Text for large base64 strings
    completed_at = Column(DateTime, nullable=True)
    completed_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    event = relationship("EmergencyEvent", back_populates="tasks")
    user = relationship("User") 

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
