import http.client
import json

IP = "10.0.1.182"
code = "YWRtaW46U2ltcHNvbiE3MTI="

payload = json.dumps({
    "serial": {
        "enabled": 1,
        "baudrate": 19200,
        "protocol": "RS-232"
    },
    "tcp": {
        "enabled": 1,
        "port": 6000
    },
    "udp": {
        "enabled": 1,
        "port": 6001
    }
})

headers = {
    "Authorization": f"Basic {code}",
    "Content-Type": "application/json"
}

# PUT
conn = http.client.HTTPConnection(IP)
conn.request("PUT", "/api/supcon.json", payload, headers)
res = conn.getresponse()
data = res.read()

print("PUT Status :", res.status)
print("PUT Body   :", data.decode("utf-8"))

conn.close()

# GET verification
conn = http.client.HTTPConnection(IP)
conn.request("GET", "/api/supcon.json", "", {
    "Authorization": f"Basic {code}"
})
res = conn.getresponse()
data = res.read()

print("GET Status :", res.status)
print("GET Body   :", data.decode("utf-8"))

conn.close()