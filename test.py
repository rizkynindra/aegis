import requests

try:
    r = requests.post("http://127.0.0.1:8989/api/events/", data={"status_level": "Waspada"})
    print("Status:", r.status_code)
    print("Response:", r.text)
except Exception as e:
    print("Error:", e)
