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
from database import User, TeamCategory, NotificationSetting, PushSubscription, ActivityLog, TaskTemplate, EmergencyEvent, EmergencyTask

app = FastAPI()

# Create tables
Base.metadata.create_all(bind=engine)

# ─── Environment Variables ───────────────────────────────────────────────────
VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY")
VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY")
VAPID_CLAIMS = {"sub": f"mailto:{os.environ.get('VAPID_EMAIL', 'admin@aegis.corp')}"}
SESSION_SECRET = os.environ.get("SESSION_SECRET", "super-secret-aegis-key")
BMKG_API_URL = os.environ.get("BMKG_API_URL", "https://data.bmkg.go.id/DataMKG/MEWS/DigitalForecast/DigitalForecast-Bali.xml")
CRON_SECRET = os.environ.get("CRON_SECRET") 

# ─── Middleware ──────────────────────────────────────────────────────────────
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET)

# ─── Templates & Static ─────────────────────────────────────────────────────
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# ─── Helpers ─────────────────────────────────────────────────────────────────
def get_current_user_from_session(request: Request):
    return request.session.get("user")

def require_role(request: Request, role: str):
    user = get_current_user_from_session(request)
    if not user or user.get("role") != role:
        raise HTTPException(status_code=403, detail="Forbidden")
    return user

# ─── Startup: Seed DB ────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup_event():
    db = SessionLocal()
    try:
        # Seed categories if empty
        if not db.query(TeamCategory).first():
            categories = [
                "Pimpinan Pengendali (Kacab)",
                "Koordinator Penanggulangan & Pengamanan (Kabeng)",
                "Koordinator Evakuasi & Penyelamatan",
                "Tim Komunikasi",
                "Tim Pelaksana / Fire & Floods",
                "Tim Keamanan (Security)",
                "Tim Listrik & Sarana",
                "Tim P3K & P3GD",
                "Tim Karyawan & Logistik",
                "Tim Barang Inventaris & Dokumen",
                "Tim Kendaraan"
            ]
            db.add_all([TeamCategory(name=cat) for cat in categories])
            db.commit()

        # Seed default users & Migration
        if not db.query(User).first():
            default_users = [
                User(employee_id="admin", username="admin", password="123", role="admin", name="Administrator"),
                User(employee_id="user", username="user", password="123", role="normal", name="Normal User"),
                User(employee_id="disaster", username="disaster", password="123", role="disaster", name="Disaster Team")
            ]
            db.add_all(default_users)
            db.commit()
        else:
            # Migration: Ensure all users have employee_id
            users_to_migrate = db.query(User).filter(User.employee_id == None).all()
            if users_to_migrate:
                for u in users_to_migrate:
                    u.employee_id = u.username
                db.commit()
        
        # Seed default setting if empty
        if not db.query(NotificationSetting).first():
            db.add(NotificationSetting(condition="hujan ringan", is_active=True))
            db.commit()
        
        # Seed specialized tasks for each category if empty
        if not db.query(TaskTemplate).first():
            category_tasks = {
                "Pimpinan Pengendali (Kacab)": "Monitoring Situasi & Pengambilan Keputusan",
                "Koordinator Penanggulangan & Pengamanan (Kabeng)": "Koordinasi dan Pengerahan Tim",
                "Koordinator Evakuasi & Penyelamatan": "Pengawasan Jalur Evakuasi dan Titik Kumpul",
                "Tim Komunikasi": "Menghubungi Instansi Terkait (Damkar, Polisi, PLN, RS)",
                "Tim Pelaksana / Fire & Floods": "Pengecekan Kesiapan APAR/Hydrant & Tanggul",
                "Tim Keamanan (Security)": "Pengamanan Area dan Aset Kantor",
                "Tim Listrik & Sarana": "Pemutusan Arus Listrik Utama (Panel)",
                "Tim P3K & P3GD": "Penyiapan Posko Medis dan Alat P3K",
                "Tim Karyawan & Logistik": "Penyiapan Bahan Makanan dan Konsumsi Darurat",
                "Tim Barang Inventaris & Dokumen": "Penyelamatan Dokumen Penting dan Backup Data",
                "Tim Kendaraan": "Pemindahan Kendaraan ke Area Aman"
            }
            
            # Fetch categories to get IDs
            all_cats = db.query(TeamCategory).all()
            cat_map = {c.name.split(' (')[0].split(' / ')[-1] if ' / ' in c.name else c.name.split(' (')[0]: c.id for c in all_cats}
            # Simplified map for robustness
            cat_map = {c.name: c.id for c in all_cats}

            task_templates = []
            for cat_name, task_title in category_tasks.items():
                cat_id = cat_map.get(cat_name)
                task_templates.append(TaskTemplate(
                    status_level="Waspada", 
                    team_category_id=cat_id, 
                    title=task_title, 
                    description=f"Instruksi khusus untuk {cat_name} berdasarkan SOP Job Desk.",
                    requires_photo=True
                ))
            
            # Also add for other levels for completeness
            for cat_name, task_title in category_tasks.items():
                cat_id = cat_map.get(cat_name)
                task_templates.append(TaskTemplate(status_level="Siaga", team_category_id=cat_id, title=f"SIAGA: {task_title}"))
                task_templates.append(TaskTemplate(status_level="Darurat", team_category_id=cat_id, title=f"DARURAT: {task_title}"))

            db.add_all(task_templates)
            db.commit()
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

@app.post("/api/notify-all")
async def notify_all(title: str = Form(...), message: str = Form(...), db: Session = Depends(get_db)):
    subs = db.query(PushSubscription).all()
    results = []
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
            results.append("success")
        except WebPushException as ex:
            results.append(f"failed: {ex}")
            if ex.response and ex.response.status_code == 410:
                db.delete(sub)
                db.commit()
    return {"sent": sent, "results": results}

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
    
    db_user = db.query(User).filter(User.username == user["username"]).first()
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
        # Before deleting, nullify references in users
        db.query(User).filter(User.team_category_id == cat_id).update({User.team_category_id: None})
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
