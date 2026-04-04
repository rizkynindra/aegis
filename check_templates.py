import os
from dotenv import load_dotenv
load_dotenv()

from database import SessionLocal, TaskTemplate, TeamCategory

db = SessionLocal()
try:
    tmpls = db.query(TaskTemplate).all()
    print(f"--- Task Templates (Total: {len(tmpls)}) ---")
    for t in tmpls:
        cat = db.query(TeamCategory).filter_by(id=t.team_category_id).first()
        print(f"[{t.status_level}] Team: {cat.name if cat else 'N/A'} (ID: {t.team_category_id}) | Title: {t.title}")
finally:
    db.close()
