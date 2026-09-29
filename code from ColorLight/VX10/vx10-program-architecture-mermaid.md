# VX10 Program Architecture

This document explains the architecture of the VX10 brightness control program using Mermaid diagrams.

The current project has two main Python entry points:

- `VX10-brightness -2 (protocol).py`: the main Tkinter desktop app and VX10 protocol/schedule engine.
- `vx10_web_app.py`: a small HTTP server that imports the protocol module and exposes browser/API endpoints.

The shared data/config files are:

- `vx10_brightness_schedule.json`
- `Civil Twilight (Toronto).json`
- `Company_logo.png`

> Note: `vx10_web_app.py` expects a `web/` folder for static browser files, but that folder is not currently present in this repo root.

## 1. High-Level System Architecture

```mermaid
flowchart LR
    User[User / Operator]
    Browser[Browser UI]
    WebApp[vx10_web_app.py\nThreadingHTTPServer]
    TkApp[VX10-brightness -2\nTkinter Desktop App]
    Protocol[VX10 Protocol Module\nshared functions]
    ScheduleJson[(vx10_brightness_schedule.json)]
    TwilightJson[(Civil Twilight Toronto JSON)]
    SunAPI[Optional Sunrise/Sunset API]
    LocalCalc[Local Sun Calculation]
    VX10HTTP[VX10 HTTP API\nbrightness/color temp]
    TCP[TCP Socket\nport 6000]
    UDP[UDP Socket\nport 6001]
    VX10[Colorlight VX10 Controller]
    Display[LED Display]

    User --> TkApp
    User --> Browser
    Browser --> WebApp

    WebApp --> Protocol
    TkApp --> Protocol

    Protocol --> ScheduleJson
    Protocol --> TwilightJson
    Protocol --> SunAPI
    Protocol --> LocalCalc

    Protocol --> VX10HTTP
    Protocol --> TCP
    Protocol --> UDP

    VX10HTTP --> VX10
    TCP --> VX10
    UDP --> VX10
    VX10 --> Display
```

## 2. Main Module Responsibilities

```mermaid
flowchart TB
    subgraph ProtocolFile["VX10-brightness -2 (protocol).py"]
        Config[Config Loading\nload_schedule_config\nget_network_config]
        Time[Time + Sun Resolver\nget_pc_now\nfetch_sun_times\nfallback_sun_times]
        Schedule[Schedule Engine\nbuild_schedule_intervals\nfind_active_interval]
        Brightness[Brightness Logic\nset_brightness\nget_brightness\npercent_to_nits]
        Network[Network Protocol\nbuild_frame\nsend_tcp\nsend_udp\nsend_command]
        HTTP[VX10 HTTP Reader\nget_display_color_temperature]
        DesktopGUI[Tkinter GUI\ncreate_gui]
    end

    subgraph WebFile["vx10_web_app.py"]
        Importer[Dynamic Import\nload_vx10_module]
        StateAPI[State Builder\nbuild_state]
        Handler[HTTP Handler\nVX10WebHandler]
        Server[ThreadingHTTPServer\nmain]
    end

    DesktopGUI --> Config
    DesktopGUI --> Schedule
    DesktopGUI --> Brightness
    DesktopGUI --> HTTP

    Importer --> Config
    StateAPI --> Config
    StateAPI --> Time
    StateAPI --> Schedule
    StateAPI --> Brightness
    Handler --> StateAPI
    Handler --> Brightness
    Handler --> HTTP
    Server --> Handler

    Brightness --> Network
```

## 3. Desktop App Flow

The desktop app starts from:

```python
if __name__ == "__main__":
    create_gui()
```

```mermaid
sequenceDiagram
    participant User
    participant GUI as Tkinter GUI
    participant Config as Schedule Config
    participant Sun as Sun Resolver
    participant Engine as Schedule Engine
    participant Protocol as VX10 Protocol
    participant VX10 as VX10 Controller

    User->>GUI: Open desktop app
    GUI->>GUI: acquire_single_instance_lock()
    GUI->>Config: load_schedule_config()
    GUI->>Sun: fetch_sun_times(config, today)
    Sun-->>GUI: SR / SS times
    GUI->>Engine: build_schedule_intervals()
    GUI->>Engine: find_active_interval()
    Engine-->>GUI: active schedule rule
    GUI->>GUI: update labels, table, timeline, nits
    alt Apply schedule on startup or active rule changed
        GUI->>Protocol: set_brightness(mode, percent)
        Protocol->>VX10: TCP or UDP framed command
        VX10-->>Protocol: optional reply
        Protocol-->>GUI: applied brightness percent
    end
```

## 4. Web App Flow

The web app starts from:

```python
if __name__ == "__main__":
    main()
```

`vx10_web_app.py` dynamically imports the main protocol file:

```python
APP_FILE = BASE_DIR / "VX10-brightness -2 (protocol).py"
```

```mermaid
sequenceDiagram
    participant Browser
    participant Web as vx10_web_app.py
    participant Protocol as Imported VX10 Module
    participant Config as JSON Config
    participant VX10 as VX10 Controller

    Browser->>Web: GET /
    Web-->>Browser: static index.html from web folder

    Browser->>Web: GET /api/state
    Web->>Protocol: load_schedule_config()
    Web->>Protocol: get_pc_now(config)
    Web->>Protocol: fetch_sun_times(config, today)
    Web->>Protocol: build_schedule_intervals()
    Web->>Protocol: find_active_interval()
    Web->>Protocol: percent_to_nits()
    Protocol->>Config: read vx10_brightness_schedule.json
    Web-->>Browser: JSON state payload

    Browser->>Web: POST /api/brightness
    Web->>Protocol: set_brightness(mode, percent)
    Protocol->>VX10: send TCP/UDP command
    VX10-->>Protocol: optional reply
    Web-->>Browser: JSON brightness result
```

## 5. Schedule Calculation Flow

```mermaid
flowchart TD
    Start[Need current schedule state]
    Load[load_schedule_config]
    Now[get_pc_now]
    Sun[fetch_sun_times]
    ApiEnabled{Sun API enabled?}
    Api[Call Sunrise/Sunset API]
    Local[Local astronomical calculation]
    Monthly[Monthly civil twilight lookup]
    Fixed[Fixed fallback_sun_times]
    Build[build_schedule_intervals]
    Active[find_active_interval]
    Nits[percent_to_nits]
    UI[Return GUI/API display data]

    Start --> Load
    Load --> Now
    Now --> Sun
    Sun --> ApiEnabled
    ApiEnabled -->|Yes| Api
    ApiEnabled -->|No or failed| Local
    Api -->|Success| Build
    Api -->|Failed| Local
    Local -->|Success| Build
    Local -->|Failed| Monthly
    Monthly -->|Success| Build
    Monthly -->|Failed| Fixed
    Fixed --> Build
    Build --> Active
    Active --> Nits
    Nits --> UI
```

## 6. Brightness Command Flow

```mermaid
flowchart TD
    UserValue[Brightness percent\n0 to 100]
    Normalize[normalize_brightness_percent]
    Raw[Convert to raw value\nround percent * 255 / 100]
    Command[Build command\n303xxx]
    Frame[build_frame\nSTX + protocol flag + command + ETX + LRC]
    Mode{Mode}
    TCP[send_tcp]
    UDP[send_udp]
    VX10[VX10 Controller]
    Reply[Optional reply]
    Status[Update GUI/API status]

    UserValue --> Normalize
    Normalize --> Raw
    Raw --> Command
    Command --> Frame
    Frame --> Mode
    Mode -->|TCP| TCP
    Mode -->|UDP| UDP
    TCP --> VX10
    UDP --> VX10
    VX10 --> Reply
    Reply --> Status
```

The protocol flags are:

```python
FLAGS = {
    "TCP": 0x11,
    "UDP": 0x12,
}
```

The frame format is:

```text
0x02 + protocol flag + ASCII command + 0x03 + 0x32
```

## 7. API Endpoints in `vx10_web_app.py`

```mermaid
flowchart LR
    Browser[Browser / Client]
    Handler[VX10WebHandler]
    State[/GET /api/state/]
    BrightRead[/GET /api/brightness?mode=TCP/]
    BrightWrite[/POST /api/brightness/]
    ColorTemp[/GET /api/color-temp/]
    Static[Static files\n/, JS, CSS, logo]

    Browser --> Handler
    Handler --> State
    Handler --> BrightRead
    Handler --> BrightWrite
    Handler --> ColorTemp
    Handler --> Static

    State --> BuildState[build_state]
    BrightRead --> GetBrightness[get_brightness]
    BrightWrite --> SetBrightness[set_brightness]
    ColorTemp --> GetTemp[get_display_color_temperature]
```

Endpoint summary:

| Endpoint | Method | Purpose |
| --- | --- | --- |
| `/` | `GET` | Serves `web/index.html` |
| `/api/state` | `GET` | Returns current schedule, sun times, active rule, nits, and network config |
| `/api/brightness?mode=TCP` | `GET` | Reads current VX10 brightness using TCP or UDP |
| `/api/brightness` | `POST` | Sets VX10 brightness from JSON body |
| `/api/color-temp` | `GET` | Reads brightness/color temperature from VX10 HTTP API |
| `/company_logo.png` | `GET` | Serves company logo |

## 8. Important Runtime Files

```mermaid
flowchart TB
    Schedule[(vx10_brightness_schedule.json)]
    Twilight[(Civil Twilight Toronto JSON)]
    Lock[(.vx10_brightness_schedule.lock)]
    Logo[(Company_logo.png)]
    WebFolder[(web folder\nexpected by web app)]

    Schedule --> Config[Schedule, location,\nnetwork, refresh settings]
    Twilight --> SunFallback[Monthly sunrise/sunset fallback]
    Lock --> SingleInstance[Prevents multiple desktop app instances]
    Logo --> GUIBranding[Logo in desktop/web UI]
    WebFolder --> StaticUI[Browser frontend files]
```

| File | Used by | Purpose |
| --- | --- | --- |
| `vx10_brightness_schedule.json` | Desktop app and web app | Main schedule, location, network, and refresh configuration |
| `Civil Twilight (Toronto).json` | Protocol module | Monthly sunrise/sunset fallback data |
| `.vx10_brightness_schedule.lock` | Desktop app | Prevents multiple desktop app instances |
| `Company_logo.png` | Desktop/web app | UI branding/logo |
| `web/` | Web app | Static frontend folder expected by `vx10_web_app.py` |

## 9. Summary

The program is built around one shared protocol/schedule module:

```text
VX10-brightness -2 (protocol).py
```

That module handles:

- VX10 TCP/UDP command framing
- brightness reads/writes
- VX10 HTTP color temperature reads
- schedule JSON loading
- sunrise/sunset resolution
- active rule calculation
- nits estimation
- Tkinter desktop UI

The web app:

```text
vx10_web_app.py
```

imports that same module and exposes the same behavior through local HTTP endpoints.
