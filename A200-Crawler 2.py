import re
import requests
from urllib.parse import urljoin

IP = "10.0.1.182"
USERNAME = "admin"
PASSWORD = "Simpson!712"

BASE = f"http://{IP}"
s = requests.Session()


def show(title):
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


# 1. Login
r = s.post(
    f"{BASE}/api/login",
    json={"username": USERNAME, "password": PASSWORD},
    timeout=5
)

print("Login:", r.status_code)
print("Cookies:", s.cookies.get_dict())


# 2. Download main page
r = s.get(BASE, timeout=5)
html = r.text

show("HTML JS FILES")

js_files = sorted(set(re.findall(r'src="([^"]+\.js)"', html)))
for js in js_files:
    print(js)


# 3. Download JS and extract API paths
api_paths = set()

patterns = [
    r'["\'](/api/[^"\']+)["\']',
    r'["\'](api/[^"\']+)["\']',
    r'["\'](/[^"\']+\.json)["\']',
]

show("EXTRACTING API PATHS")

for js in js_files:
    js_url = urljoin(BASE + "/", js)
    print("Downloading:", js_url)

    try:
        jr = s.get(js_url, timeout=10)
        text = jr.text

        for pat in patterns:
            for m in re.findall(pat, text):
                path = m
                if not path.startswith("/"):
                    path = "/" + path
                api_paths.add(path)

    except Exception as e:
        print("ERROR:", e)


# Add known/manual paths
api_paths.update([
    "/api/login",
    "/api/brightness",
    "/api/brightnessandcolortemp.json",
    "/brightnessandcolortemp.json",
    "/api/supcon.json",
    "/api/supcon",
    "/api/display",
    "/api/status",
    "/api/setting",
    "/api/settings",
    "/api/device",
    "/api/info",
    "/api/program",
])


show("FOUND API PATHS")
for p in sorted(api_paths):
    print(p)


# 4. Test GET on all paths
show("TEST GET ENDPOINTS")

for path in sorted(api_paths):
    try:
        r = s.get(urljoin(BASE, path), timeout=5)

        print(f"{path:45} status={r.status_code:<4} len={len(r.text):<5} type={r.headers.get('Content-Type')}")

        if len(r.text) > 0:
            print("  body:", repr(r.text[:300]))

    except Exception as e:
        print(f"{path:45} ERROR {e}")


# 5. Test selected likely brightness readbacks
show("LIKELY BRIGHTNESS READBACKS")

for path in sorted(api_paths):
    low = path.lower()
    if "bright" in low or "display" in low or "color" in low:
        try:
            r = s.get(urljoin(BASE, path), timeout=5)
            print("\nGET", path)
            print("Status:", r.status_code)
            print("Body:", repr(r.text[:2000]))
        except Exception as e:
            print(path, e)