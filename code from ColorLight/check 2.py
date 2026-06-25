import requests


IP = "10.0.1.182"

code = "YWRtaW46U2ltcHNvbiE3MTI="

payload = {
    "serial": {
        "enabled": 1,
        "baudrate": 19200,
        "protocol": "RS-232"
    },
    "tcp": {
        "enabled": 0,
        "port": 6000
    },
    "udp": {
        "enabled": 0,
        "port": 6001
    }
}

headers = {
    "Authorization": f"Basic {code}",
    "Content-Type": "application/json"
}

r = requests.put(
    f"http://{IP}/api/supcon",
    headers=headers,
    json=payload,
    timeout=5,
)
print("Using requests library:")
print("Status :", r.status_code)
print("Reason :", r.reason)
print("Body   :", repr(r.text))