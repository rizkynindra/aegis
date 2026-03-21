from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
import json

SQLALCHEMY_DATABASE_URL = "sqlite:///./weather_app.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password = Column(String)
    role = Column(String)
    name = Column(String)

class NotificationSetting(Base):
    __tablename__ = "notification_settings"

    id = Column(Integer, primary_key=True, index=True)
    condition = Column(String, unique=True, index=True) # e.g., "hujan ringan", "hujan lebat", "berawan"
    is_active = Column(Boolean, default=True)

class PushSubscription(Base):
    __tablename__ = "push_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    endpoint = Column(String, unique=True, index=True)
    p256dh = Column(String)
    auth = Column(String)
    user_role = Column(String, default="guest")
    
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
    message = Column(String)
    condition_matched = Column(String)

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
