"""Robot side of Avoid 3: turns a square number into a real pick and place.

Plain functions, no classes. Use it from other files with:

    import robot
    robot.home()
    robot.place_piece(square, player)

Choose the end effector with END_EFFECTOR below: "gripper" (default) or
"suction". Only grab(), release() and get_ready_to_grab() care which one is
fitted; every movement is the same. Calibrate with the one you'll play
with: the gripper and the cup hold a block at different heights.

HOW POSITIONS WORK
The game moves by replaying saved joint angles, read from calibration.csv.
Make that file with test_mycobot_squares.py: nudge the arm until it is
right over a spot, then save. Angles are used rather than coordinates
because the arm's own coordinate-to-angle maths is approximate and depends
on where it starts, while replayed angles land in the same place every time.

The coordinates below (SQUARES, STAGING, DOWN_Z) are only starting points
for nudging. The game refuses to use a spot that has no saved angles.
"""

import csv
import math
import os
import time
from datetime import datetime

from pymycobot import MyCobot280

HERE = os.path.dirname(os.path.abspath(__file__))
CALIBRATION_FILE = os.path.join(HERE, "calibration.csv")
CHECK_LOG_FILE = os.path.join(HERE, "check_log.csv")

PORT = "/dev/ttyAMA0"
BAUD = "1000000"
SPEED = 40

END_EFFECTOR = "gripper"  # "gripper" or "suction"

# ---- Gripper ----
# set_gripper_value takes 0-100. Check which end is open on your gripper
# with 'g 0' / 'g 100' in test_mycobot_squares.py before trusting these.
# GRIPPER_OPEN: only as wide as needed to clear a block, so the fingers
# don't knock the pieces next to it. GRIPPER_CLOSED: tight enough to hold
# a 15 mm block without straining the servo.
GRIPPER_OPEN = 60
GRIPPER_CLOSED = 20
GRIPPER_SPEED = 50

# ---- Suction ----
# False = the arm still moves through every pick and place, but the pump
# never switches on (quiet, for calibrating). Toggle while testing with
# 'pump' in test_mycobot_squares.py. Set True to actually pick up blocks.
PUMP_ENABLED = False

START_ANGLES = [25, 20, -120, 10, 0, -65]

# Starting guess for the flange height when holding a block on the table:
# the cup touching its top, or the gripper fingers around it. Set it near
# your real value (teach mode tells you) so uncalibrated spots start close.
DOWN_Z = {"suction": 175, "gripper": 200}[END_EFFECTOR]
BLOCK_HEIGHT = 15  # mm; each block up a stack sits this much higher

# Hover = this far above a spot's down0 height (a block on the table).
# Travel between spots happens at hover, so it must clear a full 3-high
# staging stack (45 mm) with a block hanging below the gripper or cup
# (15 mm), plus some margin.
HOVER_CLEARANCE = 70  # mm

# Safety: move_to refuses anything below this, so a wrong number can't
# drive the tool into the board. Low enough to leave room for nudging
# while calibrating; raise it once you know where the table is.
MIN_Z = DOWN_Z - 30

# Droop correction for coordinate moves only (nudging). Leave at 0: the
# game replays measured angles, which already include any droop.
SAG_START_X = 160
SAG_PER_MM = 0.0

# ---- Board layout ----
# Matches the printed sheet (avoid_three_final_A4_landscape.pdf) and
# hardware/board.scad. Seen from the player's side, robot at the far edge:
#
#                  ROBOT
#     1   2   3   4   5    R1  Y1
#     6   7   8   9  10    R2  Y2
#    11  12  13  14  15    R3  Y3
#    16  17  18  19  20    R4  Y4
#    21  22  23  24  25    R5  Y5      <- bottom row: fills first
#
#                 PLAYER
#
# Each R and Y spot holds a stack of 3 blocks.
#
# x is distance out from the robot, y is left/right (+y = the robot's left,
# which is the player's right). These positions are only starting points
# for nudging; calibrated values replace them.
PITCH = 40            # centre to centre, rows and columns (sheet: 20 mm squares, 40 mm apart)
GRID_NEAR_X = 100     # mm from robot to the centre of the top row (1-5)
SHEET_COLUMNS = 7     # 5 board columns, then Red, then Yellow
CENTRE_COLUMN = 3     # sheet column (0-6) in line with the robot base: 3 = board column 4

GRID_ROWS = 5
GRID_COLUMNS = 5
STAGING_COUNT = 5     # stacks per player
STAGING_COLUMN = {1: 5, 2: 6}   # sheet column for Red (1) and Yellow (2)


def _xy(row, sheet_column):
    return (GRID_NEAR_X + row * PITCH, (sheet_column - CENTRE_COLUMN) * PITCH)


SQUARES = [_xy(i // GRID_COLUMNS, i % GRID_COLUMNS) for i in range(GRID_ROWS * GRID_COLUMNS)]

STAGING = {
    player: [_xy(i, column) for i in range(STAGING_COUNT)]
    for player, column in STAGING_COLUMN.items()
}

# Blocks stacked on each staging spot at the start of a game. 3 high x 5
# stacks = 15 per player; only 13 Red / 12 Yellow can ever be played, so
# the last stacks are spares. Each layer has its own saved position
# ("down0" on the table, "down1", "down2" on top): calibrate all three.
STACK_SIZES = {
    1: [3] * STAGING_COUNT,
    2: [3] * STAGING_COUNT,
}

# down0 height at each spot, for nudging. Replaced by calibrated values.
SQUARE_Z = [DOWN_Z] * len(SQUARES)
STAGING_Z = {player: [DOWN_Z] * len(spots) for player, spots in STAGING.items()}

TOOL_DOWN = [180, 0, 0]  # rx, ry, rz: tool pointing straight down

PLAYER_LETTER = {1: "r", 2: "y"}

# Roughly how far out the tool can still point straight down at table
# height. Spots beyond this probably can't be calibrated. Measure yours.
REACH_LIMIT = 250  # mm


# Names count from 1, like the screen and the printed sheet: squares
# "1".."25", staging "r1".."r5" and "y1".."y5". Lists in the code still
# count from 0, so square index 12 is named "13".

def spot_name(kind, *index):
    """("square", 12) -> "13", ("staging", 1, 0) -> "r1"."""
    if kind == "square":
        return str(index[0] + 1)
    player, spot = index
    return f"{PLAYER_LETTER[player]}{spot + 1}"


def all_spot_names():
    names = [spot_name("square", i) for i in range(len(SQUARES))]
    for player, spots in STAGING.items():
        names += [spot_name("staging", player, i) for i in range(len(spots))]
    return names


def reach_report():
    """Distance from the robot base to each spot's starting position.

    Returns (farthest name, farthest mm, nearest name, nearest mm, [names
    beyond REACH_LIMIT]). Calibrated spots use their saved position.
    """
    distances = {}
    for i, (x, y) in enumerate(SQUARES):
        distances[spot_name("square", i)] = math.hypot(x, y)
    for player, spots in STAGING.items():
        for i, (x, y) in enumerate(spots):
            distances[spot_name("staging", player, i)] = math.hypot(x, y)
    far = max(distances, key=distances.get)
    near = min(distances, key=distances.get)
    beyond = [name for name, d in distances.items() if d > REACH_LIMIT]
    return far, distances[far], near, distances[near], beyond


# ---- Calibration file (calibration.csv) ----
# One row per spot and pose. Poses: "hover", "down0" (block on the table),
# "down1" and "down2" (second and third block of a stack; staging only).
# The game reads only j1..j6. Sent and reported coordinates are kept for
# cross-referencing and analysis.

ANGLE_COLUMNS = ["j1", "j2", "j3", "j4", "j5", "j6"]
CALIBRATION_COLUMNS = (
    ["spot", "pose"] + ANGLE_COLUMNS
    + ["sent_x", "sent_y", "sent_z"]
    + ["rep_x", "rep_y", "rep_z", "rep_rx", "rep_ry", "rep_rz"]
    + ["saved_at"]
)
CHECK_COLUMNS = (
    ["checked_at", "spot", "pose"]
    + ["rep_x", "rep_y", "rep_z", "rep_rx", "rep_ry", "rep_rz"]
    + ["err_x", "err_y", "err_z"]
    + ANGLE_COLUMNS
)

calibration = {}  # (spot, pose) -> row dict


def _sort_key(item):
    spot, pose = item
    if spot.isdigit():
        return (0, int(spot), "", pose != "hover", pose)
    return (1, 0, spot, pose != "hover", pose)


def _spot_index(name):
    """"13" -> ("square", 12); "r1" -> ("staging", 1, 0)."""
    if name.isdigit():
        return ("square", int(name) - 1)
    return ("staging", {"r": 1, "y": 2}[name[0]], int(name[1:]) - 1)


def load_calibration():
    calibration.clear()
    if not os.path.exists(CALIBRATION_FILE):
        return
    with open(CALIBRATION_FILE, newline="") as f:
        for row in csv.DictReader(f):
            calibration[(row["spot"], row["pose"])] = row

    # Start future nudging from the calibrated positions.
    for (spot, pose), row in calibration.items():
        if pose != "down0" or not row.get("sent_x"):
            continue
        x, y, z = float(row["sent_x"]), float(row["sent_y"]), float(row["sent_z"])
        try:
            kind, *index = _spot_index(spot)
            if kind == "square":
                SQUARES[index[0]] = (x, y)
                SQUARE_Z[index[0]] = z
            else:
                player, i = index
                STAGING[player][i] = (x, y)
                STAGING_Z[player][i] = z
        except (IndexError, KeyError, ValueError):
            pass  # spot in the file that this layout doesn't have


def _write_calibration():
    with open(CALIBRATION_FILE, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CALIBRATION_COLUMNS)
        writer.writeheader()
        for key in sorted(calibration, key=_sort_key):
            writer.writerow(calibration[key])


def _fmt(values):
    return ["" if v is None else round(v, 2) for v in values]


def save_pose(spot, pose, angles, sent, reported):
    """Record one pose and rewrite calibration.csv.

    angles: 6 joint angles. sent: (x, y, z) commanded. reported: 6 coords
    from the arm, or None if it didn't answer.
    """
    reported = reported or [None] * 6
    row = dict(zip(CALIBRATION_COLUMNS, [spot, pose] + _fmt(angles) + _fmt(sent)
                   + _fmt(reported) + [datetime.now().isoformat(timespec="seconds")]))
    calibration[(spot, pose)] = row
    _write_calibration()


def log_check(spot, pose, reported, angles):
    """Append a replay result to check_log.csv.

    err_x/y/z = where the arm reports it is now minus where it reported at
    save time. Near 0 every time = repeatable.
    """
    saved = calibration.get((spot, pose), {})
    reported = reported or [None] * 6
    errors = []
    for axis, now in zip(("rep_x", "rep_y", "rep_z"), reported[:3]):
        before = saved.get(axis)
        errors.append(now - float(before) if now is not None and before else None)
    new_file = not os.path.exists(CHECK_LOG_FILE)
    with open(CHECK_LOG_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        if new_file:
            writer.writerow(CHECK_COLUMNS)
        writer.writerow([datetime.now().isoformat(timespec="seconds"), spot, pose]
                        + _fmt(reported) + _fmt(errors) + _fmt(angles or [None] * 6))
    return errors


def saved_angles(spot, layer=0):
    """(hover, down) joint angles for a spot, or None if not both saved."""
    hover = calibration.get((spot, "hover"))
    down = calibration.get((spot, f"down{layer}"))
    if not hover or not down:
        return None
    return ([float(hover[j]) for j in ANGLE_COLUMNS],
            [float(down[j]) for j in ANGLE_COLUMNS])


def missing_spots():
    """Spots the current layout needs that have no saved angles yet."""
    missing = [spot_name("square", i) for i in range(len(SQUARES))
               if not saved_angles(spot_name("square", i))]
    for player, sizes in STACK_SIZES.items():
        for i, size in enumerate(sizes):
            name = spot_name("staging", player, i)
            missing += [f"{name}/down{layer}" if layer else name
                        for layer in range(size) if not saved_angles(name, layer)]
    return missing


load_calibration()


# ---- Connection (runs once, when this file is imported) ----

mc = MyCobot280(PORT, BAUD)

if END_EFFECTOR == "suction":
    # On the myCobot 280 Pi the pump is driven from the Pi's GPIO pins.
    # Pin numbers and on/off levels are from Elephant Robotics' examples;
    # check them against your pump before the first run.
    import RPi.GPIO as GPIO

    GPIO.setmode(GPIO.BCM)
    # initial=HIGH: an output pin starts LOW otherwise, which here means
    # pump running from the moment this file is imported.
    GPIO.setup(20, GPIO.OUT, initial=GPIO.HIGH)  # pump (LOW = on)
    GPIO.setup(21, GPIO.OUT, initial=GPIO.HIGH)  # release valve (LOW = open)

# Blocks left in each stack; refilled by reset().
blocks_left = {player: list(sizes) for player, sizes in STACK_SIZES.items()}


# ---- End effector: the only part that differs ----

def set_gripper(value):
    mc.set_gripper_value(value, GRIPPER_SPEED)
    time.sleep(1)


def get_ready_to_grab():
    """Before going down to pick: open the gripper (the cup needs nothing)."""
    if END_EFFECTOR == "gripper":
        set_gripper(GRIPPER_OPEN)


def grab():
    if END_EFFECTOR == "gripper":
        set_gripper(GRIPPER_CLOSED)
        return
    if PUMP_ENABLED:
        GPIO.output(20, 0)           # pump on
    else:
        print("(pump disabled: skipping grab)")
    time.sleep(1)


def release():
    if END_EFFECTOR == "gripper":
        set_gripper(GRIPPER_OPEN)
        return
    GPIO.output(20, 1)               # pump off
    GPIO.output(21, 0)               # open valve to drop the piece
    time.sleep(0.5)
    GPIO.output(21, 1)
    time.sleep(1)


def set_pump_enabled(on):
    """Allow or block the pump. Turning it off also stops it if running."""
    global PUMP_ENABLED
    PUMP_ENABLED = on
    if END_EFFECTOR == "suction" and not on:
        GPIO.output(20, 1)  # pump off


# ---- Talking to the arm ----
# Questions sent to the arm over the serial cable sometimes get no answer
# (None, -1 or []), especially while it is still moving. So: wait for each
# move to finish, remember what we already know, and retry only as a backup.

last_target = None   # where we last sent the arm
last_angles = None   # last good joint-angle reading


def wait_until_stopped(timeout=10):
    time.sleep(0.3)  # give the move time to start
    start = time.time()
    while time.time() - start < timeout:
        if mc.is_moving() == 0:  # 1 = moving, 0 = stopped, -1 = no answer
            return
        time.sleep(0.1)
    print("Warning: arm didn't report stopping; carrying on.")


def read_angles(fallback=True):
    """Joint angles now. With fallback=False, None rather than a stale reading."""
    global last_angles
    for _ in range(3):
        angles = mc.get_angles()
        if isinstance(angles, list) and len(angles) == 6:
            last_angles = angles
            return angles
        time.sleep(0.2)
    if fallback:
        return last_angles  # fall back to the last good reading
    return None


def read_coords():
    """Where the arm says it is: [x, y, z, rx, ry, rz], or None if no answer."""
    for _ in range(3):
        coords = mc.get_coords()
        if isinstance(coords, list) and len(coords) == 6:
            return coords
        time.sleep(0.2)
    return None


def can_reach(target):
    angles = read_angles()
    if angles is None:
        raise RuntimeError("Couldn't read the arm's joint angles. Check the connection.")

    for _ in range(3):
        solution = mc.solve_inv_kinematics(target, angles)
        if isinstance(solution, list) and len(solution) == 6:
            return True
        time.sleep(0.2)
    return False


# ---- Movement: identical for both end effectors ----

def move_to(x, y, z, mode=0):
    global last_target

    if z < MIN_Z:
        raise RuntimeError(f"Refusing to move to z={z}: below MIN_Z ({MIN_Z})")
    if mode not in (0, 1):
        raise RuntimeError(f"mode must be 0 or 1, got {mode}")

    z = z + max(0, x - SAG_START_X) * SAG_PER_MM  # droop correction
    target = [x, y, z] + TOOL_DOWN

    if target == last_target:
        return  # already there

    if not can_reach(target):
        raise RuntimeError(f"Can't reach {target}")

    mc.send_coords(target, SPEED, mode)
    wait_until_stopped()
    last_target = target


def home():
    global last_target, last_angles
    mc.send_angles(START_ANGLES, SPEED)
    wait_until_stopped()
    last_target = None
    last_angles = list(START_ANGLES)  # a known-good reading to start from


def move_angles(angles):
    """Replay saved joint angles: no coordinate maths, so it repeats exactly."""
    global last_target, last_angles
    mc.send_angles(angles, SPEED)
    wait_until_stopped()
    last_target = None  # next move_to must not assume where we are
    last_angles = list(angles)


def _replay(spot, layer, before, action):
    angles = saved_angles(spot, layer)
    if angles is None:
        command = "d" if layer == 0 else f"d{layer + 1}"
        raise RuntimeError(
            f"No saved angles for {spot} (down{layer}). Calibrate it first: "
            f"test_mycobot_squares.py, option 1, go to {spot}, {command}, nudge, save."
        )
    hover, down = angles
    move_angles(hover)
    before()
    move_angles(down)
    action()
    move_angles(hover)


def pick_from_spot(spot, layer=0):
    """layer 0 = a block on the table, 1 = second block up, 2 = third."""
    _replay(spot, layer, get_ready_to_grab, grab)


def drop_at_spot(spot):
    _replay(spot, 0, lambda: None, release)


# ---- Game-level actions ----

def place_piece(square, player):
    stacks = blocks_left[player]
    missing = missing_spots()
    if missing:
        listed = ", ".join(missing[:6]) + (" ..." if len(missing) > 6 else "")
        raise RuntimeError(f"{len(missing)} spot(s) not calibrated ({listed}). "
                           "Run test_mycobot_squares.py.")

    for stack, count in enumerate(stacks):
        if count > 0:
            layer = count - 1  # top block of this stack (0 = on the table)
            try:
                pick_from_spot(spot_name("staging", player, stack), layer)
                drop_at_spot(spot_name("square", square))
            except Exception:
                release()  # don't keep holding a block after a failed move
                raise
            stacks[stack] -= 1
            return

    raise RuntimeError(f"No staged blocks left for {'Red' if player == 1 else 'Yellow'}")


def reset():
    # Pieces go back to staging by hand, so just restart the count.
    for player, sizes in STACK_SIZES.items():
        blocks_left[player] = list(sizes)
    release()
    home()
