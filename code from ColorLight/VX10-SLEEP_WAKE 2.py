import socket

IP = "10.0.1.182"

TCP_PORT = 6000
UDP_PORT = 6001

FLAGS = {
    "TCP": 0x11,
    "UDP": 0x12,
}

COMMANDS = {
    "wake": "101",
    "sleep": "102",
    "toggle_sleep_awake": "103",
    "reboot": "104",
    "shutdown": "105",
    "get_status": "199",
}

def build_frame(mode, command):
    frame = bytearray()
    frame.append(0x02)                 # STX
    frame.append(FLAGS[mode])          # FLAG
    frame += command.encode("ascii")   # Command
    frame.append(0x03)                 # ETX
    frame.append(0x32)                 # Fixed host LRC
    return bytes(frame)

def send_tcp(command):
    frame = build_frame("TCP", command)

    print("TX:", frame.hex(" "))

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(2)
        s.connect((IP, TCP_PORT))
        s.sendall(frame)

        try:
            while True:
                data = s.recv(1024)
                if not data:
                    break
                print("RX:", data.hex(" "))
        except socket.timeout:
            pass

def send_udp(command):
    frame = build_frame("UDP", command)

    print("TX:", frame.hex(" "))

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.settimeout(2)
        s.sendto(frame, (IP, UDP_PORT))

        try:
            while True:
                data, _ = s.recvfrom(1024)
                print("RX:", data.hex(" "))
        except socket.timeout:
            pass

def run():
    mode = input("Mode TCP/UDP: ").strip().upper()
    if mode not in ["TCP", "UDP"]:
        print("Invalid mode")
        return

    print("""
1 = Wake up
2 = Sleep
3 = Toggle sleep/awake
4 = Reboot
5 = Shutdown
6 = Get status
""")

    choice = input("Select: ").strip()

    mapping = {
        "1": "wake",
        "2": "sleep",
        "3": "toggle_sleep_awake",
        "4": "reboot",
        "5": "shutdown",
        "6": "get_status",
    }

    if choice not in mapping:
        print("Invalid choice")
        return

    command = COMMANDS[mapping[choice]]

    if mode == "TCP":
        send_tcp(command)
    else:
        send_udp(command)

if __name__ == "__main__":
    run()