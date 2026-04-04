import os
from dotenv import load_dotenv
load_dotenv()

from database import SessionLocal, TeamCategory, PreventiveTask, User

db = SessionLocal()
try:
    cats = db.query(TeamCategory).all()
    print(f"Total Categories: {len(cats)}")
    for c in cats:
        print(f"  - {c.id}: {c.name}")
    
    tasks = db.query(PreventiveTask).all()
    print(f"\nTotal Preventive Tasks: {len(tasks)}")
    
    users = db.query(User).all()
    print(f"\nTotal Users: {len(users)}")
    for u in users:
        print(f"  - {u.username} (Role: {u.role}, Cat ID: {u.team_category_id})")
        
    # Check specifically for tim_fire_and_floods
    target = db.query(User).filter_by(username='tim_fire_and_floods').first()
    if target:
        print(f"\n✅ User 'tim_fire_and_floods' found!")
        print(f"  Name: {target.name}")
        print(f"  Category ID: {target.team_category_id}")
        
        if target.team_category_id:
            cat_tasks = db.query(PreventiveTask).filter_by(team_category_id=target.team_category_id).all()
            print(f"  Tasks for this user's category: {len(cat_tasks)}")
            for pt in cat_tasks:
                print(f"    - {pt.title}")
    else:
        print("\n❌ User 'tim_fire_and_floods' NOT found.")

finally:
    db.close()
