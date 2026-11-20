
import tkinter as tk
import math
import time

# =====================================
# GRIFFIN DESKTOP INTERFACE
# =====================================

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

status = "ONLINE"
phase = 0

# =====================================
# HEADER
# =====================================

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
    text="PERSONAL AI SYSTEM  •  DESKTOP",
    font=("Segoe UI", 9),
    fg=MUTED,
    bg=BG
).pack(side="right", pady=12)

tk.Frame(root, bg="#1d3550", height=1).pack(fill="x", padx=35)

# =====================================
# MAIN LAYOUT
# =====================================

main = tk.Frame(root, bg=BG)
main.pack(fill="both", expand=True, padx=35, pady=25)

left = tk.Frame(main, bg=BG)
left.pack(side="left", fill="both", expand=True)

right = tk.Frame(
    main,
    bg=PANEL,
    width=330
)
right.pack(side="right", fill="y", padx=(25, 0))
right.pack_propagate(False)

# =====================================
# CENTRAL ORB
# =====================================

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

    pulse = math.sin(phase) * 8

    # Outer rings
    for radius, color, width in [
        (145 + pulse, "#123451", 2),
        (125 - pulse / 2, "#17618b", 2),
        (105 + pulse / 3, "#168dc7", 2),
        (83 - pulse / 4, BLUE, 2)
    ]:

        canvas.create_oval(
            center_x - radius,
            center_y - radius,
            center_x + radius,
            center_y + radius,
            outline=color,
            width=width,
            tags="orb"
        )

    # Core
    canvas.create_oval(
        center_x - 65,
        center_y - 65,
        center_x + 65,
        center_y + 65,
        fill="#102d48",
        outline=CYAN,
        width=2,
        tags="orb"
    )

    canvas.create_oval(
        center_x - 43,
        center_y - 43,
        center_x + 43,
        center_y + 43,
        fill="#174a70",
        outline=BLUE,
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

# =====================================
# STATUS
# =====================================

status_label = tk.Label(
    left,
    text="● SYSTEM ONLINE",
    font=("Segoe UI", 12, "bold"),
    fg=CYAN,
    bg=BG
)
status_label.pack(pady=(0, 8))

subtitle = tk.Label(
    left,
    text="Awaiting your command",
    font=("Segoe UI", 10),
    fg=MUTED,
    bg=BG
)
subtitle.pack()

# =====================================
# CONVERSATION PANEL
# =====================================

tk.Label(
    right,
    text="CONVERSATION",
    font=("Segoe UI", 11, "bold"),
    fg=CYAN,
    bg=PANEL
).pack(anchor="w", padx=22, pady=(25, 12))

conversation = tk.Text(
    right,
    bg=PANEL,
    fg=WHITE,
    font=("Segoe UI", 10),
    wrap="word",
    relief="flat",
    borderwidth=0,
    padx=15,
    pady=10,
    insertbackground=WHITE
)

conversation.pack(
    fill="both",
    expand=True,
    padx=10,
    pady=(0, 15)
)

conversation.insert(
    "end",
    "GRIFFIN\nSystem initialised.\n\n"
    "Awaiting interface connection...\n"
)

conversation.configure(state="disabled")

# =====================================
# FOOTER
# =====================================

footer = tk.Frame(root, bg=BG)
footer.pack(fill="x", padx=35, pady=(0, 20))

tk.Label(
    footer,
    text="GRIFFIN CORE  •  LOCAL MODE",
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

# =====================================
# START
# =====================================

root.mainloop()
