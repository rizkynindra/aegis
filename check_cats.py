import os
from dotenv import load_dotenv
load_dotenv()

from database import SessionLocal, TeamCategory

db = SessionLocal()
try:
    cats = db.query(TeamCategory).all()
    print("--- Disaster Team Categories ---")
    for c in cats:
        print(f"ID: {c.id} | Name: {c.name}")
finally:
    db.close()
