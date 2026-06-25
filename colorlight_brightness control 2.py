import serial
import time
import tkinter as tk
from tkinter import ttk

# --- CONFIG ---
SERIAL_PORT = "COM6"   # change  COM port
BAUD_RATE = 115200

# --- Build command ---
def build_brightness_cmd(value):
    value = max(0, min(255, int(value)))
    level = f"{value:03d}".encode()   # ASCII bytes

    frame = bytes([
        0x02,          # STX
        0x10,          # RS232 flag
    ]) + b"303" + level + bytes([
        0x03,          # ETX
        0x32           # FIXED LRC
    ])

    return frame


# --- Send command ---
def send_brightness(value, status_var):
    cmd = build_brightness_cmd(value)

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

            ser.reset_input_buffer()
            ser.reset_output_buffer()

            ser.write(cmd)
            ser.flush()

            time.sleep(0.2)
            resp = ser.read_all()

        if resp:
            print("RX:", " ".join(f"{b:02X}" for b in resp))
            status_var.set(f"Sent {value} → ACK")
        else:
            status_var.set(f"Sent {value} (no response)")

    except Exception as e:
        status_var.set(str(e))


# --- GUI ---
def create_gui():
    root = tk.Tk()
    root.title("X16E RS232 Brightness Control")
    root.geometry("420x220")

    frame = ttk.Frame(root, padding=10)
    frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(frame, text="Brightness (0–255)").pack()
    ttk.Label(frame, text="this is a test").pack()

    brightness = tk.IntVar(value=128)

    value_label = ttk.Label(frame, text="128", font=("Arial", 18, "bold"))
    value_label.pack(pady=5)

    def on_slide(v):
        val = int(float(v))
        brightness.set(val)
        value_label.config(text=str(val))

    slider = ttk.Scale(
        frame,
        from_=0,
        to=255,
        orient=tk.HORIZONTAL,
        length=255,
        command=on_slide
    )
    slider.set(128)
    slider.pack(pady=10)

    status = tk.StringVar(value="Ready")
    ttk.Label(frame, textvariable=status).pack(pady=5)

    ttk.Button(
        frame,
        text="Send Brightness",
        command=lambda: send_brightness(brightness.get(), status)
    ).pack(pady=5)

    root.mainloop()


# --- RUN ---
if __name__ == "__main__":
    create_gui()