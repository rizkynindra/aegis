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
from datetime import datetime
from pywebpush import webpush, WebPushException

from database import engine, Base, get_db, SessionLocal
from database import User, NotificationSetting, PushSubscription, ActivityLog, TaskTemplate, EmergencyEvent, EmergencyTask

app = FastAPI()

# Create tables
Base.metadata.create_all(bind=engine)

# ─── Environment Variables ───────────────────────────────────────────────────
VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY", "BKwh-BREF31n5SfXUi7Te1v7iPxBIP2zgGL-Fcgw5OPG_nQa2xBswX2iO5SaiOk-su8b8hp_myMCDBFF3fL1_kU")
VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY", "nBEW3RwL9Z7NHFZQ0KrfAbgA9Uh6ONa9FavzG2CVbrk")
VAPID_CLAIMS = {"sub": os.environ.get("VAPID_CONTACT", "mailto:admin@example.com")}
SESSION_SECRET = os.environ.get("SESSION_SECRET", "super-secret-key-change-in-production")
BMKG_API_URL = os.environ.get("BMKG_API_URL", "https://api.bmkg.go.id/publik/prakiraan-cuaca?adm4=51.71.04.1007")
CRON_SECRET = os.environ.get("CRON_SECRET", "")  # Protect cron endpoint in production

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
        # Seed default users
        if not db.query(User).first():
            default_users = [
                User(username="admin", password="123", role="admin", name="Administrator"),
                User(username="user", password="123", role="normal", name="Normal User"),
                User(username="disaster", password="123", role="disaster", name="Disaster Team")
            ]
            db.add_all(default_users)
            db.commit()
        
        # Seed default setting if empty
        if not db.query(NotificationSetting).first():
            db.add(NotificationSetting(condition="hujan ringan", is_active=True))
            db.commit()
        
        # Seed default templates if empty
        if not db.query(TaskTemplate).first():
            task_templates = [
                TaskTemplate(status_level="Waspada", title="Cek Dokumen Penting", description="Pindahkan dokumen penting ke tempat yang lebih tinggi.", requires_photo=True),
                TaskTemplate(status_level="Waspada", title="Cek Pompa Air", description="Pastikan pompa air berfungsi dengan baik.", requires_photo=True),
                TaskTemplate(status_level="Siaga", title="Matikan Listrik Lantai 1", description="Pastikan panel listrik utama di lantai 1 telah dimatikan.", requires_photo=True),
                TaskTemplate(status_level="Darurat", title="Evakuasi", description="Pastikan semua karyawan telah dievakuasi.", requires_photo=True)
            ]
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
    user = db.query(User).filter(User.username == username).first()
    if user and user.password == password:
        request.session["user"] = {"username": user.username, "role": user.role, "name": user.name}
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
            title=template.title
        )
        db.add(task)
    db.commit()
    return {"status": "success", "event_id": event.id, "tasks_created": len(tmpl)}

@app.get("/api/events/active/tasks")
async def get_active_event_tasks(db: Session = Depends(get_db)):
    event = db.query(EmergencyEvent).filter(EmergencyEvent.is_active == True).order_by(EmergencyEvent.id.desc()).first()
    if not event:
        return {"tasks": [], "event": None}
    
    tasks = db.query(EmergencyTask).filter(EmergencyTask.event_id == event.id).all()
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
    user = require_role(request, "admin")
    
    settings = db.query(NotificationSetting).order_by(NotificationSetting.id.desc()).all()
    logs = db.query(ActivityLog).order_by(ActivityLog.timestamp.desc()).limit(10).all()
    
    recent_tasks = db.query(EmergencyTask).filter(
        EmergencyTask.photo_path.isnot(None)
    ).order_by(EmergencyTask.completed_at.desc()).limit(20).all()
    
    users = db.query(User).order_by(User.id).all()
    
    return templates.TemplateResponse("admin_dashboard.html", {
        "request": request, 
        "user": user, 
        "settings": settings,
        "logs": logs,
        "recent_tasks": recent_tasks,
        "users": users
    })

@app.get("/disaster/dashboard", response_class=HTMLResponse)
async def disaster_dashboard(request: Request, db: Session = Depends(get_db)):
    user = require_role(request, "disaster")
    
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
    username: str = Form(...),
    password: str = Form(...),
    name: str = Form(...),
    role: str = Form(...),
    db: Session = Depends(get_db)
):
    require_role(request, "admin")
    existing = db.query(User).filter(User.username == username).first()
    if existing:
        return RedirectResponse(url="/admin/dashboard#users-section", status_code=303)
    new_user = User(username=username, password=password, name=name, role=role)
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
                            t_task = EmergencyTask(event_id=new_e.id, template_id=t_temp.id, title=t_temp.title)
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
