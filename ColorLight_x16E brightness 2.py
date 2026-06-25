import serial
import struct
import time
import tkinter as tk
from tkinter import ttk

# --- CONFIG ---
SERIAL_PORT = "COM6"     # change com port as needed
BAUD_RATE = 115200       # ⚠️ try 115200 or 57600 or 19200


# --- BUILD COMMAND ---
def build_brightness_cmd(percent):
    percent = max(0, min(100, percent))

    # convert to float 0~1
    value = percent / 100.0

    # little endian float
    brightness_bytes = struct.pack('<f', value)

    frame = bytearray()

    # fixed header
    frame += bytes([0x21, 0x00, 0x14, 0x00, 0x00, 0x00])

    # sender index (0 = first sender)
    frame += bytes([0x00, 0x00])

    # fixed block
    frame += bytes([
        0xFF,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00
    ])

    # brightness float (little endian)
    frame += brightness_bytes

    return frame


# --- SEND ---
def send_brightness(percent, status_var):
    cmd = build_brightness_cmd(percent)

    print("TX:", " ".join(f"{b:02X}" for b in cmd))

    try:
        with serial.Serial(
            port=SERIAL_PORT,
            baudrate=BAUD_RATE,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=1
        ) as ser:

            ser.write(cmd)
            ser.flush()

            time.sleep(0.1)

        status_var.set(f"Sent {percent}%")

    except Exception as e:
        status_var.set(str(e))


# --- GUI ---
def create_gui():
    root = tk.Tk()
    root.title("X16E Brightness (Serial 0x21)")
    root.geometry("420x220")

    frame = ttk.Frame(root, padding=10)
    frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(frame, text="Brightness (%)").pack()

    brightness = tk.IntVar(value=50)

    value_label = ttk.Label(frame, text="50%", font=("Arial", 18, "bold"))
    value_label.pack(pady=5)

    def on_slide(v):
        val = int(float(v))
        brightness.set(val)
        value_label.config(text=f"{val}%")

    slider = ttk.Scale(
        frame,
        from_=0,
        to=100,
        orient=tk.HORIZONTAL,
        length=320,
        command=on_slide
    )
    slider.set(50)
    slider.pack(pady=10)

    status = tk.StringVar(value="Ready")
    ttk.Label(frame, textvariable=status).pack(pady=5)

    ttk.Button(
        frame,
        text="Send",
        command=lambda: send_brightness(brightness.get(), status)
    ).pack(pady=5)

    root.mainloop()


if __name__ == "__main__":
    create_gui()