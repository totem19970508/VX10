import http.client
# 404

conn = http.client.HTTPConnection("10.0.1.182")
payload = ''

headers = {
    'Authorization': 'Basic YWRtaW46U2ltcHNvbiE3MTI='
}

conn.request("GET", "/api/supcon.json", payload, headers)

res = conn.getresponse()
data = res.read()

print("HTTP Status :", res.status)
print(data, type(data))
print(data.decode("utf-8"))