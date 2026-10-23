"""Tkinter window for the board. Plain functions, no classes.

Call build() once with the functions to run on each action, then run().
A move is a column: click anywhere in it (or its number), or type a move
(see moves.py) and press Enter.
"""

import tkinter as tk

ROWS = 5
COLUMNS = 5

PIECE = "●"  # a filled circle
COLOURS = {1: "#d62828", 2: "#e0a800"}   # red, yellow (darker yellow reads on white)
NAMES = {1: "Red", 2: "Yellow"}
HIGHLIGHT = "#ffd6d6"                    # behind the losing line
EMPTY_BG = None                          # the platform's normal button colour

MODES = ["Two player", "vs Computer (easy)", "vs Computer (hard)"]

root = None
buttons = []        # 25 squares, row by row from the top
column_buttons = []
status_label = None
move_entry = None
move_button = None
mode_var = None
computer_first_var = None
robot_var = None
pump_var = None
pump_check = None


def build(on_column, on_text, on_reset, on_pump, robot_available, pump_available, pump_on):
    global root, status_label, move_entry, move_button, EMPTY_BG
    global mode_var, computer_first_var, robot_var, pump_var, pump_check

    root = tk.Tk()
    root.title("Avoid 3")

    tk.Label(root, text="Make 3 in a row and you lose", font=("Arial", 12), fg="grey").pack(
        pady=(15, 0))

    # ---- Board ----
    board_frame = tk.Frame(root)
    board_frame.pack(padx=20, pady=(10, 10))

    # Column numbers on top, clickable like the rest of the column.
    for column in range(COLUMNS):
        button = tk.Button(board_frame, text=str(column + 1), font=("Arial", 14, "bold"),
                           width=4, relief=tk.FLAT, command=lambda c=column: on_column(c))
        button.grid(row=0, column=column, padx=3, pady=(0, 4))
        column_buttons.append(button)

    for square in range(ROWS * COLUMNS):
        row, column = divmod(square, COLUMNS)
        button = tk.Button(
            board_frame,
            text="",
            width=3,
            height=1,
            font=("Arial", 38),
            command=lambda c=column: on_column(c),  # any square plays its column
        )
        button.grid(row=row + 1, column=column, padx=3, pady=3)
        buttons.append(button)
    EMPTY_BG = buttons[0].cget("background")

    status_label = tk.Label(root, text="", font=("Arial", 14))
    status_label.pack(pady=(0, 10))

    # ---- Typed move ----
    move_frame = tk.Frame(root)
    move_frame.pack(pady=(0, 10))
    tk.Label(move_frame, text="Column:", font=("Arial", 12)).pack(side=tk.LEFT)

    move_entry = tk.Entry(move_frame, width=14, font=("Arial", 14))
    move_entry.pack(side=tk.LEFT, padx=5)

    def submit(_event=None):
        text = move_entry.get()
        move_entry.delete(0, tk.END)
        if text.strip():
            on_text(text)

    move_entry.bind("<Return>", submit)
    move_button = tk.Button(move_frame, text="Move", command=submit)
    move_button.pack(side=tk.LEFT)

    tk.Label(root, text='Type 1-5, or e.g. "middle", "far left"', fg="grey").pack()

    # ---- Game settings: take effect on New game ----
    settings = tk.LabelFrame(root, text="New game settings", padx=10, pady=5)
    settings.pack(padx=20, pady=10, fill=tk.X)

    mode_var = tk.StringVar(value=MODES[0])
    tk.OptionMenu(settings, mode_var, *MODES).pack(anchor=tk.W)

    computer_first_var = tk.BooleanVar(value=False)
    tk.Checkbutton(settings, text="Computer goes first (plays Red)",
                   variable=computer_first_var).pack(anchor=tk.W)

    robot_var = tk.BooleanVar(value=robot_available)
    robot_text = "Robot arm" if robot_available else "Robot arm (not connected)"
    robot_check = tk.Checkbutton(settings, text=robot_text, variable=robot_var)
    robot_check.pack(anchor=tk.W)
    if not robot_available:
        robot_check.config(state=tk.DISABLED)

    tk.Button(settings, text="New game", command=on_reset).pack(pady=(5, 0))

    # ---- Pump: takes effect immediately. Only shown with the suction cup. ----
    pump_var = tk.BooleanVar(value=pump_on)
    if pump_available:
        pump_check = tk.Checkbutton(root, text="Suction pump on", variable=pump_var,
                                    command=lambda: on_pump(pump_var.get()))
        pump_check.pack(pady=(0, 15))
    else:
        tk.Label(root, text="").pack(pady=(0, 5))

    move_entry.focus_set()


def update_board(board, line=None):
    """Show the pieces. `line`: squares to highlight (the losing 3)."""
    line = line or ()
    for square, button in enumerate(buttons):
        piece = board[square]
        background = HIGHLIGHT if square in line else EMPTY_BG
        if piece in COLOURS:
            # disabledforeground: keep the colour while input is blocked
            button.config(text=PIECE, fg=COLOURS[piece], activeforeground=COLOURS[piece],
                          disabledforeground=COLOURS[piece], background=background)
        else:
            button.config(text="", background=background)

    # Grey out the number of a full column.
    for column, button in enumerate(column_buttons):
        button.config(fg="black" if board[column] == 0 else "#bbbbbb")


def set_status(message):
    status_label.config(text=message)


def set_busy(busy):
    """Block input while the computer or the robot is moving."""
    state = tk.DISABLED if busy else tk.NORMAL
    for button in buttons + column_buttons:
        button.config(state=state)
    move_entry.config(state=state)
    move_button.config(state=state)
    if not busy:
        move_entry.focus_set()


def refresh():
    """Redraw now, before a slow robot move or a long think blocks the window."""
    root.update_idletasks()


def later(ms, function):
    root.after(ms, function)


def get_mode():
    return MODES.index(mode_var.get())  # 0 two player, 1 easy, 2 hard


def computer_first():
    return computer_first_var.get()


def robot_on():
    return robot_var.get()


def run():
    root.mainloop()
