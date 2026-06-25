from a200 import A200

a = A200(
    ip="10.0.1.182",
    username="admin",
    password="YOUR_PASSWORD"
)

a.login()

# REST method, confirmed working
a.set_brightness_rest(50)

# Central control read-back test
# value, percent = a.get_brightness_udp(port=6001)
# print(value, percent)