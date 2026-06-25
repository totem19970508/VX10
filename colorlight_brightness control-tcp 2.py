import socket

X16E_IP = "192.168.1.192"   # change to your X16E IP
PORT = 6000

def build_brightness_cmd(value):
    value = max(0, min(255, int(value)))
    level = f"{value:03d}"

    frame = [
        0x02,
        0x11,              # TCP flag
        ord("3"), ord("0"), ord("3"),
        ord(level[0]), ord(level[1]), ord(level[2]),
        0x03,
        0x32               # fixed LRC from Colorlight PDF
    ]

    return bytes(frame)

def send_brightness(value):
    cmd = build_brightness_cmd(value)

    print("TX:", " ".join(f"{b:02X}" for b in cmd))

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(3)
        s.connect((X16E_IP, PORT))
        s.sendall(cmd)

        try:
            resp = s.recv(1024)
            print("RX:", " ".join(f"{b:02X}" for b in resp))
        except socket.timeout:
            print("No response")

send_brightness(100)