import requests

IP = "10.0.1.182"

s = requests.Session()

# login if needed
s.post(
    f"http://{IP}/api/login",
    json={
        "username": "admin",
        "password": "Simpson!712"
    },
    timeout=5
)

r = s.get(f"http://{IP}/api/brightnessandcolortemp.json", timeout=5)

print("Status:", r.status_code)
print("Raw:", r.text)

data = r.json()

brightness = data["brightness"]
color_temp = data["colortemperature"]

print("Current brightness:", brightness)
print("Color temperature:", color_temp)