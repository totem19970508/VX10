import requests
import tkinter as tk
from tkinter import ttk

IP = "10.0.1.182"
USERNAME = "admin"
PASSWORD = "Simpson!712"

BASE_URL = f"http://{IP}"
session = requests.Session()


def raw_to_percent(raw):
    return round(raw * 100 / 255)


def percent_to_raw(percent):
    return round(percent * 255 / 100)


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
    raw = int(data["brightness"])
    percent = raw_to_percent(raw)

    return raw, percent


def set_brightness(percent):
    percent = max(0, min(100, int(percent)))
    raw = percent_to_raw(percent)

    r = session.put(
        f"{BASE_URL}/api/brightness",
        json={"brightness": raw},
        timeout=5
    )
    r.raise_for_status()

    return raw, percent


def create_gui():
    root = tk.Tk()
    root.title("A200 REST API Brightness Control")
    root.geometry("500x300")

    frame = ttk.Frame(root, padding=10)
    frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(frame, text=f"A200 IP: {IP}").pack()
    ttk.Label(frame, text="REST API Brightness Control").pack()

    status = tk.StringVar(value="Starting...")
    brightness = tk.IntVar(value=0)

    value_label = ttk.Label(frame, text="--%", font=("Arial", 22, "bold"))
    value_label.pack(pady=10)

    slider = ttk.Scale(
        frame,
        from_=0,
        to=100,
        orient=tk.HORIZONTAL,
        length=360
    )
    slider.pack(pady=10)

    def update_display(percent):
        percent = max(0, min(100, int(percent)))
        brightness.set(percent)
        value_label.config(text=f"{percent}%")
        slider.set(percent)

    def refresh_current():
        try:
            raw, percent = get_current_brightness()
            update_display(percent)
            status.set(f"Current brightness: {raw}/255 = {percent}%")
        except Exception as e:
            status.set(f"Read failed: {e}")

    def on_slide(v):
        val = int(float(v))
        brightness.set(val)
        value_label.config(text=f"{val}%")

    def on_release(event):
        val = brightness.get()

        try:
            raw, percent = set_brightness(val)
            status.set(f"Brightness set: {raw}/255 = {percent}%")
        except Exception as e:
            status.set(f"Set failed: {e}")

    slider.config(command=on_slide)
    slider.bind("<ButtonRelease-1>", on_release)

    ttk.Button(
        frame,
        text="Refresh Current Brightness",
        command=refresh_current
    ).pack(pady=5)

    ttk.Label(frame, textvariable=status, wraplength=470).pack(pady=5)

    refresh_current()

    root.mainloop()


if __name__ == "__main__":
    login()
    create_gui()