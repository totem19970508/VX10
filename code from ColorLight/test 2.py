import requests
from requests.auth import HTTPBasicAuth
import json

# Configuration
IP = "10.0.1.182"
USERNAME = "admin"
PASSWORD = "Simpson!712"

url = f"http://{IP}/api/supcon.json"

try:
    r = requests.get(
        url,
        auth=HTTPBasicAuth(USERNAME, PASSWORD),
        timeout=5
    )

    print("HTTP Status:", r.status_code)
    r.raise_for_status()

    data = r.json()

    print(json.dumps(data, indent=4))

    print("\n------ Summary ------")
    print(f"Serial Enabled : {data['serial']['enabled']}")
    print(f"Baud Rate      : {data['serial']['baudrate']}")
    print(f"Protocol       : {data['serial']['protocol']}")

    print(f"TCP Enabled    : {data['tcp']['enabled']}")
    print(f"TCP Port       : {data['tcp']['port']}")

    print(f"UDP Enabled    : {data['udp']['enabled']}")
    print(f"UDP Port       : {data['udp']['port']}")

except Exception as e:
    print("Error:", e)