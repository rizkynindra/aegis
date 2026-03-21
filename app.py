from fastapi import FastAPI, Request, Form, BackgroundTasks, Depends, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session
import os
import json
import httpx
import asyncio
import uvicorn
from pywebpush import webpush, WebPushException

from database import engine, Base, get_db, SessionLocal
from database import User, NotificationSetting, PushSubscription, ActivityLog

app = FastAPI()

# Create tables
Base.metadata.create_all(bind=engine)

# VAPID Keys
VAPID_PUBLIC_KEY = "BKwh-BREF31n5SfXUi7Te1v7iPxBIP2zgGL-Fcgw5OPG_nQa2xBswX2iO5SaiOk-su8b8hp_myMCDBFF3fL1_kU"
VAPID_PRIVATE_KEY = "nBEW3RwL9Z7NHFZQ0KrfAbgA9Uh6ONa9FavzG2CVbrk"
VAPID_CLAIMS = {"sub": "mailto:admin@example.com"}

# Add Session Middleware
app.add_middleware(SessionMiddleware, secret_key="super-secret-key")

# BMKG API URL for Denpasar Utara
API_URL = "https://api.bmkg.go.id/publik/prakiraan-cuaca?adm4=51.71.04.1007"

# Setup templates
templates = Jinja2Templates(directory="templates")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

def get_current_user_from_session(request: Request):
    return request.session.get("user")

def require_role(request: Request, role: str):
    user = get_current_user_from_session(request)
    if not user or user.get("role") != role:
        raise HTTPException(status_code=403, detail="Forbidden")
    return user

@app.on_event("startup")
async def startup_event():
    db = SessionLocal()
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
    
    db.close()
    asyncio.create_task(monitor_weather_and_notify())

@app.get("/", response_class=HTMLResponse)
async def read_item(request: Request):
    user = get_current_user_from_session(request)
    if not user:
        return RedirectResponse(url="/login")
    if user.get("role") == "admin":
        return RedirectResponse(url="/admin/dashboard", status_code=303)
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
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request, "error": "Username atau password salah"})

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login")

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
    
    # Check if exists
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
        # Update role if changed
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
            # Optional: Delete expired subscriptions
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
            response = await client.get(API_URL)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}

@app.get("/api/active-conditions")
async def get_active_conditions(db: Session = Depends(get_db)):
    active_settings = db.query(NotificationSetting).filter(NotificationSetting.is_active == True).all()
    return {"conditions": [s.condition for s in active_settings]}

# Admin Dashboard Routes
@app.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request, db: Session = Depends(get_db)):
    user = require_role(request, "admin")
    
    settings = db.query(NotificationSetting).order_by(NotificationSetting.id.desc()).all()
    logs = db.query(ActivityLog).order_by(ActivityLog.timestamp.desc()).limit(10).all()
    
    return templates.TemplateResponse("admin_dashboard.html", {
        "request": request, 
        "user": user, 
        "settings": settings,
        "logs": logs
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


# Background Weather Monitor
async def monitor_weather_and_notify():
    while True:
        try:
            db = SessionLocal()
            active_settings = db.query(NotificationSetting).filter(NotificationSetting.is_active == True).all()
            conditions_to_check = [s.condition for s in active_settings]
            
            if not conditions_to_check:
                db.close()
                await asyncio.sleep(3600)
                continue
                
            async with httpx.AsyncClient() as client:
                response = await client.get(API_URL)
                if response.status_code == 200:
                    data = response.json()
                    days = data.get("data", [{}])[0].get("cuaca", [])
                    
                    for condition in conditions_to_check:
                        streak = 0
                        should_notify = False
                        
                        for day_forecast in days:
                            # Check if any segment of the day matches the condition
                            has_condition = any(condition in f.get("weather_desc", "").lower() for f in day_forecast)
                            
                            if has_condition:
                                streak += 1
                                if streak >= 3:
                                    should_notify = True
                                    break
                            else:
                                streak = 0
                        
                        if should_notify:
                            subs = db.query(PushSubscription).all()
                            if subs:
                                print(f"Background: '{condition}' detected for 3 days. Notifying {len(subs)} users.")
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
                                        print(f"Failed to send push: {ex}")
                                        if ex.response and ex.response.status_code == 410:
                                            db.delete(sub)
                                
                                # Log the Activity
                                log = ActivityLog(message=f"Terkirim ke {sent_count} perangkat", condition_matched=condition)
                                db.add(log)
                                db.commit()
            
            db.close()
        except Exception as e:
            print(f"Monitor error: {e}")
        
        await asyncio.sleep(3600) # Check every hour

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8989, reload=True)
