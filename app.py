from fastapi import FastAPI, Request, Form, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
import os
import json
import httpx
import asyncio
import uvicorn
from pywebpush import webpush, WebPushException

app = FastAPI()

# VAPID Keys
VAPID_PUBLIC_KEY = "BKwh-BREF31n5SfXUi7Te1v7iPxBIP2zgGL-Fcgw5OPG_nQa2xBswX2iO5SaiOk-su8b8hp_myMCDBFF3fL1_kU"
VAPID_PRIVATE_KEY = "nBEW3RwL9Z7NHFZQ0KrfAbgA9Uh6ONa9FavzG2CVbrk"
VAPID_CLAIMS = {"sub": "mailto:admin@example.com"}

# In-memory storage for push subscriptions
SUBSCRIPTIONS = []

# Add Session Middleware
app.add_middleware(SessionMiddleware, secret_key="super-secret-key")

# Dummy Users Database
USERS = {
    "user": {"password": "123", "role": "normal", "name": "Normal User"},
    "disaster": {"password": "123", "role": "disaster", "name": "Disaster Team"}
}

# BMKG API URL for Denpasar Utara
API_URL = "https://api.bmkg.go.id/publik/prakiraan-cuaca?adm4=51.71.04.1007"

# Setup templates
templates = Jinja2Templates(directory="templates")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def read_item(request: Request):
    user = request.session.get("user")
    if not user:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse("index.html", {"request": request, "user": user})

@app.get("/login", response_class=HTMLResponse)
async def login_get(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login_post(request: Request, username: str = Form(...), password: str = Form(...)):
    user = USERS.get(username)
    if user and user["password"] == password:
        request.session["user"] = {"username": username, "role": user["role"], "name": user["name"]}
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request, "error": "Username atau password salah"})

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login")

@app.get("/api/user")
async def get_current_user(request: Request):
    user = request.session.get("user")
    if not user:
        return {"error": "Not logged in"}
    return user

@app.get("/api/vapid-public-key")
async def get_vapid_key():
    return {"publicKey": VAPID_PUBLIC_KEY}

@app.post("/api/subscribe")
async def subscribe(request: Request):
    subscription = await request.json()
    # Tag subscription with user role if available
    user = request.session.get("user")
    subscription["user_role"] = user["role"] if user else "guest"
    
    # Store subscription (avoid duplicates)
    if subscription not in SUBSCRIPTIONS:
        SUBSCRIPTIONS.append(subscription)
    return {"status": "success"}

@app.post("/api/notify-all")
async def notify_all(title: str = Form(...), message: str = Form(...)):
    results = []
    for sub in SUBSCRIPTIONS:
        try:
            webpush(
                subscription_info=sub,
                data=json.dumps({"title": title, "body": message}),
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims=VAPID_CLAIMS
            )
            results.append("success")
        except WebPushException as ex:
            results.append(f"failed: {ex}")
    return {"sent": len(SUBSCRIPTIONS), "results": results}

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

# Background Weather Monitor
async def monitor_weather_and_notify():
    while True:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(API_URL)
                if response.status_code == 200:
                    data = response.json()
                    # Check for rain (same logic as JS)
                    days = data.get("data", [{}])[0].get("cuaca", [])
                    rain_streak = 0
                    should_notify = False
                    
                    for day_forecast in days:
                        has_rain = any("hujan ringan" in f.get("weather_desc", "").lower() for f in day_forecast)
                        if has_rain:
                            rain_streak += 1
                            if rain_streak >= 3:
                                should_notify = True
                                break
                        else:
                            rain_streak = 0
                    
                    if should_notify and SUBSCRIPTIONS:
                        print(f"Background: Rain detected for 3 days. Notifying {len(SUBSCRIPTIONS)} users.")
                        for sub in SUBSCRIPTIONS:
                            try:
                                role_text = "Tugas Siaga Bencana!" if sub.get("user_role") == "disaster" else "Waspada Hujan!"
                                msg = "Hujan ringan diprediksi turun 3 hari ke depan. Tetap waspada!"
                                webpush(
                                    subscription_info=sub,
                                    data=json.dumps({"title": role_text, "body": msg}),
                                    vapid_private_key=VAPID_PRIVATE_KEY,
                                    vapid_claims=VAPID_CLAIMS
                                )
                            except Exception as e:
                                print(f"Failed to send push: {e}")
                
        except Exception as e:
            print(f"Monitor error: {e}")
        
        await asyncio.sleep(3600) # Check every hour

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(monitor_weather_and_notify())

if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=8989, reload=True)
