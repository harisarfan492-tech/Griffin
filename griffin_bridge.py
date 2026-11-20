
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import json
import os
import re
import subprocess

# ==========================================
# GRIFFIN CONFIGURATION
# ==========================================

HOST = "127.0.0.1"
PORT = 8765

WORKSPACE = str(Path(__file__).resolve().parent / "workspace")

APPLICATIONS = {
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "firefox": r"C:\Program Files\Mozilla Firefox\firefox.exe",
    "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
}


# ==========================================
# UTILITIES
# ==========================================

def normalize(name):
    return re.sub(r"[^a-z0-9]", "", name.lower())


# ==========================================
# APPLICATION DISCOVERY
# ==========================================

def get_start_menu_apps():

    folders = [
        Path(os.environ["APPDATA"]) /
        "Microsoft/Windows/Start Menu/Programs",

        Path(os.environ["PROGRAMDATA"]) /
        "Microsoft/Windows/Start Menu/Programs"
    ]

    apps = {}

    for folder in folders:

        if not folder.exists():
            continue

        for shortcut in folder.rglob("*.lnk"):

            name = shortcut.stem.strip()

            if name:
                apps[normalize(name)] = {
                    "name": name,
                    "type": "shortcut",
                    "target": str(shortcut)
                }

    return apps


def get_store_apps():

    command = (
        "Get-StartApps | "
        "Select-Object Name, AppID | "
        "ConvertTo-Json -Compress"
    )

    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-Command",
            command
        ],
        capture_output=True,
        text=True,
        timeout=15
    )

    if result.returncode != 0 or not result.stdout.strip():
        return {}

    try:

        data = json.loads(result.stdout)

        if isinstance(data, dict):
            data = [data]

        apps = {}

        for app in data:

            name = (app.get("Name") or "").strip()
            app_id = (app.get("AppID") or "").strip()

            if name and app_id:

                apps[normalize(name)] = {
                    "name": name,
                    "type": "store",
                    "target": app_id
                }

        return apps

    except (json.JSONDecodeError, AttributeError):
        return {}


# ==========================================
# OPEN APPLICATION
# ==========================================

def launch_application(requested_name):

    requested = normalize(requested_name)

    if not requested:
        return False, "Please specify an application."

    apps = get_start_menu_apps()
    apps.update(get_store_apps())

    if requested in apps:

        match = apps[requested]

    else:

        matches = [
            app for key, app in apps.items()
            if requested in key or key in requested
        ]

        if len(matches) == 0:

            if requested in APPLICATIONS:

                executable = APPLICATIONS[requested]

                if "\\" in executable or "/" in executable:

                    if not Path(executable).exists():
                        return False, requested_name + " was not found."

                subprocess.Popen([executable], shell=False)

                return True, requested_name + " launched."

            return False, requested_name + " was not found."

        if len(matches) > 1:

            names = sorted(set(app["name"] for app in matches))

            return False, (
                "Multiple applications matched: "
                + ", ".join(names[:10])
            )

        match = matches[0]

    if match["type"] == "shortcut":

        os.startfile(match["target"])

    else:

        subprocess.Popen(
            [
                "explorer.exe",
                "shell:AppsFolder\\" + match["target"]
            ],
            shell=False
        )

    return True, match["name"] + " launched."


# ==========================================
# RUNNING APPLICATION DETECTION
# ==========================================

def get_running_applications():

    command = (
        "Get-Process | "
        "Where-Object { $_.MainWindowTitle } | "
        "Select-Object ProcessName, Id, MainWindowTitle | "
        "ConvertTo-Json -Compress"
    )

    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-Command",
            command
        ],
        capture_output=True,
        text=True,
        timeout=15
    )

    if result.returncode != 0:
        raise RuntimeError("Could not retrieve running applications.")

    if not result.stdout.strip():
        return []

    apps = json.loads(result.stdout)

    if isinstance(apps, dict):
        apps = [apps]

    return apps


# ==========================================
# CLOSE APPLICATION GRACEFULLY
# ==========================================

def close_application(requested_name):

    requested = normalize(requested_name)

    if not requested:
        return False, "Please specify an application."

    apps = get_running_applications()

    matches = [
        app for app in apps
        if requested == normalize(app["ProcessName"])
        or requested == normalize(app["MainWindowTitle"])
    ]

    if not matches:

        matches = [
            app for app in apps
            if requested in normalize(app["ProcessName"])
            or requested in normalize(app["MainWindowTitle"])
        ]

    if not matches:

        return False, (
            requested_name +
            " is not currently running."
        )

    if len(matches) > 1:

        names = [
            app["MainWindowTitle"]
            for app in matches
        ]

        return False, (
            "Multiple windows matched: "
            + ", ".join(names[:10])
        )

    target = matches[0]

    command = (
        "Get-Process -Id "
        + str(int(target["Id"]))
        + " | ForEach-Object { $_.CloseMainWindow() }"
    )

    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-Command",
            command
        ],
        capture_output=True,
        text=True,
        timeout=15
    )

    if result.returncode != 0:

        return False, (
            "Windows could not close "
            + requested_name
            + "."
        )

    return True, (
        "Sent a graceful close request to "
        + target["MainWindowTitle"]
        + ". The application may ask you to save your work."
    )


# ==========================================
# FILE OPERATIONS
# ==========================================

def file_operation(action, path="", content=""):

    try:

        base = Path(WORKSPACE).resolve()
        full_path = (base / path).resolve()

        # Prevent access outside Griffin's workspace
        try:
            full_path.relative_to(base)
        except ValueError:
            return {
                "success": False,
                "message": "Access denied outside Griffin workspace."
            }

        if action == "list":

            if not full_path.is_dir():
                return {
                    "success": False,
                    "message": "Directory does not exist."
                }

            return {
                "success": True,
                "files": [
                    {
                        "name": item.name,
                        "type": "directory" if item.is_dir() else "file"
                    }
                    for item in full_path.iterdir()
                ]
            }

        elif action == "create_directory":

            full_path.mkdir(parents=True, exist_ok=True)

            return {
                "success": True,
                "message": "Directory created: " + path
            }

        elif action == "read":

            if not full_path.is_file():
                return {
                    "success": False,
                    "message": "File does not exist."
                }

            with open(full_path, "r", encoding="utf-8") as f:
                file_content = f.read()

            return {
                "success": True,
                "content": file_content
            }

        elif action == "write":

            full_path.parent.mkdir(parents=True, exist_ok=True)

            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)

            return {
                "success": True,
                "message": "File written: " + path
            }

        else:

            return {
                "success": False,
                "message": "Unknown file operation."
            }

    except Exception as error:

        return {
            "success": False,
            "message": str(error)
        }


# ==========================================
# HTTP BRIDGE
# ==========================================

class GriffinBridge(BaseHTTPRequestHandler):

    # --------------------------------------
    # JSON RESPONSE
    # --------------------------------------

    def send_json(self, status, data):

        response = json.dumps(data).encode("utf-8")

        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self.send_header("Access-Control-Allow-Origin", "http://localhost")
        self.end_headers()

        self.wfile.write(response)

    # --------------------------------------
    # GET REQUESTS
    # --------------------------------------

    def do_GET(self):

        if self.path == "/running":

            try:

                apps = get_running_applications()

                self.send_json(200, {
                    "success": True,
                    "applications": apps
                })

            except Exception as error:

                self.send_json(500, {
                    "success": False,
                    "error": str(error)
                })

            return

        self.send_json(200, {
            "status": "online",
            "system": "Griffin Windows Bridge",
            "features": [
                "Desktop application discovery",
                "Microsoft Store application discovery",
                "Running application detection",
                "Graceful application closing",
                "File creation",
                "File reading",
                "File editing",
                "Directory management"
            ]
        })

    # --------------------------------------
    # POST REQUESTS
    # --------------------------------------

    def do_POST(self):

        if self.path not in ["/open", "/close", "/file"]:

            self.send_json(404, {
                "success": False,
                "error": "Unknown endpoint"
            })

            return

        try:

            length = int(self.headers.get("Content-Length", 0))

            if length <= 0 or length > 1024 * 1024:

                self.send_json(400, {
                    "success": False,
                    "error": "Invalid request size"
                })

                return

            body = self.rfile.read(length)
            data = json.loads(body.decode("utf-8"))

            # ==================================
            # FILE OPERATIONS
            # ==================================

            if self.path == "/file":

                action = data.get("action", "")
                path = data.get("path", "")
                content = data.get("content", "")

                if not all(
                    isinstance(value, str)
                    for value in [action, path, content]
                ):

                    self.send_json(400, {
                        "success": False,
                        "error": "Invalid file operation parameters"
                    })

                    return

                result = file_operation(action, path, content)

                self.send_json(
                    200 if result.get("success") else 400,
                    result
                )

                return

            # ==================================
            # APPLICATION OPERATIONS
            # ==================================

            application = data.get("application", "")

            if not isinstance(application, str) or len(application) > 100:

                self.send_json(400, {
                    "success": False,
                    "error": "Invalid application name"
                })

                return

            if self.path == "/open":

                success, message = launch_application(
                    application.strip()
                )

            else:

                success, message = close_application(
                    application.strip()
                )

            self.send_json(
                200 if success else 404,
                {
                    "success": success,
                    "message": message
                }
            )

        except Exception as error:

            self.send_json(500, {
                "success": False,
                "error": str(error)
            })

    # --------------------------------------
    # SERVER LOGGING
    # --------------------------------------

    def log_message(self, format, *args):

        print("[GRIFFIN BRIDGE]", format % args)


# ==========================================
# START SERVER
# ==========================================

server = HTTPServer((HOST, PORT), GriffinBridge)

print("================================")
print(" GRIFFIN WINDOWS BRIDGE")
print("================================")
print("Listening on http://127.0.0.1:8765")
print("Desktop application discovery enabled.")
print("Microsoft Store discovery enabled.")
print("Running application detection enabled.")
print("Graceful application closing enabled.")
print("File operations enabled.")
print("Waiting for Griffin...")

try:

    server.serve_forever()

except KeyboardInterrupt:

    print("Shutting down Griffin Bridge...")
    server.server_close()

