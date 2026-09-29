import requests
import re

IP = "10.0.1.182"
BASE_URL = f"http://{IP}"

session = requests.Session()

KEYWORDS = [
    "rs232", "RS232",
    "serial", "Serial",
    "uart", "UART",
    "com", "COM",
    "tty", "TTY",
    "tcp", "TCP",
    "udp", "UDP",
    "socket", "Socket",
    "network", "Network",
    "ethernet", "Ethernet",
    "ip", "IP",
    "gateway",
    "mask",
    "dns",
    "port",
    "listen",
    "modbus",
    "485",
    "232",
    "rndis",
    "RNDIS"
]


def get_homepage():
    r = session.get(BASE_URL, timeout=10)
    r.raise_for_status()
    return r.text


def find_js_files(html):
    files = re.findall(r'src="([^"]+\.js)"', html)
    return sorted(set(files))


def download_js(js_file):
    url = js_file
    if not js_file.startswith("http"):
        url = BASE_URL + "/" + js_file.lstrip("/")

    print(f"Downloading: {url}")
    r = session.get(url, timeout=10)
    r.raise_for_status()
    return r.text


def extract_api_paths(text):
    paths = set()

    # /api/xxx
    paths.update(re.findall(r'/api/[A-Za-z0-9_\-./]+', text))

    # any xxx.json
    paths.update(re.findall(r'/[A-Za-z0-9_\-./]+\.json', text))

    return paths


def search_keywords(text, filename):
    print("\n" + "=" * 80)
    print(f"KEYWORD SEARCH IN {filename}")
    print("=" * 80)

    found_any = False

    for kw in KEYWORDS:
        for match in re.finditer(re.escape(kw), text):
            found_any = True
            start = max(match.start() - 120, 0)
            end = min(match.end() + 120, len(text))
            context = text[start:end].replace("\n", " ")

            print(f"\nKeyword: {kw}")
            print(context)

    if not found_any:
        print("No RS232/TCP/UDP/network keywords found.")


def test_get_endpoint(path):
    url = BASE_URL + path

    try:
        r = session.get(url, timeout=5)
        print(f"{path:<45} status={r.status_code:<4} len={len(r.text)}")

        if r.text.strip():
            print("  body:", repr(r.text[:300]))

    except Exception as e:
        print(f"{path:<45} ERROR {e}")


def main():
    html = get_homepage()

    js_files = find_js_files(html)

    print("\n" + "=" * 80)
    print("JS FILES FOUND")
    print("=" * 80)

    for f in js_files:
        print(f)

    all_paths = set()

    for js in js_files:
        text = download_js(js)

        all_paths.update(extract_api_paths(text))

        search_keywords(text, js)

    print("\n" + "=" * 80)
    print("ALL API / JSON PATHS FOUND")
    print("=" * 80)

    for p in sorted(all_paths):
        print(p)

    print("\n" + "=" * 80)
    print("JSON FILES ONLY")
    print("=" * 80)

    for p in sorted(all_paths):
        if p.endswith(".json"):
            print(p)

    print("\n" + "=" * 80)
    print("TEST GET ENDPOINTS")
    print("=" * 80)

    for p in sorted(all_paths):
        test_get_endpoint(p)


if __name__ == "__main__":
    main()