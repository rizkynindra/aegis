import httpx
import asyncio

async def test():
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8989") as client:
        # Login
        r = await client.post("/login", data={"username": "disaster", "password": "123"})
        print("Login:", r.status_code)
        
        # Trigger
        await client.post("/api/events/", data={"status_level": "Waspada"})
        
        # Fetch 
        r2 = await client.get("/api/events/active/tasks")
        print("Fetch Tasks:", r2.status_code)
        
        data = r2.json()
        print(data)
        
        if not data.get("tasks"):
            print("No tasks found!")
            return
            
        task_id = data["tasks"][0]["id"]
        
        # Upload
        files = {'photo': ('test.jpg', b'fakeimagebytes', 'image/jpeg')}
        r3 = await client.post(f"/api/tasks/{task_id}/upload", files=files)
        print("Upload result:", r3.status_code)
        print("Upload error:", r3.text)

asyncio.run(test())
