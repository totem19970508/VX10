import base64

username = "admin"
password = "Simpson!712"

credentials = f"{username}:{password}"
encoded = base64.b64encode(credentials.encode("utf-8")).decode("utf-8")

print(encoded)