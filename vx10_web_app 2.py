import importlib.util
import json
import mimetypes
import os
import sys
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"
APP_FILE = BASE_DIR / "VX10-brightness -2 (protocol).py"
HOST = os.environ.get("VX10_WEB_HOST", "127.0.0.1")
PORT = int(os.environ.get("VX10_WEB_PORT", "8080"))


def load_vx10_module():
    spec = importlib.util.spec_from_file_location("vx10_protocol", APP_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


vx10 = load_vx10_module()


def display_timeline_items(items):
    display_items = []
    seen = set()
    for item in items:
        key = (
            item["name"],
            vx10.format_schedule_time(item["start"]),
            vx10.format_schedule_time(item["end"]),
            item["brightness_percent"],
        )
        if key in seen:
            continue
        seen.add(key)
        display_items.append(item)
    return display_items


def item_identity(item):
    if item is None:
        return None
    return (
        item["name"],
        vx10.format_schedule_time(item["start"]),
        vx10.format_schedule_time(item["end"]),
        item["brightness_percent"],
    )


def serialize_item(item, active_identity):
    nits = vx10.percent_to_nits(item["brightness_percent"])
    return {
        "name": item["name"],
        "label": item["name"].split(" - ", 1)[0],
        "start": item["start"].isoformat(),
        "end": item["end"].isoformat(),
        "start_text": vx10.format_schedule_time(item["start"]),
        "end_text": vx10.format_schedule_time(item["end"]),
        "schedule_text": f"{vx10.format_schedule_time(item['start'])} - {vx10.format_schedule_time(item['end'])}",
        "brightness_percent": item["brightness_percent"],
        "brightness_text": vx10.format_brightness_percent(item["brightness_percent"]),
        "nits": nits,
        "nits_text": f"{nits:,.0f}",
        "active": item_identity(item) == active_identity,
    }


def build_state():
    config = vx10.load_schedule_config()
    now = vx10.get_pc_now(config)
    today = now.date()
    sun_times = vx10.fetch_sun_times(config, today)
    intervals = vx10.build_schedule_intervals(config, today, sun_times)
    active = vx10.find_active_interval(intervals, now)
    active_id = item_identity(active)
    todays_rows = [
        item for item in intervals
        if item["start"].date() <= today <= item["end"].date()
    ]
    timeline_items = display_timeline_items(todays_rows)

    active_payload = None
    if active is not None:
        active_nits = vx10.percent_to_nits(active["brightness_percent"])
        active_payload = {
            "name": active["name"],
            "start_text": vx10.format_schedule_time(active["start"]),
            "end_text": vx10.format_schedule_time(active["end"]),
            "brightness_percent": active["brightness_percent"],
            "brightness_text": vx10.format_brightness_percent(active["brightness_percent"]),
            "nits": active_nits,
            "nits_text": f"{active_nits:,.0f}",
        }

    return {
        "version": getattr(vx10, "APP_VERSION", "Version 1.0"),
        "location": config["location"].get("name", "Location"),
        "today": today.isoformat(),
        "now": now.isoformat(),
        "now_text": now.strftime("%Y-%m-%d %I:%M:%S %p %Z").replace(" 0", " "),
        "sun": {
            "sr": sun_times["SR"].isoformat(),
            "ss": sun_times["SS"].isoformat(),
            "sr_text": vx10.format_schedule_time(sun_times["SR"]),
            "ss_text": vx10.format_schedule_time(sun_times["SS"]),
            "source": sun_times.get("source", "unknown"),
        },
        "active": active_payload,
        "schedule": [serialize_item(item, active_id) for item in timeline_items],
        "reference": [
            {
                "percent": percent,
                "percent_text": f"{percent}%",
                "nits": nits,
                "nits_text": f"{nits:,.0f}",
            }
            for percent, nits in vx10.REFERENCE_NIT_ROWS
        ],
        "refresh_seconds": float(config.get("pc_time_refresh_seconds", 1)),
        "network": vx10.get_network_config(config),
    }


class VX10WebHandler(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        parsed = urlparse(path)
        if parsed.path == "/":
            return str(WEB_DIR / "index.html")
        if parsed.path == "/company_logo.png":
            logo = BASE_DIR / "company_logo.png"
            if not logo.exists():
                logo = BASE_DIR / "Company_logo.png"
            return str(logo)
        return str(WEB_DIR / parsed.path.lstrip("/"))

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/state":
            self.send_json(build_state())
            return
        if parsed.path == "/api/brightness":
            params = parse_qs(parsed.query)
            mode = params.get("mode", ["TCP"])[0]
            value = vx10.get_brightness(mode)
            self.send_json({"brightness": value})
            return
        if parsed.path == "/api/color-temp":
            self.send_json(vx10.get_display_color_temperature())
            return
        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/brightness":
            body = self.read_json_body()
            mode = body.get("mode", "TCP")
            percent = body.get("percent", 0)
            value = vx10.set_brightness(mode, percent)
            self.send_json({
                "brightness": value,
                "brightness_text": vx10.format_brightness_percent(value),
                "nits": vx10.percent_to_nits(value),
            })
            return
        self.send_error(404)

    def read_json_body(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def send_json(self, payload, status=200):
        encoded = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def guess_type(self, path):
        if path.endswith(".js"):
            return "application/javascript"
        if path.endswith(".css"):
            return "text/css"
        return mimetypes.guess_type(path)[0] or "application/octet-stream"


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else PORT
    WEB_DIR.mkdir(exist_ok=True)
    server = ThreadingHTTPServer((HOST, port), VX10WebHandler)
    print(f"VX10 web app running at http://{HOST}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
