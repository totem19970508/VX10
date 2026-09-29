import socket
import requests


class VX10:
    def __init__(self, ip, username="admin", password="", timeout=3):
        self.ip = ip
        self.username = username
        self.password = password
        self.timeout = timeout
        self.base_url = f"http://{ip}"
        self.session = requests.Session()

    # -------------------------
    # REST API
    # -------------------------
    def login(self):
        r = self.session.post(
            f"{self.base_url}/api/login",
            json={
                "username": self.username,
                "password": self.password
            },
            timeout=self.timeout
        )
        r.raise_for_status()
        return r

    def set_brightness_rest(self, value):
        value = max(0, min(100, int(value)))

        r = self.session.put(
            f"{self.base_url}/api/brightness",
            json={"brightness": value},
            timeout=self.timeout
        )
        r.raise_for_status()
        return r

    # -------------------------
    # Central Control Protocol
    # -------------------------
    @staticmethod
    def _hex(data):
        return data.hex(" ").upper()

    @staticmethod
    def _calc_lrc(data):
        x = 0
        for b in data:
            x ^= b
        return x

    def _build_frame(self, command, flag):
        return bytes([0x02, flag]) + command.encode("ascii") + bytes([0x03, 0x32])

    def _parse_get_brightness(self, rx):
        print("RX:", self._hex(rx))

        if len(rx) >= 10 and rx[2:5] == b"399":
            value = int(rx[5:8].decode("ascii"))
            percent = round(value * 100 / 255, 1)
            return value, percent

        return None, None

    def get_brightness_tcp(self, port=6000):
        tx = self._build_frame("399", 0x11)
        print("TCP TX:", self._hex(tx))

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(self.timeout)
            s.connect((self.ip, port))
            s.sendall(tx)
            rx = s.recv(1024)

        return self._parse_get_brightness(rx)

    def get_brightness_udp(self, port=6001):
        tx = self._build_frame("399", 0x12)
        print("UDP TX:", self._hex(tx))

        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(self.timeout)
            s.sendto(tx, (self.ip, port))
            rx, addr = s.recvfrom(1024)

        return self._parse_get_brightness(rx)

    def set_brightness_tcp(self, value_0_255, port=6000):
        value_0_255 = max(0, min(255, int(value_0_255)))
        tx = self._build_frame(f"303{value_0_255:03d}", 0x11)

        print("TCP TX:", self._hex(tx))

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(self.timeout)
            s.connect((self.ip, port))
            s.sendall(tx)
            rx = s.recv(1024)

        print("TCP RX:", self._hex(rx))
        return rx

    def set_brightness_udp(self, value_0_255, port=6001):
        value_0_255 = max(0, min(255, int(value_0_255)))
        tx = self._build_frame(f"303{value_0_255:03d}", 0x12)

        print("UDP TX:", self._hex(tx))

        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(self.timeout)
            s.sendto(tx, (self.ip, port))

            try:
                rx, addr = s.recvfrom(1024)
                print("UDP RX:", self._hex(rx))
                return rx
            except socket.timeout:
                print("UDP no response")
                return None