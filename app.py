from fastapi import FastAPI, Request, Form, BackgroundTasks, Depends, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session
import os
import json
import httpx
import asyncio
import base64
from datetime import datetime, timedelta
from pywebpush import webpush, WebPushException
from dotenv import load_dotenv

load_dotenv()

from database import engine, Base, get_db, SessionLocal
from database import User, TeamCategory, NotificationSetting, PushSubscription, ActivityLog, TaskTemplate, EmergencyEvent, EmergencyTask, AdHocReport, PreventiveTask, PreventiveReport

app = FastAPI()

# Create tables
Base.metadata.create_all(bind=engine)

# ─── Environment Variables ───────────────────────────────────────────────────
VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY")
VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY")
VAPID_EMAIL = os.environ.get("VAPID_EMAIL", "admin@aegis.corp")
VAPID_CLAIMS = {"sub": f"mailto:{VAPID_EMAIL}"}
SESSION_SECRET = os.environ.get("SESSION_SECRET")
BMKG_API_URL = os.environ.get("BMKG_API_URL")
CRON_SECRET = os.environ.get("CRON_SECRET")

# ─── Middleware ──────────────────────────────────────────────────────────────
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET)

# ─── Templates & Static ─────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

# ─── Helpers ─────────────────────────────────────────────────────────────────
def get_current_user_from_session(request: Request):
    return request.session.get("user")

def require_role(request: Request, role: str):
    user = get_current_user_from_session(request)
    if not user or user.get("role") != role:
        raise HTTPException(status_code=403, detail="Forbidden")
    return user

def send_broadcast_notification(db: Session, title: str, body: str):
    subs = db.query(PushSubscription).all()
    sent_count = 0
    for sub in subs:
        try:
            webpush(
                subscription_info=sub.to_dict(),
                data=json.dumps({"title": title, "body": body}),
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims=VAPID_CLAIMS
            )
            sent_count += 1
        except WebPushException:
            pass
    return sent_count

# ─── Startup: Seed DB ────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup_event():
    db = SessionLocal()
    try:
        if not db.query(User).filter(User.username == "admin").first():
            db.add(User(employee_id="admin", username="admin", password="123", role="admin", name="Administrator"))
        db.commit()
    except Exception as e:
        print(f"Error during startup seeding: {e}")
        db.rollback()
    finally:
        db.close()

# ─── Routes: Auth ────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def read_item(request: Request):
    user = get_current_user_from_session(request)
    if not user:
        return RedirectResponse(url="/login")
    if user.get("role") == "admin":
        return RedirectResponse(url="/admin/dashboard", status_code=303)
    if user.get("role") == "disaster":
        return RedirectResponse(url="/disaster/dashboard", status_code=303)
    return templates.TemplateResponse("index.html", {"request": request, "user": user})

@app.get("/evaluation", response_class=HTMLResponse)
async def evaluation_report(request: Request, db: Session = Depends(get_db)):
    user_session = require_role(request, "normal")
    user = db.query(User).filter(User.employee_id == user_session["username"]).first()
    return templates.TemplateResponse("evaluation.html", {"request": request, "user": user})

@app.get("/login", response_class=HTMLResponse)
async def login_get(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login_post(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    # "username" parameter from HTML form now refers to Employee ID
    user = db.query(User).filter(User.employee_id == username).first()
    if user and user.password == password:
        request.session["user"] = {"username": user.employee_id, "role": user.role, "name": user.name}
        if user.role == "admin":
            return RedirectResponse(url="/admin/dashboard", status_code=303)
        if user.role == "disaster":
            return RedirectResponse(url="/disaster/dashboard", status_code=303)
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request, "error": "Username atau password salah"})

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login")

# ─── Routes: API ─────────────────────────────────────────────────────────────
@app.get("/api/user")
async def get_current_user(request: Request):
    user = get_current_user_from_session(request)
    if not user:
        return {"error": "Not logged in"}
    return user

@app.get("/api/vapid-public-key")
async def get_vapid_key():
    return {"publicKey": VAPID_PUBLIC_KEY}

@app.post("/api/subscribe")
async def subscribe(request: Request, db: Session = Depends(get_db)):
    subscription = await request.json()
    user = get_current_user_from_session(request)
    user_role = user["role"] if user else "guest"
    
    existing = db.query(PushSubscription).filter(PushSubscription.endpoint == subscription.get("endpoint")).first()
    
    if not existing:
        new_sub = PushSubscription(
            endpoint=subscription.get("endpoint"),
            p256dh=subscription.get("keys", {}).get("p256dh"),
            auth=subscription.get("keys", {}).get("auth"),
            user_role=user_role
        )
        db.add(new_sub)
        db.commit()
    else:
        if existing.user_role != user_role:
            existing.user_role = user_role
            db.commit()
            
    return {"status": "success"}

def send_broadcast_notification(db: Session, title: str, message: str):
    subs = db.query(PushSubscription).all()
    sent = 0
    for sub in subs:
        try:
            webpush(
                subscription_info=sub.to_dict(),
                data=json.dumps({"title": title, "body": message}),
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims=VAPID_CLAIMS
            )
            sent += 1
        except WebPushException as ex:
            if ex.response and ex.response.status_code == 410:
                db.delete(sub)
                db.commit()
    return sent

@app.post("/api/notify-all")
async def notify_all_endpoint(title: str = Form(...), message: str = Form(...), db: Session = Depends(get_db)):
    sent = send_broadcast_notification(db, title, message)
    return {"sent": sent}

@app.get("/manifest.json")
async def manifest():
    return FileResponse(os.path.join("static", "manifest.json"))

@app.get("/sw.js")
async def service_worker():
    return FileResponse(os.path.join("static", "sw.js"), media_type="application/javascript")

@app.get("/api/weather")
async def get_weather():
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(BMKG_API_URL)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}

@app.get("/api/active-conditions")
async def get_active_conditions(db: Session = Depends(get_db)):
    active_settings = db.query(NotificationSetting).filter(NotificationSetting.is_active == True).all()
    return {"conditions": [s.condition for s in active_settings]}

# ─── Routes: Emergency Tasks ────────────────────────────────────────────────
@app.get("/api/tasks/templates")
async def get_task_templates(db: Session = Depends(get_db)):
    tmpl = db.query(TaskTemplate).all()
    return tmpl

@app.post("/api/events/")
async def create_emergency_event(status_level: str = Form(...), db: Session = Depends(get_db)):
    event = EmergencyEvent(status_level=status_level)
    db.add(event)
    db.commit()
    db.refresh(event)

    tmpl = db.query(TaskTemplate).filter(TaskTemplate.status_level == status_level).all()
    for template in tmpl:
        task = EmergencyTask(
            event_id=event.id,
            template_id=template.id,
            team_category_id=template.team_category_id,
            title=template.title
        )
        db.add(task)
    db.commit()
    return {"status": "success", "event_id": event.id, "tasks_created": len(tmpl)}

@app.get("/api/events/active/tasks")
async def get_active_event_tasks(request: Request, db: Session = Depends(get_db)):
    user_session = get_current_user_from_session(request)
    if not user_session:
        raise HTTPException(status_code=401, detail="Not logged in")
    
    user = db.query(User).filter(User.employee_id == user_session["username"]).first()
    
    event = db.query(EmergencyEvent).filter(EmergencyEvent.is_active == True).order_by(EmergencyEvent.id.desc()).first()
    if not event:
        return {"tasks": [], "event": None}
    
    # Filter tasks by user category
    query = db.query(EmergencyTask).filter(EmergencyTask.event_id == event.id)
    if user.role != "admin" and user.team_category_id:
        query = query.filter(EmergencyTask.team_category_id == user.team_category_id)
    
    tasks = query.all()
    task_list = []
    for t in tasks:
        task_list.append({
            "id": t.id,
            "title": t.title,
            "is_completed": t.is_completed,
            "photo_path": t.photo_path,
            "completed_at": t.completed_at,
            "completed_by": t.completed_by
        })
    return {"event_id": event.id, "status_level": event.status_level, "tasks": task_list}

@app.post("/api/tasks/{task_id}/report")
async def report_task_completion(
    request: Request,
    task_id: int,
    content: str = Form(...),
    actions_taken: str = Form(""),
    planned_actions: str = Form(""),
    monitoring_notes: str = Form(""),
    photo: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    user_session = get_current_user_from_session(request)
    if not user_session:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    user = db.query(User).filter(User.employee_id == user_session["username"]).first()
    
    task = db.query(EmergencyTask).filter(EmergencyTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Update task with report fields
    task.report_content = content
    task.actions_taken = actions_taken
    task.planned_actions = planned_actions
    task.monitoring_notes = monitoring_notes
    task.is_completed = True
    task.completed_at = datetime.utcnow()
    task.completed_by = user.id

    if photo:
        contents = await photo.read()
        task.photo_path = f"data:image/jpeg;base64,{base64.b64encode(contents).decode()}"
    
    db.commit()
    # Notify everyone
    send_broadcast_notification(db, f"SOP {task.title}", f"Laporan penyelesaian tugas dari {user.name}")
    return {"status": "success", "message": "Zadatak i izvješće su uspješno spremljeni"}

@app.get("/api/incidents/recent")
async def get_recent_incidents(db: Session = Depends(get_db)):
    one_month_ago = datetime.utcnow() - timedelta(days=30)
    # Fetch tasks that have report content (merged system)
    tasks = db.query(EmergencyTask).filter(
        EmergencyTask.report_content != None,
        EmergencyTask.completed_at >= one_month_ago
    ).order_by(EmergencyTask.completed_at.desc()).all()
    
    return [{
        "id": t.id,
        "title": t.title,
        "content": t.report_content,
        "author": t.user.name if t.user else "N/A",
        "timestamp": t.completed_at.strftime("%d %b %Y, %H:%M"),
        "actions_taken": t.actions_taken,
        "planned_actions": t.planned_actions,
        "monitoring_notes": t.monitoring_notes
    } for t in tasks]

@app.post("/api/reports/adhoc")
async def create_adhoc_report(
    request: Request,
    category: str = Form(...),
    content: str = Form(...),
    actions_taken: str = Form(""),
    planned_actions: str = Form(""),
    monitoring_notes: str = Form(""),
    photo: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    user_session = get_current_user_from_session(request)
    if not user_session:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    user = db.query(User).filter(User.employee_id == user_session["username"]).first()
    
    new_report = AdHocReport(
        user_id=user.id,
        category=category,
        content=content,
        actions_taken=actions_taken,
        planned_actions=planned_actions,
        monitoring_notes=monitoring_notes
    )

    if photo:
        contents = await photo.read()
        new_report.photo_path = f"data:image/jpeg;base64,{base64.b64encode(contents).decode()}"
    
    db.add(new_report)
    db.commit()
    # Notify everyone
    send_broadcast_notification(db, f"Laporan {category}", f"Kejadian baru dilaporkan oleh {user.name}")
    return {"status": "success", "message": "Laporan berhasil dikirim"}

@app.get("/api/reports/adhoc/recent")
async def get_recent_adhoc_reports(db: Session = Depends(get_db)):
    one_month_ago = datetime.utcnow() - timedelta(days=30)
    reports = db.query(AdHocReport).filter(
        AdHocReport.timestamp >= one_month_ago
    ).order_by(AdHocReport.timestamp.desc()).all()
    
    return [{
        "id": r.id,
        "category": r.category,
        "content": r.content,
        "author": r.user.name if r.user else "N/A",
        "timestamp": r.timestamp.strftime("%d %b %Y, %H:%M"),
        "actions_taken": r.actions_taken,
        "planned_actions": r.planned_actions,
        "monitoring_notes": r.monitoring_notes,
        "photo_path": r.photo_path
    } for r in reports]

@app.post("/api/tasks/{task_id}/upload")
async def upload_task_photo(
    request: Request, 
    task_id: int, 
    photo: UploadFile = File(...), 
    db: Session = Depends(get_db)
):
    user = get_current_user_from_session(request)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    task = db.query(EmergencyTask).filter(EmergencyTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
        
    contents = await photo.read()
    base64_encoded = base64.b64encode(contents).decode("utf-8")
    mime_type = photo.content_type or "image/jpeg"
        
    task.photo_path = f"data:{mime_type};base64,{base64_encoded}"
    db.commit()
    return {"status": "success", "task_id": task.id, "photo_path": task.photo_path}

@app.post("/api/tasks/{task_id}/complete")
async def complete_task(
    request: Request, 
    task_id: int, 
    db: Session = Depends(get_db)
):
    user = get_current_user_from_session(request)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    db_user = db.query(User).filter(User.employee_id == user["username"]).first()
    task = db.query(EmergencyTask).filter(EmergencyTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
        
    if not task.photo_path:
        raise HTTPException(status_code=400, detail="Harap upload foto bukti terlebih dahulu!")
        
    task.is_completed = True
    task.completed_at = datetime.utcnow()
    task.completed_by = db_user.id
    
    db.commit()
    
    uncompleted_tasks = db.query(EmergencyTask).filter(
        EmergencyTask.event_id == task.event_id, 
        EmergencyTask.is_completed == False
    ).count()
    
    if uncompleted_tasks == 0:
        event = db.query(EmergencyEvent).filter(EmergencyEvent.id == task.event_id).first()
        if event:
            event.is_active = False
            event.resolved_at = datetime.utcnow()
            db.commit()
            
    return {"status": "success", "task_id": task.id, "photo_path": task.photo_path, "event_completed": uncompleted_tasks == 0}

@app.post("/api/emergency/evacuate")
async def trigger_evacuation(request: Request, db: Session = Depends(get_db)):
    user_session = get_current_user_from_session(request)
    if not user_session:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    user = db.query(User).filter(User.employee_id == user_session["username"]).first()
    if not user or not user.team_category or user.id != user.team_category.leader_id:
        raise HTTPException(status_code=403, detail="Hanya Team Leader yang dapat memberikan instruksi evakuasi!")
    
    # 1. Create a high-alert Emergency Event
    active_event = db.query(EmergencyEvent).filter(EmergencyEvent.is_active == True).first()
    if not active_event:
        active_event = EmergencyEvent(status_level="EVAKUASI")
        db.add(active_event)
        db.commit()
        db.refresh(active_event)
        
        # Add emergency tasks for each team from templates
        templates = db.query(TaskTemplate).all() # Get all templates for high alert?
        for t in templates:
             db.add(EmergencyTask(
                 event_id=active_event.id,
                 template_id=t.id,
                 team_category_id=t.team_category_id,
                 title=t.title
             ))
        db.commit()
        
    # 2. Log activity
    log = ActivityLog(message=f"INSTRUKSI EVAKUASI dikeluarkan oleh {user.name} ({user.team_category.name})", condition_matched="EVAKUASI")
    db.add(log)
    db.commit()
    
    # 3. Broadcast notification
    msg = "INSTRUKSI EVAKUASI: Silahkan tinggalkan gedung melalui jalur evakuasi menuju titik kumpul!"
    send_broadcast_notification(db, "🚨 EMERGENCY: EVAKUASI! 🚨", msg)
    
    return {"status": "success", "message": "Instruksi evakuasi telah dikirim ke seluruh karyawan."}

# ─── Routes: Admin Dashboard ────────────────────────────────────────────────
@app.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request, db: Session = Depends(get_db)):
    user_session = require_role(request, "admin")
    user = db.query(User).filter(User.employee_id == user_session["username"]).first()
    
    settings = db.query(NotificationSetting).order_by(NotificationSetting.id.desc()).all()
    logs = db.query(ActivityLog).order_by(ActivityLog.timestamp.desc()).limit(10).all()
    
    recent_tasks = db.query(EmergencyTask).filter(
        EmergencyTask.photo_path.isnot(None)
    ).order_by(EmergencyTask.completed_at.desc()).limit(20).all()
    
    users = db.query(User).order_by(User.id).all()
    categories = db.query(TeamCategory).order_by(TeamCategory.name).all()
    
    return templates.TemplateResponse("admin_dashboard.html", {
        "request": request, 
        "user": user, 
        "settings": settings,
        "logs": logs,
        "recent_tasks": recent_tasks,
        "users": users,
        "categories": categories
    })

# ─── Admin API: Leadership Management ──────────────────────────────────────
@app.get("/api/admin/teams")
async def get_admin_teams(request: Request, db: Session = Depends(get_db)):
    require_role(request, "admin")
    teams = db.query(TeamCategory).all()
    result = []
    for t in teams:
        leader_name = "Belum Ditentukan"
        if t.leader:
            leader_name = t.leader.name
        result.append({
            "id": t.id,
            "name": t.name,
            "leader_id": t.leader_id,
            "leader_name": leader_name
        })
    return result

@app.get("/api/admin/eligible-leaders")
async def get_eligible_leaders(request: Request, db: Session = Depends(get_db)):
    require_role(request, "admin")
    users = db.query(User).filter(User.role == "disaster").all()
    return [{"id": u.id, "name": u.name, "emp_id": u.employee_id} for u in users]

@app.post("/api/admin/teams/{team_id}/assign-leader")
async def assign_team_leader(team_id: int, request: Request, db: Session = Depends(get_db)):
    require_role(request, "admin")
    data = await request.json()
    user_id = data.get("user_id")
    
    team = db.query(TeamCategory).filter(TeamCategory.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    
    # Check if user target is valid or null (to unassign)
    if user_id:
        user = db.query(User).filter(User.id == user_id, User.role == "disaster").first()
        if not user:
             raise HTTPException(status_code=400, detail="User target tidak valid atau bukan anggota Tim KTD")
        
    team.leader_id = user_id
    db.commit()
    return {"status": "success"}

@app.get("/disaster/dashboard", response_class=HTMLResponse)
async def disaster_dashboard(request: Request, db: Session = Depends(get_db)):
    user_session = require_role(request, "disaster")
    user = db.query(User).filter(User.employee_id == user_session["username"]).first()
    
    event = db.query(EmergencyEvent).filter(EmergencyEvent.is_active == True).order_by(EmergencyEvent.id.desc()).first()
    
    return templates.TemplateResponse("disaster_dashboard.html", {
        "request": request, 
        "user": user, 
        "event": event
    })

@app.get("/disaster/preventive", response_class=HTMLResponse)
async def preventive_dashboard(request: Request, db: Session = Depends(get_db)):
    user_session = require_role(request, "disaster")
    user = db.query(User).filter(User.employee_id == user_session["username"]).first()
    
    # We pass the same event info just in case
    event = db.query(EmergencyEvent).filter(EmergencyEvent.is_active == True).order_by(EmergencyEvent.id.desc()).first()
    
    return templates.TemplateResponse("preventive_dashboard.html", {
        "request": request, 
        "user": user, 
        "event": event
    })

@app.get("/monitoring", response_class=HTMLResponse)
async def monitoring_page(request: Request, db: Session = Depends(get_db)):
    user_session = get_current_user_from_session(request)
    if not user_session:
        return RedirectResponse(url="/login")
    
    user = db.query(User).filter(User.employee_id == user_session["username"]).first()
    
    return templates.TemplateResponse("monitoring.html", {
        "request": request, 
        "user": user
    })

# ─── Preventive Checklist API ────────────────────────────────────────────────
@app.get("/api/tasks/preventive")
async def get_preventive_tasks(request: Request, db: Session = Depends(get_db)):
    user_session = get_current_user_from_session(request)
    if not user_session:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    user = db.query(User).filter(User.employee_id == user_session["username"]).first()
    if not user or not user.team_category_id:
        return {"tasks": []}
    
    tasks = db.query(PreventiveTask).filter(PreventiveTask.team_category_id == user.team_category_id).all()
    
    # Get this month's reports for these tasks
    month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    result = []
    for t in tasks:
        report = db.query(PreventiveReport).filter(
            PreventiveReport.task_id == t.id,
            PreventiveReport.timestamp >= month_start
        ).first()
        
        result.append({
            "id": t.id,
            "title": t.title,
            "is_completed": report is not None,
            "photo_path": report.photo_path if report else None,
            "completed_at": report.timestamp.strftime("%d %b %Y, %H:%M") if report else None
        })
    
    return {"tasks": result}

@app.post("/api/tasks/preventive/{task_id}/report")
async def report_preventive_task(
    request: Request,
    task_id: int,
    photo: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    user_session = get_current_user_from_session(request)
    if not user_session:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    user = db.query(User).filter(User.username == user_session["username"]).first()
    
    # Convert photo to base64
    contents = await photo.read()
    base64_photo = f"data:image/jpeg;base64,{base64.b64encode(contents).decode()}"
    
    new_report = PreventiveReport(
        task_id=task_id,
        user_id=user.id,
        photo_path=base64_photo
    )
    db.add(new_report)
    db.commit()
    
    return {"status": "success"}

@app.post("/admin/settings")
async def add_setting(request: Request, condition: str = Form(...), db: Session = Depends(get_db)):
    require_role(request, "admin")
    condition = condition.lower().strip()
    existing = db.query(NotificationSetting).filter(NotificationSetting.condition == condition).first()
    if not existing:
        new_setting = NotificationSetting(condition=condition, is_active=True)
        db.add(new_setting)
        db.commit()
    return RedirectResponse(url="/admin/dashboard", status_code=303)

@app.post("/admin/settings/{setting_id}/toggle")
async def toggle_setting(request: Request, setting_id: int, db: Session = Depends(get_db)):
    require_role(request, "admin")
    setting = db.query(NotificationSetting).filter(NotificationSetting.id == setting_id).first()
    if setting:
        setting.is_active = not setting.is_active
        db.commit()
    return RedirectResponse(url="/admin/dashboard", status_code=303)

@app.post("/admin/settings/{setting_id}/delete")
async def delete_setting(request: Request, setting_id: int, db: Session = Depends(get_db)):
    require_role(request, "admin")
    setting = db.query(NotificationSetting).filter(NotificationSetting.id == setting_id).first()
    if setting:
        db.delete(setting)
        db.commit()
    return RedirectResponse(url="/admin/dashboard", status_code=303)

@app.post("/admin/tasks/{task_id}/delete-photo")
async def admin_delete_task_photo(request: Request, task_id: int, db: Session = Depends(get_db)):
    require_role(request, "admin")
    task = db.query(EmergencyTask).filter(EmergencyTask.id == task_id).first()
    if task:
        task.photo_path = None
        task.is_completed = False
        task.completed_at = None
        task.completed_by = None
        # Also clear report fields
        task.report_content = None
        task.actions_taken = None
        task.planned_actions = None
        task.monitoring_notes = None
        db.commit()
    return RedirectResponse(url="/admin/dashboard#photos-section", status_code=303)

@app.post("/admin/users/add")
async def admin_add_user(
    request: Request,
    employee_id: str = Form(...),
    password: str = Form(...),
    name: str = Form(...),
    role: str = Form(...),
    team_category_id: int = Form(None),
    db: Session = Depends(get_db)
):
    require_role(request, "admin")
    existing = db.query(User).filter(User.employee_id == employee_id).first()
    if existing:
        return RedirectResponse(url="/admin/dashboard#users-section", status_code=303)
    
    new_user = User(
        employee_id=employee_id, 
        username=employee_id, 
        password=password, 
        name=name, 
        role=role,
        team_category_id=team_category_id if role == "disaster" else None
    )
    db.add(new_user)
    db.commit()
    return RedirectResponse(url="/admin/dashboard#users-section", status_code=303)

@app.post("/admin/users/{user_id}/update-role")
async def admin_update_user_role(
    request: Request,
    user_id: int,
    role: str = Form(...),
    db: Session = Depends(get_db)
):
    require_role(request, "admin")
    target_user = db.query(User).filter(User.id == user_id).first()
    if target_user:
        target_user.role = role
        db.commit()
    return RedirectResponse(url="/admin/dashboard#users-section", status_code=303)

@app.post("/admin/users/{user_id}/delete")
async def admin_delete_user(request: Request, user_id: int, db: Session = Depends(get_db)):
    require_role(request, "admin")
    target_user = db.query(User).filter(User.id == user_id).first()
    if target_user and target_user.role != "admin":
        # 1. Clear leadership before deleting
        db.query(TeamCategory).filter(TeamCategory.leader_id == user_id).update({TeamCategory.leader_id: None})
        
        # 2. Nullify references in Emergency Tasks and Reports
        db.query(EmergencyTask).filter(EmergencyTask.completed_by == user_id).update({EmergencyTask.completed_by: None})
        db.query(AdHocReport).filter(AdHocReport.user_id == user_id).update({AdHocReport.user_id: None})
        db.query(PreventiveReport).filter(PreventiveReport.user_id == user_id).update({PreventiveReport.user_id: None})
        
        db.delete(target_user)
        db.commit()
    return RedirectResponse(url="/admin/dashboard#users-section", status_code=303)

@app.post("/admin/categories/add")
async def admin_add_category(request: Request, name: str = Form(...), db: Session = Depends(get_db)):
    require_role(request, "admin")
    existing = db.query(TeamCategory).filter(TeamCategory.name == name).first()
    if not existing:
        new_cat = TeamCategory(name=name)
        db.add(new_cat)
        db.commit()
    return RedirectResponse(url="/admin/dashboard#categories-section", status_code=303)

@app.post("/admin/categories/{cat_id}/delete")
async def admin_delete_category(request: Request, cat_id: int, db: Session = Depends(get_db)):
    require_role(request, "admin")
    cat = db.query(TeamCategory).filter(TeamCategory.id == cat_id).first()
    if cat:
        # 1. Nullify references in users
        db.query(User).filter(User.team_category_id == cat_id).update({User.team_category_id: None})
        
        # 2. Delete or nullify referencing tasks/templates
        db.query(PreventiveTask).filter(PreventiveTask.team_category_id == cat_id).delete()
        db.query(EmergencyTask).filter(EmergencyTask.team_category_id == cat_id).update({EmergencyTask.team_category_id: None})
        db.query(TaskTemplate).filter(TaskTemplate.team_category_id == cat_id).update({TaskTemplate.team_category_id: None})
        
        db.delete(cat)
        db.commit()
    return RedirectResponse(url="/admin/dashboard#categories-section", status_code=303)

# ─── Cron: Weather Monitor (replaces background worker) ─────────────────────
# Called by cron-job.org or Vercel Cron every hour
@app.get("/api/cron/weather-check")
@app.post("/api/cron/weather-check")
async def cron_weather_check(request: Request):
    # Verify cron secret in production
    if CRON_SECRET:
        auth_header = request.headers.get("authorization", "")
        query_secret = request.query_params.get("secret", "")
        if auth_header != f"Bearer {CRON_SECRET}" and query_secret != CRON_SECRET:
            raise HTTPException(status_code=401, detail="Unauthorized")

    db = SessionLocal()
    results = {"checked": [], "triggered": [], "notified": 0}
    
    try:
        active_settings = db.query(NotificationSetting).filter(NotificationSetting.is_active == True).all()
        conditions_to_check = [s.condition for s in active_settings]
        
        if not conditions_to_check:
            active_event = db.query(EmergencyEvent).filter(EmergencyEvent.is_active == True).first()
            if active_event:
                active_event.is_active = False
                active_event.resolved_at = datetime.utcnow()
                db.commit()
            return {"status": "ok", "message": "No active conditions to check, resolved active events", **results}
            
        async with httpx.AsyncClient() as client:
            response = await client.get(BMKG_API_URL)
            if response.status_code != 200:
                return {"status": "error", "message": f"BMKG API returned {response.status_code}"}
            
            data = response.json()
            days = data.get("data", [{}])[0].get("cuaca", [])
            
            any_triggered = False

            for condition in conditions_to_check:
                results["checked"].append(condition)
                streak = 0
                should_notify = False
                
                for day_forecast in days:
                    has_condition = any(condition in f.get("weather_desc", "").lower() for f in day_forecast)
                    if has_condition:
                        streak += 1
                        if streak >= 3:
                            should_notify = True
                            any_triggered = True
                            break
                    else:
                        streak = 0
                
                if should_notify:
                    results["triggered"].append(condition)
                    
                    # Create emergency event if none active
                    event_level = "Waspada"
                    active_event = db.query(EmergencyEvent).filter(EmergencyEvent.is_active == True).first()
                    
                    if not active_event:
                        new_e = EmergencyEvent(status_level=event_level)
                        db.add(new_e)
                        db.commit()
                        db.refresh(new_e)
                        
                        t_templates = db.query(TaskTemplate).filter(TaskTemplate.status_level == event_level).all()
                        for t_temp in t_templates:
                            t_task = EmergencyTask(
                                event_id=new_e.id, 
                                template_id=t_temp.id, 
                                team_category_id=t_temp.team_category_id,
                                title=t_temp.title
                            )
                            db.add(t_task)
                        db.commit()

                    # Send push notifications
                    subs = db.query(PushSubscription).all()
                    if subs:
                        msg = f"Kondisi {condition} diprediksi terjadi 3 hari ke depan. Tetap waspada!"
                        sent_count = 0
                        for sub in subs:
                            try:
                                role_text = "Tugas Siaga Bencana!" if sub.user_role == "disaster" else "Waspada Cuaca!"
                                webpush(
                                    subscription_info=sub.to_dict(),
                                    data=json.dumps({"title": role_text, "body": msg}),
                                    vapid_private_key=VAPID_PRIVATE_KEY,
                                    vapid_claims=VAPID_CLAIMS
                                )
                                sent_count += 1
                            except WebPushException as ex:
                                if ex.response and ex.response.status_code == 410:
                                    db.delete(sub)
                        
                        results["notified"] = sent_count
                        log = ActivityLog(message=f"Terkirim ke {sent_count} perangkat", condition_matched=condition)
                        db.add(log)
                        db.commit()
            
            if not any_triggered:
                active_event = db.query(EmergencyEvent).filter(EmergencyEvent.is_active == True).first()
                if active_event:
                    active_event.is_active = False
                    active_event.resolved_at = datetime.utcnow()
                    db.commit()
                    results["message"] = "Weather cleared. Resolved active emergency events."
                    
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        db.close()
    
    return {"status": "ok", **results}

# ─── Local Dev Server ────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8989, reload=True)
