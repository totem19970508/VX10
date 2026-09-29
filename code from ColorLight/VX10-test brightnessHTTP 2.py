import socket
import time

HOST = "10.0.1.182"

TCP_PORT = 6000
UDP_PORT = 6001


def build_brightness_cmd(value, protocol):
    """
    value: 0~255
    protocol: RS232, TCP, UDP
    """

    value = max(0, min(255, int(value)))
    protocol = protocol.upper()

    if protocol == "RS232":
        flag = 0x10
    elif protocol == "TCP":
        flag = 0x11
    elif protocol == "UDP":
        flag = 0x12
    else:
        raise ValueError("Protocol must be RS232, TCP, or UDP")

    brightness = f"{value:03d}".encode("ascii")

    frame = bytearray()
    frame.append(0x02)          # STX
    frame.append(flag)          # FLAG
    frame += b"303"             # Brightness command
    frame += brightness         # 000~255
    frame.append(0x03)          # ETX
    frame.append(0x32)          # LRC, based on PDF example

    return bytes(frame)


def send_tcp(value):
    cmd = build_brightness_cmd(value, "TCP")

    print("\n--- TCP TEST ---")
    print("Brightness:", value)
    print("Send Hex  :", cmd.hex(" "))

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)

        sock.connect((HOST, TCP_PORT))
        sock.sendall(cmd)

        try:
            data = sock.recv(1024)
            print("Reply Hex :", data.hex(" "))
        except socket.timeout:
            print("No TCP reply")

        sock.close()

    except Exception as e:
        print("TCP Error:", e)


def send_udp(value):
    cmd = build_brightness_cmd(value, "UDP")

    print("\n--- UDP TEST ---")
    print("Brightness:", value)
    print("Send Hex  :", cmd.hex(" "))

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(3)

        sock.sendto(cmd, (HOST, UDP_PORT))

        try:
            data, addr = sock.recvfrom(1024)
            print("Reply From:", addr)
            print("Reply Hex :", data.hex(" "))
        except socket.timeout:
            print("No UDP reply")

        sock.close()

    except Exception as e:
        print("UDP Error:", e)


def main():
    while True:
        print("\n==============================")
        print("VX10 Brightness Protocol Test")
        print("==============================")
        print("1 = TCP")
        print("2 = UDP")
        print("3 = Both TCP and UDP")
        print("0 = Exit")

        mode = input("Select mode: ").strip()

        if mode == "0":
            break

        value = input("Brightness 0~255: ").strip()

        try:
            value = int(value)
        except ValueError:
            print("Invalid brightness")
            continue

        if mode == "1":
            send_tcp(value)

        elif mode == "2":
            send_udp(value)

        elif mode == "3":
            send_tcp(value)
            time.sleep(1)
            send_udp(value)

        else:
            print("Invalid selection")


if __name__ == "__main__":
    main()