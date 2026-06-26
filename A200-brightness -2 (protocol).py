"""
Colorlight A200 brightness scheduler and monitor.
(Version 1.0)
Task summary:
- Send brightness commands to the A200 over TCP or UDP.
- Load a daily brightness schedule from a JSON file.
- Resolve sunrise (SR) and sunset (SS) times for timeline-based rules.
- Show the active schedule, nits estimate, color temperature, and timeline.
- Auto-refresh from PC time so the display follows the schedule.
"""

import socket
import json
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, date, time, timedelta, timezone
from pathlib import Path
import re
import math
import os
import sys
import atexit
import threading
import time as time_module
import http.cookiejar
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPCookieProcessor, urlopen
from urllib.error import HTTPError, URLError
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_IP = "10.0.1.182"

if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).resolve().parent
else:
    APP_DIR = Path(__file__).resolve().parent
BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", APP_DIR))

SCHEDULE_FILE = APP_DIR / "a200_brightness_schedule.json"
CIVIL_TWILIGHT_FILE = APP_DIR / "Civil Twilight (Toronto).json"
LOCK_FILE = APP_DIR / ".a200_brightness_schedule.lock"
LOGO_FILE = APP_DIR / "company_logo.png"
FALLBACK_LOGO_FILE = APP_DIR / "Company_logo.png"
LOGO_CANDIDATES = (
    LOGO_FILE,
    FALLBACK_LOGO_FILE,
    BUNDLE_DIR / "company_logo.png",
    BUNDLE_DIR / "Company_logo.png",
)
LOGO_SIZE_DIVISOR = 2 # 2 bigger, 3, 4 smaller, etc.
APP_BG = "#2f2f2f"
PANEL_BG = "#3a3a3a"
SURFACE_BG = "#1f1f1f"
SURFACE_HEADER_BG = "#242424"
TEXT_LIGHT = "#f5f5f5"
TEXT_DARK = "#111111"
ACTIVE_BG = "#4a2525"
ACTIVE_TEXT = "#ffd6d6"
ACTIVE_ACCENT = "#ff3333"
APP_VERSION = "Version 1.0"

DEFAULT_TCP_PORT = 6000
DEFAULT_UDP_PORT = 6001

MEASURED_NITS = {
    0.0: 0.0,
    1.0: (39.583 + 39.848) / 2,
    2.0: (85.192 + 85.468) / 2,
    3.0: 140.41,
    45.0: 2831.3,
    50.0: 3133.3,
    60.0: 3951.7,
    70.0: 4668.3,
    80.0: 5371.6,
    90.0: 6103.1,
    100.0: 7083.7,
}

REFERENCE_NIT_ROWS = [
    (0, 0.0),
    (1, MEASURED_NITS[1.0]),
    (2, MEASURED_NITS[2.0]),
    (3, MEASURED_NITS[3.0]),
    (45, MEASURED_NITS[45.0]),
    (50, MEASURED_NITS[50.0]),
    (60, MEASURED_NITS[60.0]),
    (70, MEASURED_NITS[70.0]),
    (80, MEASURED_NITS[80.0]),
    (90, MEASURED_NITS[90.0]),
    (100, MEASURED_NITS[100.0]),
]

# CSS-like timeline style reference.
# Tkinter does not use CSS, so these values act like a tiny stylesheet for the
# canvas: change colors, fonts, or spacing here when adjusting the timeline.
TIMELINE_STYLE = {
    "background": SURFACE_BG,
    "line_color": "#f5f5f5",
    "schedule_label_color": "#d22",
    "sun_marker_color": "#2277dd",
    "now_marker_color": ACTIVE_ACCENT,
    "line_width": 2,
    "margin_x": 42,
    "line_y": 58,
    "brightness_y": 92,
    "tick_height": 15,
    "time_label_offset": 30,
    "sun_arrow_top_offset": 36,
    "sun_arrow_tip_offset": 18,
    "sun_label_offset": 46,
    "time_font": ("Arial", 10, "bold"),
    "brightness_font": ("Arial", 12, "bold"),
    "schedule_label_font": ("Arial", 14, "bold"),
    "sun_label_font": ("Arial", 10, "bold"),
}

FLAGS = {
    "TCP": 0x11,
    "UDP": 0x12,
}

DEFAULT_SCHEDULE = {
    "location": {
        "name": "Toronto",
        "latitude": 43.6532,
        "longitude": -79.3832,
        "timezone": "America/Toronto",
    },
    "sun_api": {
        "enabled": False,
        "url": "https://api.sunrise-sunset.org/json",
        "timeout_seconds": 8,
        "example_full_request": "https://api.sunrise-sunset.org/json?lat=43.6532&lng=-79.3832&date=today&formatted=0&tzid=America/Toronto",
    },
    "fallback_sun_times": {
        "sunrise": "06:00",
        "sunset": "20:00",
    },
    "network": {
        "ip_address": DEFAULT_IP,
        "tcp": {
            "enabled": True,
            "port": DEFAULT_TCP_PORT,
        },
        "udp": {
            "enabled": True,
            "port": DEFAULT_UDP_PORT,
        },
    },
    "http_api": {
        "username": "admin",
        "password": "Simpson!712",
        "timeout_seconds": 5,
    },
    "apply_schedule_on_startup": True,
    "auto_refresh_seconds": 1,
    "pc_time_refresh_seconds": 1,
    "delta_hours": 0.5,
    "test_pc_time": "",
    "schedule": [
        {
            "name": "a - Late night off",
            "start": {"time": "23:00"},
            "end": {"time": "00:00"},
            "brightness_percent": 0,
        },
        {
            "name": "b - Overnight off",
            "start": {"time": "00:00"},
            "end": {"anchor": "SR", "offset_hours": "D"},
            "brightness_percent": 0,
        },
        {
            "name": "c - Sunrise ramp",
            "start": {"anchor": "SR", "offset_hours": "D"},
            "end": {"anchor": "SR", "offset_hours": "2D"},
            "brightness_percent": 10,
        },
        {
            "name": "d - Morning ramp",
            "start": {"anchor": "SR", "offset_hours": "2D"},
            "end": {"anchor": "SR", "offset_hours": "3D"},
            "brightness_percent": 20,
        },
        {
            "name": "e - Business day",
            "start": {"anchor": "SR", "offset_hours": "3D"},
            "end": {"anchor": "SS", "offset_hours": "-2D"},
            "brightness_percent": 65,
        },
        {
            "name": "f - Sunset prep",
            "start": {"anchor": "SS", "offset_hours": "-2D"},
            "end": {"anchor": "SS"},
            "brightness_percent": 50,
        },
        {
            "name": "g - After sunset low",
            "start": {"anchor": "SS"},
            "end": {"time": "23:00"},
            "brightness_percent": 3,
        },
    ],
}

DEFAULT_CIVIL_TWILIGHT = {
    "location": {
        "name": "Toronto",
        "timezone": "America/Toronto",
    },
    "description": "Monthly average sunrise/sunset lookup for Toronto. Used as fallback when live API and local calculation are unavailable.",
    "delta_note": "Schedule D remains controlled by a200_brightness_schedule.json.",
    "months": {
        "1": {
            "month": "January",
            "sunrise": "7:45 AM",
            "sunset": "5:00 PM",
            "average_day_length": "~9 hours, 15 mins",
            "monthly_daylight_trend": "Gaining ~2 mins of light per day.",
        },
        "2": {
            "month": "February",
            "sunrise": "7:10 AM",
            "sunset": "5:40 PM",
            "average_day_length": "~10 hours, 30 mins",
            "monthly_daylight_trend": "Gaining ~2.5 mins of light per day.",
        },
        "3": {
            "month": "March (DST)",
            "sunrise": "7:25 AM",
            "sunset": "7:20 PM",
            "average_day_length": "~11 hours, 55 mins",
            "monthly_daylight_trend": "Gaining ~3 mins of light per day.",
        },
        "4": {
            "month": "April",
            "sunrise": "6:30 AM",
            "sunset": "8:00 PM",
            "average_day_length": "~13 hours, 30 mins",
            "monthly_daylight_trend": "Gaining ~2.5 mins of light per day.",
        },
        "5": {
            "month": "May",
            "sunrise": "5:50 AM",
            "sunset": "8:35 PM",
            "average_day_length": "~14 hours, 45 mins",
            "monthly_daylight_trend": "Gaining ~2 mins of light per day.",
        },
        "6": {
            "month": "June",
            "sunrise": "5:35 AM",
            "sunset": "9:00 PM",
            "average_day_length": "~15 hours, 25 mins",
            "monthly_daylight_trend": "Summer Solstice; peak annual daylight.",
        },
        "7": {
            "month": "July",
            "sunrise": "5:50 AM",
            "sunset": "8:50 PM",
            "average_day_length": "~15 hours, 00 mins",
            "monthly_daylight_trend": "Losing ~1.5 mins of light per day.",
        },
        "8": {
            "month": "August",
            "sunrise": "6:25 AM",
            "sunset": "8:15 PM",
            "average_day_length": "~13 hours, 50 mins",
            "monthly_daylight_trend": "Losing ~2.5 mins of light per day.",
        },
        "9": {
            "month": "September",
            "sunrise": "7:00 AM",
            "sunset": "7:20 PM",
            "average_day_length": "~12 hours, 20 mins",
            "monthly_daylight_trend": "Losing ~3 mins of light per day.",
        },
        "10": {
            "month": "October",
            "sunrise": "7:35 AM",
            "sunset": "6:30 PM",
            "average_day_length": "~10 hours, 55 mins",
            "monthly_daylight_trend": "Losing ~2.5 mins of light per day.",
        },
        "11": {
            "month": "November (ST)",
            "sunrise": "7:15 AM",
            "sunset": "4:50 PM",
            "average_day_length": "~9 hours, 35 mins",
            "monthly_daylight_trend": "Losing ~2 mins of light per day.",
        },
        "12": {
            "month": "December",
            "sunrise": "7:45 AM",
            "sunset": "4:45 PM",
            "average_day_length": "~9 hours, 00 mins",
            "monthly_daylight_trend": "Winter Solstice; lowest annual daylight.",
        },
    },
}

def build_frame(mode, command):
    flag = FLAGS[mode]
    frame = bytearray()
    frame.append(0x02)                 # STX
    frame.append(flag)                 # TCP / UDP flag
    frame += command.encode("ascii")   # Command data
    frame.append(0x03)                 # ETX
    frame.append(0x32)                 # Fixed LRC from host
    return bytes(frame)

def send_tcp(command):
    network = get_network_config()
    if not network["tcp_enabled"]:
        raise RuntimeError("TCP is disabled in network config")

    frame = build_frame("TCP", command)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(3)
        s.connect((network["ip_address"], network["tcp_port"]))
        s.sendall(frame)
        try:
            return s.recv(1024)
        except socket.timeout:
            return b""

def send_udp(command):
    network = get_network_config()
    if not network["udp_enabled"]:
        raise RuntimeError("UDP is disabled in network config")

    frame = build_frame("UDP", command)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.settimeout(3)
        s.sendto(frame, (network["ip_address"], network["udp_port"]))
        try:
            data, _ = s.recvfrom(1024)
            return data
        except socket.timeout:
            return b""

def send_command(mode, command):
    if mode == "TCP":
        return send_tcp(command)
    else:
        return send_udp(command)

def normalize_brightness_percent(percent):
    return max(0.0, min(100.0, float(percent)))

def format_brightness_percent(percent):
    value = normalize_brightness_percent(percent)
    if value.is_integer():
        return f"{int(value)}%"
    return f"{value:g}%"

def set_brightness(mode, percent):
    percent = normalize_brightness_percent(percent)
    raw = round(percent * 255 / 100)
    command = f"303{raw:03d}"
    response = send_command(mode, command)

    print("SET:", command)
    print("RX:", response.hex(" ") if response else "No reply")
    return percent

def get_brightness(mode):
    response = send_command(mode, "399")
    print("GET RX:", response.hex(" ") if response else "No reply")

    # Expected data response contains: 399 + 3-digit brightness
    try:
        text = response.decode("ascii", errors="ignore")
        idx = text.find("399")
        if idx >= 0:
            raw = int(text[idx + 3:idx + 6])
            return round(raw * 100 / 255)
    except Exception:
        pass

    return None


def http_json_request(url, method="GET", payload=None, timeout=5, opener=None):
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = Request(url, data=data, headers=headers, method=method)
    open_request = opener.open if opener is not None else urlopen
    with open_request(request, timeout=timeout) as response:
        raw = response.read().decode("utf-8", errors="replace")
    return json.loads(raw)


def get_display_color_temperature(config=None):
    if config is None:
        config = load_schedule_config()

    network = get_network_config(config)
    http_api = config.get("http_api", {})
    ip_address = network["ip_address"]
    timeout = float(http_api.get("timeout_seconds", 5))
    base_url = f"http://{ip_address}"
    endpoint = f"{base_url}/api/brightnessandcolortemp.json"
    cookie_jar = http.cookiejar.CookieJar()
    opener = build_opener(HTTPCookieProcessor(cookie_jar))

    try:
        data = http_json_request(endpoint, timeout=timeout, opener=opener)
    except HTTPError as e:
        if e.code not in (401, 403):
            raise
        username = http_api.get("username", "admin")
        password = http_api.get("password", "Simpson!712")
        http_json_request(
            f"{base_url}/api/login",
            method="POST",
            payload={"username": username, "password": password},
            timeout=timeout,
            opener=opener,
        )
        data = http_json_request(endpoint, timeout=timeout, opener=opener)

    brightness = data.get("brightness")
    color_temperature = data.get("colortemperature")
    if color_temperature is None:
        color_temperature = data.get("color_temperature")

    return {
        "brightness": brightness,
        "color_temperature": color_temperature,
        "raw": data,
    }


def percent_to_nits(percent: float) -> float:
    """Convert brightness percent to approximate nits using measured points

    Uses measured values and linear interpolation between them. Treats 0% as 0 nits.
    """
    p = float(max(0.0, min(100.0, percent)))
    keys = sorted(MEASURED_NITS.keys())
    if p in MEASURED_NITS:
        return MEASURED_NITS[p]

    # find nearest interval
    for i in range(len(keys) - 1):
        a = keys[i]
        b = keys[i + 1]
        if a <= p <= b:
            na = MEASURED_NITS[a]
            nb = MEASURED_NITS[b]
            if b == a:
                return na
            t = (p - a) / (b - a)
            return na + (nb - na) * t

    # fallback (shouldn't happen) linear extrapolation using top two points
    a, b = keys[-2], keys[-1]
    na, nb = MEASURED_NITS[a], MEASURED_NITS[b]
    t = (p - a) / (b - a)
    return na + (nb - na) * t

def load_schedule_config():
    if not SCHEDULE_FILE.exists():
        try:
            SCHEDULE_FILE.write_text(json.dumps(DEFAULT_SCHEDULE, indent=2), encoding="utf-8")
        except OSError:
            return DEFAULT_SCHEDULE

    try:
        with SCHEDULE_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return DEFAULT_SCHEDULE

def get_network_config(config=None):
    if config is None:
        config = load_schedule_config()

    network = config.get("network", {})
    tcp = network.get("tcp", {})
    udp = network.get("udp", {})
    return {
        "ip_address": network.get("ip_address", DEFAULT_IP),
        "tcp_port": int(tcp.get("port", DEFAULT_TCP_PORT)),
        "udp_port": int(udp.get("port", DEFAULT_UDP_PORT)),
        "tcp_enabled": tcp.get("enabled", True),
        "udp_enabled": udp.get("enabled", True),
    }

def get_zone_info(timezone_name="UTC"):
    if timezone_name.upper() == "UTC":
        return timezone.utc

    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return datetime.now().astimezone().tzinfo


def get_pc_now(config):
    tz = get_zone_info(config["location"].get("timezone", "America/Toronto"))
    test_pc_time = str(config.get("test_pc_time", "")).strip()
    if test_pc_time:
        today = datetime.now(tz).date()
        if "T" in test_pc_time:
            parsed = datetime.fromisoformat(test_pc_time)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=tz)
            return parsed.astimezone(tz)

        hour, minute = [int(part) for part in test_pc_time.split(":", 1)]
        return datetime.combine(today, time(hour, minute), tzinfo=tz)

    return datetime.now(tz)

def fetch_sun_times(config, for_date):
    location = config["location"]
    api = config.get("sun_api", DEFAULT_SCHEDULE["sun_api"])
    tz = get_zone_info(location.get("timezone", "America/Toronto"))

    if not api.get("enabled", False):
        return fallback_sun_times(config, location, for_date, tz, "API disabled")

    params = urlencode({
        "lat": location["latitude"],
        "lng": location["longitude"],
        "date": for_date.isoformat(),
        "formatted": 0,
        "tzid": location.get("timezone", "America/Toronto"),
    })
    url = f"{api.get('url', DEFAULT_SCHEDULE['sun_api']['url'])}?{params}"

    try:
        with urlopen(url, timeout=api.get("timeout_seconds", 8)) as response:
            payload = json.loads(response.read().decode("utf-8"))

        if payload.get("status") != "OK":
            raise RuntimeError(f"Sunrise/sunset API error: {payload.get('status')}")

        results = payload["results"]
        sunrise = parse_api_datetime(results["sunrise"]).astimezone(tz)
        sunset = parse_api_datetime(results["sunset"]).astimezone(tz)
        return {"SR": sunrise, "SS": sunset, "source": "API"}
    except (OSError, RuntimeError, URLError) as e:
        return fallback_sun_times(config, location, for_date, tz, f"API failed ({e})")

def fallback_sun_times(config, location, for_date, tz, reason):
    try:
        sun_times = calculate_sun_times(location, for_date, tz)
        sun_times["source"] = f"local calculation, {reason}"
        return sun_times
    except Exception as local_error:
        try:
            sun_times = lookup_monthly_sun_times(for_date, tz)
            sun_times["source"] = (
                f"{sun_times['source']}, {reason}, local calculation failed ({local_error})"
            )
            return sun_times
        except Exception as lookup_error:
            sun_times = fallback_fixed_sun_times(config, for_date, tz)
            sun_times["source"] = (
                f"{sun_times['source']}, {reason}, local calculation failed ({local_error}), "
                f"monthly lookup failed ({lookup_error})"
            )
            return sun_times

def lookup_monthly_sun_times(for_date, tz):
    try:
        with CIVIL_TWILIGHT_FILE.open("r", encoding="utf-8") as f:
            lookup = json.load(f)
        source = f"monthly lookup: {CIVIL_TWILIGHT_FILE.name}"
    except (OSError, json.JSONDecodeError):
        lookup = DEFAULT_CIVIL_TWILIGHT
        source = "embedded monthly lookup"

    month_data = lookup["months"][str(for_date.month)]
    return {
        "SR": parse_lookup_clock_time(month_data["sunrise"], for_date, tz),
        "SS": parse_lookup_clock_time(month_data["sunset"], for_date, tz),
        "source": source,
    }

def fallback_fixed_sun_times(config, for_date, tz):
    fallback = config.get("fallback_sun_times", DEFAULT_SCHEDULE["fallback_sun_times"])
    return {
        "SR": parse_clock_time(fallback.get("sunrise", "06:00"), for_date, tz),
        "SS": parse_clock_time(fallback.get("sunset", "20:00"), for_date, tz),
        "source": "fixed fallback_sun_times",
    }

def calculate_sun_times(location, for_date, tz):
    latitude = float(location["latitude"])
    longitude = float(location["longitude"])
    sunrise = calculate_sun_time_utc(for_date, latitude, longitude, is_sunrise=True).astimezone(tz)
    sunset = calculate_sun_time_utc(for_date, latitude, longitude, is_sunrise=False).astimezone(tz)
    return {
        "SR": normalize_sun_local_date(sunrise, for_date),
        "SS": normalize_sun_local_date(sunset, for_date),
        "source": "local calculation",
    }

def normalize_sun_local_date(value, for_date):
    while value.date() < for_date:
        value += timedelta(days=1)
    while value.date() > for_date:
        value -= timedelta(days=1)
    return value

def calculate_sun_time_utc(for_date, latitude, longitude, is_sunrise):
    zenith = 90.833
    day_of_year = for_date.timetuple().tm_yday
    lng_hour = longitude / 15
    approximate_hour = 6 if is_sunrise else 18
    t = day_of_year + ((approximate_hour - lng_hour) / 24)

    mean_anomaly = (0.9856 * t) - 3.289
    true_longitude = (
        mean_anomaly
        + (1.916 * math.sin(math.radians(mean_anomaly)))
        + (0.020 * math.sin(math.radians(2 * mean_anomaly)))
        + 282.634
    ) % 360

    right_ascension = math.degrees(
        math.atan(0.91764 * math.tan(math.radians(true_longitude)))
    ) % 360
    longitude_quadrant = math.floor(true_longitude / 90) * 90
    ascension_quadrant = math.floor(right_ascension / 90) * 90
    right_ascension = (right_ascension + longitude_quadrant - ascension_quadrant) / 15

    sin_declination = 0.39782 * math.sin(math.radians(true_longitude))
    cos_declination = math.cos(math.asin(sin_declination))
    cos_hour_angle = (
        math.cos(math.radians(zenith))
        - (sin_declination * math.sin(math.radians(latitude)))
    ) / (cos_declination * math.cos(math.radians(latitude)))

    if cos_hour_angle > 1:
        raise RuntimeError("Sun never rises on this date at this location")
    if cos_hour_angle < -1:
        raise RuntimeError("Sun never sets on this date at this location")

    if is_sunrise:
        hour_angle = 360 - math.degrees(math.acos(cos_hour_angle))
    else:
        hour_angle = math.degrees(math.acos(cos_hour_angle))
    hour_angle = hour_angle / 15

    local_mean_time = (
        hour_angle + right_ascension - (0.06571 * t) - 6.622
    )
    raw_utc_hour = local_mean_time - lng_hour
    utc_day_offset = math.floor(raw_utc_hour / 24)
    utc_hour = raw_utc_hour % 24
    hour = int(utc_hour)
    minute_float = (utc_hour - hour) * 60
    minute = int(minute_float)
    second = int(round((minute_float - minute) * 60))

    if second == 60:
        second = 0
        minute += 1
    if minute == 60:
        minute = 0
        hour = (hour + 1) % 24

    utc_date = for_date + timedelta(days=utc_day_offset)
    return datetime.combine(utc_date, time(hour, minute, second), tzinfo=timezone.utc)

def parse_api_datetime(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))

def parse_clock_time(value, base_date, tz):
    hour, minute = [int(part) for part in value.split(":", 1)]
    return datetime.combine(base_date, time(hour, minute), tzinfo=tz)

def parse_lookup_clock_time(value, base_date, tz):
    parsed = datetime.strptime(value.strip(), "%I:%M %p").time()
    return datetime.combine(base_date, parsed, tzinfo=tz)

def resolve_time(rule_time, base_date, sun_times, tz, delta_hours):
    if isinstance(rule_time, str):
        return parse_clock_time(rule_time, base_date, tz)

    if "time" in rule_time:
        resolved = parse_clock_time(rule_time["time"], base_date, tz)
        return apply_time_bounds(resolved, rule_time, base_date, sun_times, tz, delta_hours)

    anchor = rule_time.get("anchor", "").upper()
    if anchor not in sun_times:
        raise ValueError(f"Schedule anchor must be SR or SS, got {anchor!r}")

    offset_hours = parse_offset_hours(rule_time.get("offset_hours", 0), delta_hours)
    resolved = sun_times[anchor] + timedelta(hours=offset_hours)
    return apply_time_bounds(resolved, rule_time, base_date, sun_times, tz, delta_hours)

def resolve_bound_time(bound, base_date, sun_times, tz, delta_hours):
    if isinstance(bound, dict):
        return resolve_time(bound, base_date, sun_times, tz, delta_hours)
    return parse_clock_time(bound, base_date, tz)

def apply_time_bounds(resolved, rule_time, base_date, sun_times, tz, delta_hours):
    # Guards for seasonal sun times. Example: Toronto winter sunrise can be
    # after 7:00 AM and sunset can be before 6:00 PM, so schedule rules may
    # compare fixed clock times against sun anchor times to avoid reversed ranges.
    if "not_before" in rule_time:
        resolved = max(
            resolved,
            resolve_bound_time(rule_time["not_before"], base_date, sun_times, tz, delta_hours),
        )
    if "not_after" in rule_time:
        resolved = min(
            resolved,
            resolve_bound_time(rule_time["not_after"], base_date, sun_times, tz, delta_hours),
        )
    return resolved

def parse_offset_hours(value, delta_hours=0):
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()

    delta_match = re.fullmatch(r"([-+]?)\s*(?:(\d+(?:\.\d+)?)\s*)?D", text, flags=re.IGNORECASE)
    if delta_match:
        sign_text, multiplier_text = delta_match.groups()
        sign = -1 if sign_text == "-" else 1
        multiplier = float(multiplier_text) if multiplier_text else 1.0
        return sign * multiplier * float(delta_hours)

    match = re.search(r"[-+]?\d+(?:\.\d+)?", text)
    if not match:
        raise ValueError(f"Invalid offset_hours value: {value!r}")

    return float(match.group(0))

def parse_refresh_seconds(config):
    if "auto_refresh_seconds" in config:
        return parse_duration_seconds(config["auto_refresh_seconds"], default_unit="seconds")

    if "auto_refresh_minutes" in config:
        return parse_duration_seconds(config["auto_refresh_minutes"], default_unit="minutes")

    return 0

def parse_pc_time_refresh_seconds(config):
    if "pc_time_refresh_seconds" in config:
        return parse_duration_seconds(config["pc_time_refresh_seconds"], default_unit="seconds")

    return parse_refresh_seconds(config) or 15

def parse_duration_seconds(value, default_unit="seconds"):
    if isinstance(value, (int, float)):
        seconds = float(value)
        if default_unit == "minutes":
            seconds *= 60
        return max(0, seconds)

    text = str(value).strip().lower()
    match = re.search(r"[-+]?\d+(?:\.\d+)?", text)
    if not match:
        raise ValueError(f"Invalid refresh interval value: {value!r}")

    amount = float(match.group(0))
    if re.search(r"(minute|minutes|min|mins)\b", text):
        amount *= 60
    elif re.search(r"(second|seconds|sec|secs|s)\b", text):
        amount *= 1
    elif default_unit == "minutes":
        amount *= 60

    return max(0, amount)

def build_schedule_intervals(config, today, sun_times):
    tz = get_zone_info(config["location"].get("timezone", "America/Toronto"))
    delta_hours = parse_offset_hours(config.get("delta_hours", 0.5))
    intervals = []

    for day_offset in (-1, 0, 1):
        base_date = today + timedelta(days=day_offset)
        day_sun_times = sun_times if day_offset == 0 else {
            anchor: value + timedelta(days=day_offset)
            for anchor, value in sun_times.items()
            if anchor in ("SR", "SS")
        }

        for rule in config.get("schedule", []):
            start = resolve_time(rule["start"], base_date, day_sun_times, tz, delta_hours)
            end = resolve_time(rule["end"], base_date, day_sun_times, tz, delta_hours)
            if end <= start:
                start_is_clock = "time" in rule["start"]
                end_is_clock = "time" in rule["end"]
                if start_is_clock and end_is_clock:
                    end += timedelta(days=1)
                else:
                    continue

            intervals.append({
                "name": rule.get("name", "Schedule"),
                "start": start,
                "end": end,
                "brightness_percent": normalize_brightness_percent(rule["brightness_percent"]),
            })

    return sorted(intervals, key=lambda item: item["start"])

def find_active_interval(intervals, now):
    for item in intervals:
        if item["start"] <= now < item["end"]:
            return item
    return None

def format_schedule_time(dt):
    return dt.strftime("%I:%M %p").lstrip("0")

def acquire_single_instance_lock():
    if LOCK_FILE.exists():
        try:
            old_pid = int(LOCK_FILE.read_text(encoding="utf-8").strip())
            os.kill(old_pid, 0)
            return False, old_pid
        except ProcessLookupError:
            LOCK_FILE.unlink(missing_ok=True)
        except Exception:
            LOCK_FILE.unlink(missing_ok=True)

    LOCK_FILE.write_text(str(os.getpid()), encoding="utf-8")
    atexit.register(lambda: LOCK_FILE.unlink(missing_ok=True))
    return True, os.getpid()

def create_gui():
    lock_ok, lock_pid = acquire_single_instance_lock()
    if not lock_ok:
        print(f"A200 schedule app is already running with PID {lock_pid}.")
        return

    root = tk.Tk()
    root.title(f"Colorlight A200 Brightness Schedule Control - Layout V4 - PID {os.getpid()}")
    root.geometry("1000x760")
    root.minsize(1000, 760)
    root.configure(bg=APP_BG)
    root.option_add("*Background", APP_BG)
    root.option_add("*Foreground", TEXT_LIGHT)

    mode_var = tk.StringVar(value="TCP")
    value_var = tk.IntVar(value=50)
    status_var = tk.StringVar(value="Ready")
    sun_var = tk.StringVar(value="Sunrise/sunset: not loaded")
    active_var = tk.StringVar(value="Active schedule: not loaded")
    clock_var = tk.StringVar(value="Current time: not loaded")
    nits_var = tk.StringVar(value="~0 nits")
    temp_var = tk.StringVar(value="Color temperature: not loaded")
    auto_var = tk.StringVar(value="Auto refresh: not started")
    pid_var = tk.StringVar(value=f"Running PID: {os.getpid()}")
    auto_state = {"count": 0, "pc_time_count": 0}
    applied_schedule_state = {"key": None}
    timeline_state = {"items": []}
    stop_event = threading.Event()

    style = ttk.Style()
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    style.configure(".", font=("Arial", 10), background=APP_BG, foreground=TEXT_LIGHT)
    style.configure("App.TFrame", background=APP_BG)
    style.configure("SunInfo.TLabel", font=("Arial", 15, "bold"), background=APP_BG, foreground=TEXT_LIGHT)
    style.configure("Section.TLabel", font=("Arial", 11, "bold"), background=APP_BG, foreground=TEXT_LIGHT)
    style.configure("TLabel", background=APP_BG, foreground=TEXT_LIGHT)
    style.configure("TButton", padding=(8, 4))
    style.configure("TCombobox", fieldbackground=PANEL_BG, background=PANEL_BG, foreground=TEXT_LIGHT)
    style.configure(
        "Treeview",
        background=SURFACE_BG,
        fieldbackground=SURFACE_BG,
        foreground=TEXT_LIGHT,
        rowheight=24,
        bordercolor="#cccccc",
    )
    style.configure(
        "Treeview.Heading",
        background=SURFACE_HEADER_BG,
        foreground=TEXT_LIGHT,
        font=("Arial", 10, "bold"),
        relief="flat",
    )
    style.map(
        "Treeview",
        background=[("selected", PANEL_BG)],
        foreground=[("selected", TEXT_LIGHT)],
    )

    app_canvas = tk.Canvas(
        root,
        bg=APP_BG,
        highlightthickness=0,
        borderwidth=0,
    )
    app_canvas.pack(fill=tk.BOTH, expand=True)

    frame = tk.Frame(app_canvas, bg=APP_BG, padx=12, pady=12)
    frame_window = app_canvas.create_window(
        0,
        0,
        anchor=tk.NW,
        window=frame,
        width=1000,
        height=760,
    )

    def resize_app_canvas(event):
        app_canvas.itemconfigure(frame_window, width=event.width, height=event.height)

    app_canvas.bind("<Configure>", resize_app_canvas)

    header_frame = tk.Frame(frame, bg=APP_BG)
    header_frame.pack(fill=tk.X, pady=(0, 8))

    title_label = tk.Label(
        header_frame,
        text="EQ Bank Brightness Schedule Control",
        bg=APP_BG,
        fg=TEXT_LIGHT,
        font=("Arial", 18, "bold"),
    )
    title_label.pack(side=tk.LEFT, anchor=tk.W)

    logo_path = next((path for path in LOGO_CANDIDATES if path.exists()), None)
    if logo_path:
        logo_image = tk.PhotoImage(file=str(logo_path)).subsample(4, 4)
        logo_label = tk.Label(
            header_frame,
            image=logo_image,
            bg=APP_BG,
            borderwidth=0,
            highlightthickness=0,
        )
        logo_label.image = logo_image
        logo_label.pack(side=tk.RIGHT, anchor=tk.E)

    control_frame = tk.Frame(frame, bg=APP_BG)
    control_frame.pack(fill=tk.X, pady=(0, 8))

    tk.Label(
        control_frame,
        text="Protocol",
        bg=APP_BG,
        fg=TEXT_LIGHT,
        font=("Arial", 10, "bold"),
    ).pack(side=tk.LEFT, padx=(0, 6))
    tk.OptionMenu(
        control_frame,
        mode_var,
        "TCP",
        "UDP",
    ).pack(side=tk.LEFT, padx=(0, 16))

    tk.Label(
        control_frame,
        text="Brightness (%)",
        bg=APP_BG,
        fg=TEXT_LIGHT,
        font=("Arial", 10, "bold"),
    ).pack(side=tk.LEFT, padx=(0, 6))

    slider = ttk.Scale(
        control_frame,
        from_=0,
        to=100,
        orient="horizontal",
        variable=value_var,
        length=260
    )
    slider.pack(side=tk.LEFT, padx=(0, 8))

    label = tk.Label(
        control_frame,
        textvariable=value_var,
        bg=ACTIVE_BG,
        fg=ACTIVE_TEXT,
        font=("Arial", 14, "bold"),
        width=4,
    )
    label.pack(side=tk.LEFT)

    # Live nits readout next to percent
    def update_nits_label(*args):
        try:
            p = float(value_var.get())
            n = percent_to_nits(p)
            nits_var.set(f"{n:,.0f} nits")
        except Exception:
            nits_var.set("~0 nits")

    value_var.trace_add("write", update_nits_label)
    # initialize label
    update_nits_label()
    nits_label = tk.Label(
        control_frame,
        textvariable=nits_var,
        bg=ACTIVE_BG,
        fg=ACTIVE_TEXT,
        font=("Arial", 14, "bold"),
        width=14,
        anchor=tk.W,
    )
    nits_label.pack(side=tk.LEFT, padx=(10, 0))

    def apply_brightness():
        try:
            v = set_brightness(mode_var.get(), value_var.get())
            status_var.set(f"Brightness set to {format_brightness_percent(v)}")
        except Exception as e:
            messagebox.showerror("Error", str(e))
            status_var.set("Failed")

    def read_brightness():
        try:
            v = get_brightness(mode_var.get())
            if v is not None:
                value_var.set(v)
                status_var.set(f"Current brightness: {format_brightness_percent(v)}")
            else:
                status_var.set("No valid brightness reply")
        except Exception as e:
            messagebox.showerror("Error", str(e))
            status_var.set("Failed")

    def read_display_color_temperature():
        # Task: read the A200 HTTP API for brightness and color temperature.
        try:
            reading = get_display_color_temperature()
            brightness = reading.get("brightness")
            color_temperature = reading.get("color_temperature")

            if brightness is not None:
                try:
                    value_var.set(int(round(float(brightness))))
                except (TypeError, ValueError):
                    pass

            if color_temperature is None:
                temp_var.set("Color temperature: not found in reply")
                status_var.set(f"Display HTTP reply: {reading['raw']}")
                return

            temp_var.set(f"Color temperature: {color_temperature} K")
            if brightness is None:
                status_var.set(f"Current color temperature: {color_temperature} K")
            else:
                status_var.set(
                    f"Current brightness: {brightness}% | Color temperature: {color_temperature} K"
                )
        except Exception as e:
            messagebox.showerror("Temperature Error", str(e))
            status_var.set("Temperature read failed")

    def schedule_key(active):
        return (
            mode_var.get(),
            active["name"],
            active["start"].isoformat(),
            active["end"].isoformat(),
            active["brightness_percent"],
        )

    def schedule_table_rows(items, active=None):
        # Task: convert resolved schedule intervals into rows for the table.
        rows = []
        seen = set()
        active_identity = None
        if active is not None:
            active_identity = (
                active["name"],
                format_schedule_time(active["start"]),
                format_schedule_time(active["end"]),
                active["brightness_percent"],
            )

        for item in items:
            n = percent_to_nits(item['brightness_percent'])
            identity = (
                item["name"],
                format_schedule_time(item["start"]),
                format_schedule_time(item["end"]),
                item["brightness_percent"],
            )
            row = (
                item["name"],
                f"{format_schedule_time(item['start'])} - {format_schedule_time(item['end'])}",
                format_brightness_percent(item["brightness_percent"]),
                f"{n:,.0f}",
                identity == active_identity,
            )
            if row in seen:
                continue
            seen.add(row)
            rows.append(row)
        return rows

    def display_timeline_items(items):
        display_items = []
        seen = set()
        for item in items:
            key = (
                item["name"],
                format_schedule_time(item["start"]),
                format_schedule_time(item["end"]),
                item["brightness_percent"],
            )
            if key in seen:
                continue
            seen.add(key)
            display_items.append(item)
        return display_items

    def update_schedule_table(rows):
        for child in schedule_table.winfo_children():
            child.destroy()

        table_rows = [
            ("Description", [row[0] for row in rows]),
            ("Schedule", [row[1] for row in rows]),
            ("Brightness", [row[2] for row in rows]),
            ("Nits", [row[3] for row in rows]),
        ]
        active_columns = [bool(row[4]) for row in rows]

        for row_index, (label_text, values) in enumerate(table_rows):
            label = tk.Label(
                schedule_table,
                text=label_text,
                bg=SURFACE_HEADER_BG,
                fg=TEXT_LIGHT,
                font=("Arial", 10, "bold"),
                padx=8,
                pady=6,
                width=12,
                anchor=tk.CENTER,
            )
            label.grid(row=row_index, column=0, sticky="nsew")

            for column_index, value in enumerate(values, start=1):
                is_active = active_columns[column_index - 1]
                bg = ACTIVE_BG if is_active else SURFACE_BG
                fg = ACTIVE_TEXT if is_active else TEXT_LIGHT
                is_important_active_value = is_active and label_text in ("Brightness", "Nits")
                cell = tk.Label(
                    schedule_table,
                    text=value,
                    bg=bg,
                    fg=fg,
                    font=("Arial", 11 if is_important_active_value else 10, "bold" if row_index == 0 or is_important_active_value else "normal"),
                    padx=8,
                    pady=6,
                    width=18,
                    anchor=tk.CENTER,
                )
                cell.grid(row=row_index, column=column_index, sticky="nsew")

    def update_timeline_canvas(items, sun_times=None, current_time=None, active=None):
        timeline_state["items"] = items
        # Task: store optional sunrise/sunset data for blue SR/SS markers.
        timeline_state["sun_times"] = sun_times
        timeline_state["current_time"] = current_time
        timeline_state["active"] = active
        draw_timeline_canvas()

    def timeline_label(item):
        return item["name"].split(" - ", 1)[0]

    def draw_timeline_canvas(event=None):
        # Task: draw the visual timeline. TIMELINE_STYLE is the CSS-like
        # reference for colors, fonts, line positions, and marker spacing.
        items = timeline_state["items"]
        timeline_canvas.delete("all")
        if not items:
            return

        width = max(timeline_canvas.winfo_width(), 600)
        height = max(timeline_canvas.winfo_height(), 120)
        left = TIMELINE_STYLE["margin_x"]
        right = width - TIMELINE_STYLE["margin_x"]
        line_y = TIMELINE_STYLE["line_y"]
        bright_y = TIMELINE_STYLE["brightness_y"]
        tick_height = TIMELINE_STYLE["tick_height"]
        line_color = TIMELINE_STYLE["line_color"]
        timeline_canvas.create_rectangle(
            0,
            0,
            width,
            height,
            fill=TIMELINE_STYLE["background"],
            outline="",
        )

        # Soft proportional layout: use sqrt(duration) so long periods are
        # visibly longer than short ramps without taking over the full canvas.
        durations = [
            max(1.0, (item["end"] - item["start"]).total_seconds() / 3600)
            for item in items
        ]
        weights = [max(0.85, math.sqrt(hours)) for hours in durations]
        total_weight = sum(weights) or 1
        span = right - left
        segment_starts = [left]
        for weight in weights[:-1]:
            segment_starts.append(segment_starts[-1] + (weight / total_weight) * span)
        segment_ends = [
            left + (sum(weights[:index + 1]) / total_weight) * span
            for index in range(len(weights))
        ]

        def x_for(dt):
            # Presentable timeline: soft proportional blocks show long vs short
            # durations without making the full day mathematically exact.
            for index, item in enumerate(items):
                start = item["start"]
                end = item["end"]
                if start <= dt <= end:
                    seconds = max(1, (end - start).total_seconds())
                    ratio = (dt - start).total_seconds() / seconds
                    return segment_starts[index] + ratio * (segment_ends[index] - segment_starts[index])

            if dt < items[0]["start"]:
                return left
            return right

        last_label_x = None
        active = timeline_state.get("active")
        for index, item in enumerate(items):
            start_x = segment_starts[index]
            end_x = segment_ends[index]
            center_x = (start_x + end_x) / 2
            label = timeline_label(item)
            is_active = (
                active is not None
                and item["name"] == active["name"]
                and item["start"] == active["start"]
                and item["end"] == active["end"]
                and item["brightness_percent"] == active["brightness_percent"]
            )
            segment_color = ACTIVE_ACCENT if is_active else line_color
            brightness = (
                "OFF"
                if item["brightness_percent"] == 0
                else format_brightness_percent(item["brightness_percent"])
            )

            timeline_canvas.create_line(
                start_x,
                line_y,
                end_x,
                line_y,
                width=4 if is_active else TIMELINE_STYLE["line_width"],
                fill=segment_color,
            )
            timeline_canvas.create_line(
                start_x,
                line_y - tick_height,
                start_x,
                line_y + tick_height,
                width=TIMELINE_STYLE["line_width"],
                fill=line_color,
            )
            # Timeline layout: time labels above, brightness and rule letters below.
            timeline_canvas.create_text(
                center_x,
                bright_y + 20,
                text=label,
                fill=TIMELINE_STYLE["schedule_label_color"],
                font=TIMELINE_STYLE["schedule_label_font"],
            )
            timeline_canvas.create_text(
                center_x,
                bright_y,
                text=brightness,
                fill=segment_color,
                font=TIMELINE_STYLE["brightness_font"],
            )

            time_text = format_schedule_time(item["start"])
            if last_label_x is None or abs(start_x - last_label_x) > 44:
                timeline_canvas.create_text(
                    start_x,
                    line_y - TIMELINE_STYLE["time_label_offset"],
                    text=time_text,
                    fill=line_color,
                    font=TIMELINE_STYLE["time_font"],
                )
                last_label_x = start_x

        timeline_canvas.create_line(
            right,
            line_y - tick_height,
            right,
            line_y + tick_height,
            width=TIMELINE_STYLE["line_width"],
            fill=line_color,
        )
        timeline_canvas.create_text(
            right,
            line_y - TIMELINE_STYLE["time_label_offset"],
            text=format_schedule_time(items[-1]["end"]),
            fill=line_color,
            font=TIMELINE_STYLE["time_font"],
        )

        # Sunrise/sunset display: draw blue SR/SS arrows on the equal-spaced
        # visual timeline. Their location is presentable, not time-proportional.
        sun_times = timeline_state.get("sun_times")
        if sun_times and isinstance(sun_times, dict):
            try:
                sr = sun_times.get("SR")
                ss = sun_times.get("SS")
                def draw_marker(dt, text):
                    if dt is None:
                        return
                    x = x_for(dt)
                    timeline_canvas.create_polygon(
                        x,
                        line_y - TIMELINE_STYLE["sun_arrow_tip_offset"],
                        x - 6,
                        line_y - TIMELINE_STYLE["sun_arrow_top_offset"],
                        x + 6,
                        line_y - TIMELINE_STYLE["sun_arrow_top_offset"],
                        fill=TIMELINE_STYLE["sun_marker_color"],
                    )
                    timeline_canvas.create_text(
                        x,
                        line_y - TIMELINE_STYLE["sun_label_offset"],
                        text=text,
                        fill=TIMELINE_STYLE["sun_marker_color"],
                        font=TIMELINE_STYLE["sun_label_font"],
                    )

                draw_marker(sr, "SR")
                draw_marker(ss, "SS")
            except Exception:
                pass

        current_time = timeline_state.get("current_time")
        if current_time is not None:
            if current_time < items[0]["start"]:
                x = left
            elif current_time > items[-1]["end"]:
                x = right
            else:
                x = x_for(current_time)
            marker_color = TIMELINE_STYLE["now_marker_color"]
            # Red upward arrow: current PC time position on the schedule.
            timeline_canvas.create_polygon(
                x,
                line_y + 10,
                x - 5,
                line_y + 22,
                x + 5,
                line_y + 22,
                fill=marker_color,
                outline=marker_color,
            )
            timeline_canvas.create_text(
                x,
                line_y - 50,
                text=format_schedule_time(current_time),
                fill=marker_color,
                font=("Arial", 10, "bold"),
            )

    def refresh_schedule(
        apply_brightness_now=True,
        show_error=True,
        source="Manual",
        update_status=True,
    ):
        # Task: refresh sunrise/sunset, rebuild today's intervals, update GUI,
        # and optionally apply the active brightness to the display.
        try:
            config = load_schedule_config()
            now = get_pc_now(config)
            today = now.date()
            sun_times = fetch_sun_times(config, today)
            intervals = build_schedule_intervals(config, today, sun_times)
            active = find_active_interval(intervals, now)

            # Sunrise/sunset data display shown near the top of the GUI.
            sun_var.set(
                f"{config['location'].get('name', 'Location')} | "
                f"{today.isoformat()} | "
                f"SR {format_schedule_time(sun_times['SR'])} | "
                f"SS {format_schedule_time(sun_times['SS'])} | "
                f"{sun_times.get('source', 'API')}"
            )

            todays_rows = [
                item for item in intervals
                if item["start"].date() <= today <= item["end"].date()
            ]
            display_rows = display_timeline_items(todays_rows)
            update_schedule_table(schedule_table_rows(display_rows, active))
            update_timeline_canvas(display_rows, sun_times, now, active)

            if active is None:
                active_var.set("Active schedule: no matching rule")
                if update_status:
                    status_var.set("Schedule loaded, no brightness rule is active")
                return

            value_var.set(round(active["brightness_percent"]))
            active_nits = percent_to_nits(active["brightness_percent"])
            active_var.set(
                f"Active schedule: {active['name']} | "
                f"{format_schedule_time(active['start'])} - "
                f"{format_schedule_time(active['end'])} | "
                f"{format_brightness_percent(active['brightness_percent'])} | "
                f"{active_nits:,.0f} nits"
            )

            if apply_brightness_now:
                scheduled_brightness = active["brightness_percent"]
                try:
                    v = set_brightness(mode_var.get(), scheduled_brightness)
                    applied_schedule_state["key"] = schedule_key(active)
                    status_var.set(
                        f"{source} schedule applied: {format_brightness_percent(v)} at PC time {now.strftime('%I:%M:%S %p').lstrip('0')}"
                    )
                except Exception as e:
                    status_var.set(
                        f"{source} schedule loaded, but A200 brightness was not applied: {e}"
                    )
            else:
                if update_status:
                    status_var.set(
                        f"{source} schedule refreshed at PC time {now.strftime('%I:%M:%S %p').lstrip('0')}"
                    )
        except Exception as e:
            if show_error:
                messagebox.showerror("Schedule Error", str(e))
            if update_status:
                status_var.set(f"Schedule failed: {e}")

    def schedule_auto_refresh():
        try:
            config = load_schedule_config()
            refresh_seconds = parse_refresh_seconds(config)
        except Exception as e:
            status_var.set(f"Auto refresh config failed: {e}")
            refresh_seconds = 15

        if refresh_seconds <= 0:
            auto_var.set("Auto refresh: off")
            return

        auto_var.set(f"Auto refresh: every {refresh_seconds:g} seconds")

        def run_auto_refresh():
            auto_state["count"] += 1
            refresh_schedule(
                apply_brightness_now=False,
                show_error=False,
                source="Auto",
                update_status=True,
            )
            auto_var.set(
                f"Auto refresh: every {refresh_seconds:g} seconds | "
                f"checks: {auto_state['count']}"
            )
            schedule_auto_refresh()

        root.after(int(refresh_seconds * 1000), run_auto_refresh)

    def apply_clock_snapshot(
        clock_text,
        active_text,
        sun_text,
        sun_times,
        table_rows,
        timeline_items,
        active_brightness,
        active,
        current_time,
        refresh_seconds,
    ):
        auto_state["pc_time_count"] += 1
        if active_brightness is not None:
            value_var.set(round(active_brightness))
        clock_var.set(
            f"{clock_text} | "
            f"PC time checks: {auto_state['pc_time_count']} | "
            f"display refresh every {refresh_seconds:g} seconds"
        )
        sun_var.set(sun_text)
        active_var.set(active_text)
        update_schedule_table(table_rows)
        update_timeline_canvas(timeline_items, sun_times, current_time, active)
        if active is None:
            return

        current_key = schedule_key(active)
        if current_key == applied_schedule_state["key"]:
            return

        try:
            v = set_brightness(mode_var.get(), active["brightness_percent"])
            applied_schedule_state["key"] = current_key
            status_var.set(
                f"PC time schedule applied: {format_brightness_percent(v)} for {active['name']}"
            )
        except Exception as e:
            status_var.set(
                f"PC time found active schedule, but A200 brightness was not applied: {e}"
            )

    def build_clock_snapshot():
        # Task: build GUI text/table/timeline values from PC time without
        # touching Tkinter widgets from the background thread.
        refresh_seconds = 15
        config = load_schedule_config()
        refresh_seconds = parse_pc_time_refresh_seconds(config)
        if refresh_seconds <= 0:
            refresh_seconds = 15

        now = get_pc_now(config)
        today = now.date()
        sun_times = fetch_sun_times(config, today)
        intervals = build_schedule_intervals(config, today, sun_times)
        active = find_active_interval(intervals, now)

        # Same sunrise/sunset data format used by manual and auto refresh.
        sun_text = (
            f"{config['location'].get('name', 'Location')} | "
            f"{today.isoformat()} | "
            f"SR {format_schedule_time(sun_times['SR'])} | "
            f"SS {format_schedule_time(sun_times['SS'])} | "
            f"{sun_times.get('source', 'API')}"
        )
        clock_text = (
            "PC time used for schedule: "
            f"{now.strftime('%Y-%m-%d %I:%M:%S %p %Z').replace(' 0', ' ')}"
        )
        todays_rows = [
            item for item in intervals
            if item["start"].date() <= today <= item["end"].date()
        ]
        timeline_items = display_timeline_items(todays_rows)
        table_rows = schedule_table_rows(timeline_items, active)

        if active is None:
            active_text = "Active schedule: no matching rule"
            active_brightness = None
            active_snapshot = None
        else:
            active_brightness = active["brightness_percent"]
            active_snapshot = active
            active_nits = percent_to_nits(active["brightness_percent"])
            active_text = (
                f"Active schedule: {active['name']} | "
                f"{format_schedule_time(active['start'])} - "
                f"{format_schedule_time(active['end'])} | "
                f"{format_brightness_percent(active['brightness_percent'])} | "
                f"{active_nits:,.0f} nits"
            )

        return clock_text, active_text, sun_text, sun_times, table_rows, timeline_items, active_brightness, active_snapshot, now, refresh_seconds

    def pc_time_refresh_loop():
        while not stop_event.is_set():
            try:
                snapshot = build_clock_snapshot()
                root.after(0, apply_clock_snapshot, *snapshot)
                refresh_seconds = snapshot[-1]
            except Exception as e:
                root.after(0, clock_var.set, f"Current time failed: {e}")
                refresh_seconds = 15

            stop_event.wait(refresh_seconds)

    def stop_background_work():
        stop_event.set()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", stop_background_work)

    button_frame = tk.Frame(frame, bg=APP_BG)
    button_frame.pack(anchor=tk.W, pady=(0, 8))
    # Task buttons: manual set/read controls plus schedule refresh.
    tk.Button(button_frame, text="Set Brightness", command=apply_brightness, bg=PANEL_BG, fg=TEXT_LIGHT, activebackground=PANEL_BG, activeforeground=TEXT_LIGHT).pack(side=tk.LEFT, padx=4)
    tk.Button(button_frame, text="Get Brightness", command=read_brightness, bg=PANEL_BG, fg=TEXT_LIGHT, activebackground=PANEL_BG, activeforeground=TEXT_LIGHT).pack(side=tk.LEFT, padx=4)
    tk.Button(button_frame, text="Get Color Temp", command=read_display_color_temperature, bg=PANEL_BG, fg=TEXT_LIGHT, activebackground=PANEL_BG, activeforeground=TEXT_LIGHT).pack(side=tk.LEFT, padx=4)
    tk.Button(button_frame, text="Refresh Schedule", command=refresh_schedule, bg=PANEL_BG, fg=TEXT_LIGHT, activebackground=PANEL_BG, activeforeground=TEXT_LIGHT).pack(side=tk.LEFT, padx=4)

    ttk.Separator(frame).pack(fill=tk.X, pady=6)

    # Status display area: sunrise/sunset, color temperature, PC time,
    # and the currently active schedule rule.
    tk.Label(
        frame,
        textvariable=sun_var,
        bg=APP_BG,
        fg=TEXT_LIGHT,
        font=("Arial", 14, "bold"),
    ).pack(anchor=tk.W)
    tk.Label(frame, textvariable=temp_var, bg=APP_BG, fg=TEXT_LIGHT, wraplength=920).pack(anchor=tk.W, pady=(4, 0))
    tk.Label(frame, textvariable=clock_var, bg=APP_BG, fg=TEXT_LIGHT, wraplength=920).pack(anchor=tk.W, pady=(4, 0))
    tk.Label(frame, textvariable=active_var, bg=APP_BG, fg=TEXT_LIGHT, wraplength=920).pack(anchor=tk.W, pady=(6, 8))

    # Schedule table: resolved daily rules before they are drawn on the timeline.
    tk.Label(
        frame,
        text="Signage schedule",
        bg=APP_BG,
        fg=TEXT_LIGHT,
        font=("Arial", 11, "bold"),
    ).pack(anchor=tk.CENTER)
    schedule_table = tk.Frame(
        frame,
        bg=SURFACE_BG,
        highlightbackground="#777777",
        highlightthickness=1,
    )
    schedule_table.pack(fill=tk.X, anchor=tk.CENTER, pady=(0, 8))

    # Timeline canvas: visual schedule strip with SR/SS markers.
    tk.Label(
        frame,
        text="Presentable timeline",
        bg=APP_BG,
        fg=TEXT_LIGHT,
        font=("Arial", 11, "bold"),
    ).pack(anchor=tk.CENTER)
    timeline_canvas = tk.Canvas(
        frame,
        height=132,
        background=TIMELINE_STYLE["background"],
        highlightthickness=0,
    )
    timeline_canvas.pack(fill=tk.X, padx=24, pady=(0, 8))
    timeline_canvas.bind("<Configure>", draw_timeline_canvas)

    # Reference table: measured Percent -> Nits values used for estimates.
    reference_frame = tk.Frame(frame, bg=APP_BG)
    reference_frame.pack(anchor=tk.W, pady=(0, 8))
    tk.Label(
        reference_frame,
        text="Reference: % \u2192 Nits",
        bg=APP_BG,
        fg=TEXT_LIGHT,
        font=("Arial", 11, "bold"),
    ).pack(anchor=tk.W)
    ref_table = tk.Frame(
        reference_frame,
        bg=SURFACE_BG,
        highlightbackground="#777777",
        highlightthickness=1,
    )
    ref_table.pack(anchor=tk.W)

    ref_percent_labels = ["%"] + [f"{percent}%" for percent, _ in REFERENCE_NIT_ROWS]
    ref_nits_labels = ["Nits"] + [f"{nits:,.0f}" for _, nits in REFERENCE_NIT_ROWS]
    for row_index, row_values in enumerate((ref_percent_labels, ref_nits_labels)):
        for column_index, value in enumerate(row_values):
            bg = SURFACE_HEADER_BG if column_index == 0 else SURFACE_BG
            label = tk.Label(
                ref_table,
                text=value,
                bg=bg,
                fg=TEXT_LIGHT,
                font=("Arial", 10, "bold" if column_index == 0 else "normal"),
                padx=8,
                pady=6,
                width=8,
                anchor=tk.CENTER,
            )
            label.grid(row=row_index, column=column_index, sticky="nsew")

    tk.Label(frame, textvariable=auto_var, bg=APP_BG, fg=TEXT_LIGHT, wraplength=920).pack(anchor=tk.W, pady=(4, 0))
    tk.Label(frame, textvariable=pid_var, bg=APP_BG, fg=TEXT_LIGHT, wraplength=920).pack(anchor=tk.W)
    tk.Label(frame, textvariable=status_var, bg=APP_BG, fg=TEXT_LIGHT, wraplength=920).pack(anchor=tk.W, pady=(2, 0))
    tk.Label(
        frame,
        text=APP_VERSION,
        bg=APP_BG,
        fg="#bdbdbd",
        font=("Arial", 9, "bold"),
    ).pack(anchor=tk.E, pady=(0, 0))

    try:
        config = load_schedule_config()
        refresh_schedule(
            apply_brightness_now=config.get("apply_schedule_on_startup", True),
            show_error=False,
            source="Startup",
            update_status=True,
        )
    except Exception as e:
        status_var.set(f"Startup schedule failed: {e}")

    schedule_auto_refresh()
    threading.Thread(target=pc_time_refresh_loop, daemon=True).start()

    root.mainloop()

if __name__ == "__main__":
    create_gui()
