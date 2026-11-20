import os

import tkinter as tk
import math
import sounddevice as sd
import soundfile as sf
import requests
import subprocess
import numpy as np
import threading
import time
import base64
import sqlite3
from pathlib import Path
from datetime import datetime

# ==========================================
# GRIFFIN CONFIGURATION
# ==========================================

WEBHOOK_URL = os.getenv("GRIFFIN_WEBHOOK_URL", "")
FFMPEG = r"C:\ffmpeg\bin\ffmpeg.exe"

MIC = 2
SPEAKER = 5

SAMPLE_RATE = int(sd.query_devices(MIC)["default_samplerate"])

SILENCE_LIMIT = 1.2
MAX_DURATION = 20
START_TIMEOUT = 10
THRESHOLD = 0.012

# Database stored beside this Python file
HISTORY_DB = Path(__file__).resolve().parent / "griffin_history.db"

stop_event = threading.Event()
assistant_thread = None

current_mode = "IDLE"
phase = 0

# ==========================================
# DATABASE
# ==========================================

def initialize_database():

    with sqlite3.connect(HISTORY_DB) as connection:

        connection.execute("""
            CREATE TABLE IF NOT EXISTS conversation_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                message TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
        """)

        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_conversation_timestamp
            ON conversation_history(timestamp)
        """)


def save_message(role, message, timestamp):

    with sqlite3.connect(HISTORY_DB) as connection:

        connection.execute(
            """
            INSERT INTO conversation_history
            (role, message, timestamp)
            VALUES (?, ?, ?)
            """,
            (role, str(message), timestamp)
        )


def get_saved_messages():

    with sqlite3.connect(HISTORY_DB) as connection:

        return connection.execute("""
            SELECT role, message, timestamp
            FROM conversation_history
            ORDER BY id ASC
        """).fetchall()


# Create the database before starting the interface
initialize_database()


# ==========================================
# GUI SETUP
# ==========================================

root = tk.Tk()
root.title("GRIFFIN | Desktop Assistant")
root.geometry("1100x720")
root.minsize(900, 600)
root.configure(bg="#080d18")

BG = "#080d18"
PANEL = "#101a2b"
BLUE = "#29a8ff"
CYAN = "#56dcff"
WHITE = "#e8f4ff"
MUTED = "#71849e"


# ==========================================
# CONVERSATION FUNCTIONS
# ==========================================

def scroll_to_bottom():

    chat_canvas.update_idletasks()

    chat_canvas.configure(
        scrollregion=chat_canvas.bbox("all")
    )

    chat_canvas.yview_moveto(1.0)


def display_conversation(role, message, timestamp):

    def update():

        try:
            display_time = datetime.fromisoformat(
                timestamp
            ).strftime("%b %d Â· %I:%M %p")

        except ValueError:
            display_time = timestamp

        outer = tk.Frame(
            chat_inner,
            bg=PANEL
        )

        outer.pack(
            fill="x",
            padx=12,
            pady=7
        )

        is_user = role == "YOU"

        alignment = "right" if is_user else "left"

        bubble_colour = "#123c60" if is_user else "#18352f"
        name_colour = CYAN if is_user else "#54e6a5"

        bubble_column = tk.Frame(
            outer,
            bg=PANEL
        )

        bubble_column.pack(
            side=alignment,
            anchor="e" if is_user else "w"
        )

        name_label = tk.Label(
            bubble_column,
            text=role,
            font=("Segoe UI", 9, "bold"),
            fg=name_colour,
            bg=PANEL
        )

        name_label.pack(
            anchor="e" if is_user else "w",
            padx=5,
            pady=(0, 3)
        )

        bubble = tk.Label(
            bubble_column,
            text=str(message).strip(),
            font=("Segoe UI", 10),
            fg=WHITE,
            bg=bubble_colour,
            justify="left",
            wraplength=255,
            padx=13,
            pady=10
        )

        bubble.pack(
            anchor="e" if is_user else "w"
        )

        time_label = tk.Label(
            bubble_column,
            text=display_time,
            font=("Segoe UI", 8),
            fg=MUTED,
            bg=PANEL
        )

        time_label.pack(
            anchor="e" if is_user else "w",
            padx=5,
            pady=(3, 0)
        )

        root.after_idle(scroll_to_bottom)

    root.after(0, update)


def add_conversation(role, message):

    timestamp = datetime.now().isoformat(timespec="seconds")

    # Save the message without interrupting the conversation
    try:

        save_message(
            role,
            message,
            timestamp
        )

    except Exception as error:

        print("Database save error:", error)

    # Display the message
    display_conversation(
        role,
        message,
        timestamp
    )


def load_conversation_history():

    try:

        messages = get_saved_messages()

        for role, message, timestamp in messages:

            display_conversation(
                role,
                message,
                timestamp
            )

        if not messages:

            display_conversation(
                "GRIFFIN",
                "System initialised. Voice engine ready. Griffin activated. Waiting for your voice...",
                datetime.now().isoformat(timespec="seconds")
            )

        log_message(
            f"Conversation history loaded: {len(messages)} messages."
        )

    except Exception as error:

        log_message(
            "Unable to load conversation history: " + str(error)
        )


def log_message(message):

    def update():

        timestamp = datetime.now().strftime("%I:%M %p")

        system_frame = tk.Frame(
            chat_inner,
            bg=PANEL
        )

        system_frame.pack(
            fill="x",
            padx=10,
            pady=5
        )

        label = tk.Label(
            system_frame,
            text=f"â— {message}  Â·  {timestamp}",
            font=("Segoe UI", 8),
            fg=MUTED,
            bg=PANEL,
            wraplength=280,
            justify="center"
        )

        label.pack()

        root.after_idle(scroll_to_bottom)

    root.after(0, update)


# ==========================================
# STATUS DISPLAY
# ==========================================

def set_mode(mode, message=None):

    def update():

        global current_mode
        current_mode = mode

        colours = {
            "IDLE": MUTED,
            "LISTENING": CYAN,
            "THINKING": "#b18cff",
            "SPEAKING": "#54e6a5",
            "ERROR": "#ff6464"
        }

        descriptions = {
            "IDLE": "Assistant stopped",
            "LISTENING": "Listening for your voice...",
            "THINKING": "Processing your request...",
            "SPEAKING": "Griffin is speaking...",
            "ERROR": "Something went wrong"
        }

        status_label.config(
            text="â— SYSTEM " + mode,
            fg=colours[mode]
        )

        subtitle.config(
            text=message or descriptions[mode]
        )

    root.after(0, update)


# ==========================================
# VOICE DETECTION
# ==========================================

def listen():

    log_message("Waiting for your voice...")

    chunk_duration = 0.03
    chunk_size = int(SAMPLE_RATE * chunk_duration)

    frames = []
    speaking = False
    silence_time = 0
    elapsed = 0

    try:

        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
            device=MIC,
            blocksize=chunk_size
        ) as stream:

            while elapsed < MAX_DURATION:

                if stop_event.is_set():
                    return False

                audio, overflowed = stream.read(chunk_size)

                level = float(np.sqrt(np.mean(audio ** 2)))

                elapsed += chunk_duration

                if level > THRESHOLD:

                    if not speaking:
                        speaking = True
                        set_mode("LISTENING", "I can hear you...")

                    silence_time = 0
                    frames.append(audio.copy())

                elif speaking:

                    frames.append(audio.copy())
                    silence_time += chunk_duration

                    if silence_time >= SILENCE_LIMIT:
                        break

                elif elapsed >= START_TIMEOUT:

                    return False

        if not frames:
            return False

        recording = np.concatenate(frames, axis=0)

        sf.write(
            "griffin_input.wav",
            recording,
            SAMPLE_RATE
        )

        subprocess.run(
            [
                FFMPEG,
                "-y",
                "-i", "griffin_input.wav",
                "-c:a", "aac",
                "-b:a", "128k",
                "griffin_input.m4a"
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True
        )

        log_message("Voice recording captured.")
        return True

    except Exception as error:

        log_message("Microphone error: " + str(error))
        set_mode("ERROR", "Microphone problem")
        stop_event.set()
        return False


# ==========================================
# SEND AUDIO TO GRIFFIN
# ==========================================

def talk():

    try:

        set_mode("THINKING")
        log_message("Sending request to Griffin...")

        with open("griffin_input.m4a", "rb") as audio:

            response = requests.post(
                WEBHOOK_URL,
                files={
                    "audio0": (
                        "griffin.m4a",
                        audio,
                        "audio/mp4"
                    )
                },
                timeout=180
            )

        response.raise_for_status()

        payload = response.json()

        transcript = payload["transcript"]
        griffin_reply = payload["response"]
        audio_base64 = payload["audio"]

        if not audio_base64:
            raise Exception("Griffin returned no audio.")

        audio_bytes = base64.b64decode(audio_base64)

        with open("griffin_response.mp3", "wb") as file:
            file.write(audio_bytes)

        add_conversation("YOU", transcript)
        add_conversation("GRIFFIN", griffin_reply)

        subprocess.run(
            [
                FFMPEG,
                "-y",
                "-i", "griffin_response.mp3",
                "-f", "wav",
                "-acodec", "pcm_s16le",
                "-ar", "44100",
                "griffin_response.wav"
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True
        )

        audio_data, rate = sf.read(
            "griffin_response.wav",
            dtype="float32"
        )

        set_mode("SPEAKING")
        log_message("Griffin is speaking.")

        sd.play(
            audio_data,
            rate,
            device=SPEAKER
        )

        sd.wait()

        log_message("Response completed.")

    except Exception as error:

        log_message("Response error: " + str(error))
        set_mode("ERROR", "Unable to complete request")
        time.sleep(2)


# ==========================================
# ASSISTANT LOOP
# ==========================================

def assistant_loop():

    while not stop_event.is_set():

        set_mode("LISTENING")

        if listen():

            if stop_event.is_set():
                break

            talk()

        else:

            if not stop_event.is_set():
                time.sleep(0.2)

    set_mode("IDLE")


# ==========================================
# START AND STOP CONTROLS
# ==========================================

def start_assistant():

    global assistant_thread

    if assistant_thread and assistant_thread.is_alive():
        return

    stop_event.clear()

    assistant_thread = threading.Thread(
        target=assistant_loop,
        daemon=True
    )

    assistant_thread.start()

    log_message("Griffin activated.")


def stop_assistant():

    stop_event.set()

    set_mode("IDLE", "Griffin is shutting down...")

    log_message("Shutdown requested.")


# ==========================================
# HEADER
# ==========================================

header = tk.Frame(root, bg=BG)
header.pack(fill="x", padx=35, pady=25)

tk.Label(
    header,
    text="G R I F F I N",
    font=("Segoe UI", 23, "bold"),
    fg=WHITE,
    bg=BG
).pack(side="left")

tk.Label(
    header,
    text="PERSONAL AI SYSTEM  â€¢  DESKTOP",
    font=("Segoe UI", 9),
    fg=MUTED,
    bg=BG
).pack(side="right", pady=12)

tk.Frame(
    root,
    bg="#1d3550",
    height=1
).pack(fill="x", padx=35)


# ==========================================
# MAIN LAYOUT
# ==========================================

main = tk.Frame(root, bg=BG)
main.pack(fill="both", expand=True, padx=35, pady=25)

left = tk.Frame(main, bg=BG)
left.pack(side="left", fill="both", expand=True)

right = tk.Frame(
    main,
    bg=PANEL,
    width=350
)

right.pack(side="right", fill="y", padx=(25, 0))
right.pack_propagate(False)


# ==========================================
# ANIMATED ORB
# ==========================================

canvas = tk.Canvas(
    left,
    width=430,
    height=430,
    bg=BG,
    highlightthickness=0
)

canvas.pack(expand=True)

center_x = 215
center_y = 215


def draw_orb():

    global phase

    canvas.delete("orb")

    colours = {
        "IDLE": "#123451",
        "LISTENING": CYAN,
        "THINKING": "#b18cff",
        "SPEAKING": "#54e6a5",
        "ERROR": "#ff6464"
    }

    accent = colours[current_mode]
    pulse = math.sin(phase) * 9

    for radius, width in [
        (145 + pulse, 2),
        (125 - pulse / 2, 2),
        (105 + pulse / 3, 2),
        (83 - pulse / 4, 3)
    ]:

        canvas.create_oval(
            center_x - radius,
            center_y - radius,
            center_x + radius,
            center_y + radius,
            outline=accent,
            width=width,
            tags="orb"
        )

    canvas.create_oval(
        center_x - 65,
        center_y - 65,
        center_x + 65,
        center_y + 65,
        fill="#102d48",
        outline=accent,
        width=2,
        tags="orb"
    )

    canvas.create_oval(
        center_x - 43,
        center_y - 43,
        center_x + 43,
        center_y + 43,
        fill="#174a70",
        outline=accent,
        width=2,
        tags="orb"
    )

    canvas.create_text(
        center_x,
        center_y,
        text="G",
        font=("Segoe UI", 45, "bold"),
        fill=WHITE,
        tags="orb"
    )

    phase += 0.06
    root.after(30, draw_orb)


draw_orb()


# ==========================================
# STATUS DISPLAY
# ==========================================

status_label = tk.Label(
    left,
    text="â— SYSTEM IDLE",
    font=("Segoe UI", 12, "bold"),
    fg=MUTED,
    bg=BG
)

status_label.pack(pady=(0, 8))

subtitle = tk.Label(
    left,
    text="Awaiting activation",
    font=("Segoe UI", 10),
    fg=MUTED,
    bg=BG
)

subtitle.pack()


# ==========================================
# CONTROL BUTTONS
# ==========================================

controls = tk.Frame(left, bg=BG)
controls.pack(pady=20)

start_button = tk.Button(
    controls,
    text="START GRIFFIN",
    command=start_assistant,
    bg="#123c60",
    fg=WHITE,
    activebackground="#1b5b87",
    activeforeground=WHITE,
    font=("Segoe UI", 10, "bold"),
    relief="flat",
    padx=22,
    pady=12,
    cursor="hand2"
)

start_button.pack(side="left", padx=8)

stop_button = tk.Button(
    controls,
    text="STOP",
    command=stop_assistant,
    bg="#38202b",
    fg=WHITE,
    activebackground="#633344",
    activeforeground=WHITE,
    font=("Segoe UI", 10, "bold"),
    relief="flat",
    padx=22,
    pady=12,
    cursor="hand2"
)

stop_button.pack(side="left", padx=8)


# ==========================================
# CHAT HEADER
# ==========================================

chat_header = tk.Frame(
    right,
    bg=PANEL
)

chat_header.pack(
    fill="x",
    padx=18,
    pady=(22, 12)
)

tk.Label(
    chat_header,
    text="CONVERSATION",
    font=("Segoe UI", 11, "bold"),
    fg=CYAN,
    bg=PANEL
).pack(anchor="w")

tk.Label(
    chat_header,
    text="Persistent conversation history",
    font=("Segoe UI", 8),
    fg=MUTED,
    bg=PANEL
).pack(anchor="w", pady=(4, 0))


# ==========================================
# SCROLLABLE CHAT AREA
# ==========================================

chat_container = tk.Frame(
    right,
    bg=PANEL
)

chat_container.pack(
    fill="both",
    expand=True,
    padx=8,
    pady=(0, 10)
)

chat_canvas = tk.Canvas(
    chat_container,
    bg=PANEL,
    highlightthickness=0
)

chat_scrollbar = tk.Scrollbar(
    chat_container,
    orient="vertical",
    command=chat_canvas.yview
)

chat_canvas.configure(
    yscrollcommand=chat_scrollbar.set
)

chat_scrollbar.pack(
    side="right",
    fill="y"
)

chat_canvas.pack(
    side="left",
    fill="both",
    expand=True
)

chat_inner = tk.Frame(
    chat_canvas,
    bg=PANEL
)

chat_window = chat_canvas.create_window(
    (0, 0),
    window=chat_inner,
    anchor="nw"
)


def update_chat_scroll(event=None):

    chat_canvas.configure(
        scrollregion=chat_canvas.bbox("all")
    )


def resize_chat_inner(event):

    chat_canvas.itemconfigure(
        chat_window,
        width=event.width
    )


chat_inner.bind(
    "<Configure>",
    update_chat_scroll
)

chat_canvas.bind(
    "<Configure>",
    resize_chat_inner
)


def mousewheel_scroll(event):

    chat_canvas.yview_scroll(
        int(-1 * (event.delta / 120)),
        "units"
    )


def enable_mousewheel(event):

    chat_canvas.bind_all(
        "<MouseWheel>",
        mousewheel_scroll
    )


def disable_mousewheel(event):

    chat_canvas.unbind_all("<MouseWheel>")


chat_canvas.bind("<Enter>", enable_mousewheel)
chat_canvas.bind("<Leave>", disable_mousewheel)


# ==========================================
# LOAD PREVIOUS CONVERSATIONS
# ==========================================

load_conversation_history()


# ==========================================
# FOOTER
# ==========================================

footer = tk.Frame(root, bg=BG)
footer.pack(fill="x", padx=35, pady=(0, 20))

tk.Label(
    footer,
    text="GRIFFIN CORE  â€¢  LOCAL MODE",
    font=("Segoe UI", 9),
    fg=MUTED,
    bg=BG
).pack(side="left")

tk.Label(
    footer,
    text="VOICE ENGINE: READY",
    font=("Segoe UI", 9),
    fg=CYAN,
    bg=BG
).pack(side="right")


# ==========================================
# SHUTDOWN
# ==========================================

def close_application():

    stop_event.set()
    root.destroy()


root.protocol("WM_DELETE_WINDOW", close_application)

root.mainloop()

