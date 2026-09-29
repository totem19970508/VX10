import requests
import tkinter as tk
from tkinter import ttk

IP = "10.0.1.182"
USERNAME = "admin"
PASSWORD = "Simpson!712"

BASE_URL = f"http://{IP}"
session = requests.Session()


def login():
    r = session.post(
        f"{BASE_URL}/api/login",
        json={"username": USERNAME, "password": PASSWORD},
        timeout=5
    )
    r.raise_for_status()
    print("Login OK")


def get_current_brightness():
    r = session.get(
        f"{BASE_URL}/api/brightnessandcolortemp.json",
        timeout=5
    )
    r.raise_for_status()

    data = r.json()
    return int(data["brightness"])


def set_brightness(value):
    value = max(0, min(100, int(value)))

    r = session.put(
        f"{BASE_URL}/api/brightness",
        json={"brightness": value},
        timeout=5
    )
    r.raise_for_status()

    return value


def create_gui():
    root = tk.Tk()
    root.title("VX10 REST API Brightness Control")
    root.geometry("480x270")

    frame = ttk.Frame(root, padding=10)
    frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(frame, text=f"VX10 IP: {IP}").pack()
    ttk.Label(frame, text="REST API Brightness Control").pack()

    status = tk.StringVar(value="Starting...")
    brightness = tk.IntVar(value=0)

    value_label = ttk.Label(frame, text="--%", font=("Arial", 22, "bold"))
    value_label.pack(pady=10)

    def update_display(value):
        brightness.set(value)
        value_label.config(text=f"{value}%")
        slider.set(value)

    # Get current brightness before slider is shown
    try:
        current = get_current_brightness()
        update_start_value = current
        status.set(f"Current brightness read: {current}%")
    except Exception as e:
        update_start_value = 50
        status.set(f"Read failed, default 50%. Error: {e}")

    def on_slide(v):
        val = int(float(v))
        brightness.set(val)
        value_label.config(text=f"{val}%")

    def on_release(event):
        val = brightness.get()

        try:
            set_brightness(val)
            status.set(f"Brightness set to {val}%")
        except Exception as e:
            status.set(f"Set failed: {e}")

    slider = ttk.Scale(
        frame,
        from_=0,
        to=100,
        orient=tk.HORIZONTAL,
        length=360,
        command=on_slide
    )
    slider.pack(pady=10)
    slider.bind("<ButtonRelease-1>", on_release)

    update_display(update_start_value)

    ttk.Button(
        frame,
        text="Refresh Current Brightness",
        command=lambda: update_display(get_current_brightness())
    ).pack(pady=5)

    ttk.Label(frame, textvariable=status, wraplength=450).pack(pady=5)

    root.mainloop()


if __name__ == "__main__":
    login()
    create_gui()