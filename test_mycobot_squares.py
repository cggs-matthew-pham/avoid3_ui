"""Calibration checks for the Avoid 3 robot.

Uses the same positions and movement code as the game (robot.py), so
anything you fix here is automatically what main.py uses.

Run on the Pi, no window needed (fine over SSH):

    python3 test_mycobot_squares.py

Calibrate with the end effector you'll play with (END_EFFECTOR in
robot.py), and with a block in place: on the cup for suction, between the
fingers for the gripper. The saved "down" pose is where the arm holds that
block in its final resting place, so the drop is the same as the pick.
"""

import math
import re
import time

import robot
from robot import SQUARES, STAGING, SQUARE_Z, STAGING_Z, HOVER_CLEARANCE, BLOCK_HEIGHT

LAYER_COMMANDS = {"d": 0, "d2": 1, "d3": 2}   # down to the 1st, 2nd, 3rd block
CHECK_COMMANDS = {"check": 0, "check2": 1, "check3": 2}


def ask(message):
    return input(message).strip().lower()


def find_spot(name):
    """Turn '13' into square 13, or 'r1' / 'y3' into a staging spot.

    Names are as printed on the sheet (see robot.spot_name). Returns
    (label, key), key being robot's list index: "1" -> ("square", 20),
    "r1" -> ("staging", 1, 4). None if the name doesn't match anything.
    """
    if not (name.isdigit() or (name[:1] in ("r", "y") and name[1:].isdigit())):
        return None
    try:
        key = robot._spot_index(name)
    except (ValueError, KeyError):
        return None
    label = f"square {name}" if key[0] == "square" else name.upper()
    return label, key


def stack_size(key):
    if key[0] == "square":
        return 1
    _, player, index = key
    return robot.STACK_SIZES[player][index]


def get_spot(key):
    """(x, y, down0_z) currently stored for a spot."""
    if key[0] == "square":
        x, y = SQUARES[key[1]]
        return x, y, SQUARE_Z[key[1]]
    _, player, index = key
    x, y = STAGING[player][index]
    return x, y, STAGING_Z[player][index]


def set_spot(key, x, y, table_z):
    if key[0] == "square":
        SQUARES[key[1]] = (x, y)
        SQUARE_Z[key[1]] = table_z
    else:
        _, player, index = key
        STAGING[player][index] = (x, y)
        STAGING_Z[player][index] = table_z


def hover_height(key):
    return get_spot(key)[2] + HOVER_CLEARANCE


def lift_height(key, z):
    """Where to lift to before moving sideways: the spot's hover height,
    which clears a full stack, or higher if already above it."""
    return max(z, hover_height(key))


def show_position(x, y, z):
    print(f"  Sent:     x={x:g}  y={y:g}  z={z:g}")
    coords = robot.read_coords()
    if coords:
        print("  Reported: x={:.1f}  y={:.1f}  z={:.1f}  rx={:.1f}  ry={:.1f}  rz={:.1f}".format(*coords))
    else:
        print("  Reported: (no answer from arm)")
    angles = robot.read_angles()
    if angles:
        print("  Angles:   " + "  ".join(f"J{i + 1}={a:.1f}" for i, a in enumerate(angles)))


def tool_command(command):
    """Pump or gripper commands. Returns True if it was one."""
    if command in ("pump", "pump on", "pump off"):
        if robot.END_EFFECTOR != "suction":
            print("  No pump fitted (END_EFFECTOR is the gripper).")
            return True
        if command == "pump":
            on = not robot.PUMP_ENABLED
        else:
            on = command == "pump on"
        robot.set_pump_enabled(on)
        print(f"  Pump {'ENABLED: grab will switch it on' if on else 'disabled: moves only, no suction'}.")
        return True

    if command in ("open", "open wide", "close") or command.startswith("g "):
        if robot.END_EFFECTOR != "gripper":
            print("  No gripper fitted (END_EFFECTOR is suction).")
            return True
        if command == "open":
            value = robot.GRIPPER_OPEN
        elif command == "open wide":
            value = robot.GRIPPER_PICK_OPEN
        elif command == "close":
            value = robot.GRIPPER_CLOSED
        else:
            try:
                value = int(command[2:])
                if not 0 <= value <= 100:
                    raise ValueError
            except ValueError:
                print("  g takes a number 0-100, e.g. g 40.")
                return True
        robot.set_gripper(value)
        print(f"  Gripper set to {value}. (release {robot.GRIPPER_OPEN}, "
              f"pick {robot.GRIPPER_PICK_OPEN}, closed {robot.GRIPPER_CLOSED} in robot.py)")
        return True

    return False


MAX_NUDGE = 10  # mm; stops a typo like x+40 swinging the arm across the board
NUDGE = re.compile(r"^([xyz])([+-])(\d+(?:\.\d+)?)?$")


def print_layout():
    print("The sheet, seen from the player (robot at the top):")
    for row in range(robot.GRID_ROWS):
        cells = "".join(f"{robot.spot_name('square', row * robot.GRID_COLUMNS + c):>4}"
                        for c in range(robot.GRID_COLUMNS))
        stacks = "  ".join(robot.spot_name("staging", p, row).upper() for p in (1, 2))
        print(f"  {cells}     {stacks}     ROW {robot.GRID_ROWS - row}")


def test_go_to():
    print_layout()
    print("Type a spot: 1-25, r1-r5, y1-y5. Then:")
    print(f"  h = hover ({HOVER_CLEARANCE} mm above the bottom block: clears a full stack)")
    print("  d = down to a block on the table; d2 / d3 = 2nd / 3rd block of a stack")
    print("  x+ x- y+ y- z+ z- = nudge 1 mm; add mm for more, up to 10 (x+4, z-0.5)")
    print("  teach = go limp, you hold the tool on the spot, Enter to read it")
    if robot.END_EFFECTOR == "gripper":
        print("  open / open wide / close / g 40 = gripper (release / pick / hold / any 0-100)")
    else:
        print("  pump / pump on / pump off = allow the suction pump (off by default)")
    print("  w = show where the arm is, save = keep this spot, q = back to menu")
    print("  n = go to the next spot that still needs saving")
    print("  layers = at a stack: do the 2nd and 3rd blocks one after the other")
    print("  check / check2 / check3 = replay the saved angles for layer 1 / 2 / 3,")
    print("                            exactly as the game moves: tests repeatability")
    print("Save at d (holding a block where it sits on the table): records the joint")
    print("angles the game will replay, then lifts straight up and records hover.")
    print("Staging stacks: then 'layers' for the 2nd and 3rd blocks.")
    print("Big moves happen at hover; only fine-tune near the block.")
    print("Quickest: type n, d, nudge, save; repeat. Spots not yet saved start from")
    print("a guess corrected by the saved spots around them, so later ones need less nudging.")

    key = None        # which spot we're working on
    x = y = z = None  # where the arm was last sent
    level = None      # "h", "d", "d2" or "d3"
    layer_queue = []  # stack layers still to do after 'layers'

    def go_to(found):
        """Lift if needed, then travel at hover to a spot. Returns the new state."""
        if not heights_known():
            raise RuntimeError(HEIGHT_WARNING)
        if level in LAYER_COMMANDS:  # always lift before moving sideways
            robot.move_to(x, y, lift_height(key, z), mode=1)
        label, new_key = found
        name = robot.spot_name(*new_key)
        guess = ""
        if not robot.saved_angles(name):
            # Not calibrated: start from a guess corrected by its neighbours.
            gx, gy, gz, used = robot.predict_spot(name)
            set_spot(new_key, gx, gy, gz)
            if used:
                guess = f" (starting guess from {used} calibrated spot{'s' if used > 1 else ''} nearby)"
        new_x, new_y, _ = get_spot(new_key)
        new_z = hover_height(new_key)
        robot.move_to(new_x, new_y, new_z)
        stack = f" (stack of {stack_size(new_key)})" if new_key[0] == "staging" else ""
        print(f"Over {label}{stack}{guess}")
        show_position(new_x, new_y, new_z)
        return new_key, new_x, new_y, new_z, "h"

    def go_to_layer(layer):
        """Prompt for the stack, then come down to its top block. Returns z, or None to stop."""
        name = robot.spot_name(*key)
        print(f"\n  Layer {layer + 1}: stack {layer + 1} blocks on {name.upper()}.")
        if robot.END_EFFECTOR == "gripper":
            print("  The gripper will open and come down around the top block.")
        if ask("  Enter when ready, or s to stop: ") == "s":
            return None
        robot.get_ready_to_grab()
        down_z = get_spot(key)[2] + layer * BLOCK_HEIGHT
        robot.move_to(x, y, down_z, mode=1)  # straight down from hover
        show_position(x, y, down_z)
        print("  Nudge until it's centred on the top block, then save.")
        return down_z

    while True:
        command = ask("> ")

        if command == "q":
            if level in LAYER_COMMANDS:
                try:
                    robot.move_to(x, y, lift_height(key, z), mode=1)
                except RuntimeError as error:
                    print(f"{error}\n  (Couldn't lift first; check the arm is clear.)")
            return

        if tool_command(command):
            continue

        try:
            if command == "h" or command in LAYER_COMMANDS:
                if key is None:
                    print("Choose a square or staging spot first.")
                    continue
                if command == "h":
                    if level == "h":
                        print("  Already at hover. Use z+ to go higher.")
                        continue
                    z = lift_height(key, z)
                else:
                    layer = LAYER_COMMANDS[command]
                    if layer >= stack_size(key):
                        print(f"  This spot only holds {stack_size(key)} block(s).")
                        continue
                    z = get_spot(key)[2] + layer * BLOCK_HEIGHT
                robot.move_to(x, y, z, mode=1)  # straight up or down
                level = command
                show_position(x, y, z)
                continue

            nudge = NUDGE.match(command)
            if nudge:
                if key is None:
                    print("Choose a square or staging spot first.")
                    continue
                axis, sign, amount = nudge.groups()
                step = float(amount or 1)
                if step > MAX_NUDGE:
                    print(f"  Max {MAX_NUDGE:g} mm per nudge; repeat it to go further.")
                    continue
                if sign == "-":
                    step = -step
                new = {"x": x, "y": y, "z": z}
                new[axis] += step
                # Small moves in a straight line so it can't swing into the board.
                robot.move_to(new["x"], new["y"], new["z"], mode=1)
                x, y, z = new["x"], new["y"], new["z"]
                show_position(x, y, z)
                continue

            if command == "teach":
                if key is None:
                    print("Choose a square or staging spot first.")
                    continue
                print("  Servos releasing - HOLD THE ARM, it will drop.")
                ask("  Enter to release: ")
                robot.mc.release_all_servos()
                ask("  Hold the tool on a block on the table at the spot, pointing down. "
                    "Enter when there: ")
                robot.mc.power_on()
                time.sleep(1)
                coords = robot.read_coords()
                if coords is None:
                    print("  Couldn't read the arm's position. Try again.")
                    level = None
                    robot.last_target = None
                    continue
                tx, ty, tz = (round(c, 1) for c in coords[:3])
                print(f"  Taught: x={tx:g}  y={ty:g}  z={tz:g}")
                if tz < robot.MIN_Z:
                    print(f"  z is below MIN_Z ({robot.MIN_Z}); using {robot.MIN_Z}. "
                          "Run option 5 to measure the grip height.")
                    tz = robot.MIN_Z
                # A limp arm sags and tilts, so drive there properly under power
                # (tool straight down) and check before saving.
                robot.last_target = None
                robot.move_to(tx, ty, tz, mode=1)
                x, y, z = tx, ty, tz
                level = "d"
                show_position(x, y, z)
                print("  Now nudge until it's dead centre at block height, then save.")
                continue

            if command == "w":
                if key is None:
                    print("Choose a square or staging spot first.")
                    continue
                show_position(x, y, z)
                continue

            if command == "save":
                if key is None:
                    print("Choose a square or staging spot first.")
                    continue
                name = robot.spot_name(*key)
                saved = []
                saved_layer = LAYER_COMMANDS.get(level)  # None if saving at hover

                if level in LAYER_COMMANDS:
                    layer = LAYER_COMMANDS[level]
                    pose = f"down{layer}"
                    angles = robot.read_angles(fallback=False)
                    if angles is None:
                        print("  Couldn't read joint angles; nothing saved. Try again.")
                        continue
                    robot.save_pose(name, pose, angles, (x, y, z), robot.read_coords())
                    saved.append(pose)
                    if layer == 0:
                        set_spot(key, x, y, z)  # nudging and hover start from here
                    # Straight up to hover. Layer 0 sets the hover height;
                    # upper layers keep an existing hover.
                    z = z + HOVER_CLEARANCE if layer == 0 else lift_height(key, z)
                    robot.move_to(x, y, z, mode=1)
                    level = "h"
                    save_hover = layer == 0 or robot.calibration.get((name, "hover")) is None
                else:
                    save_hover = True

                if save_hover:
                    angles = robot.read_angles(fallback=False)
                    if angles is None:
                        print("  Couldn't read hover angles; press h then save again to add them.")
                    else:
                        robot.save_pose(name, "hover", angles, (x, y, z), robot.read_coords())
                        saved.append("hover")

                print(f"  Saved {name}: {', '.join(saved) or 'nothing'} -> calibration.csv")

                if layer_queue and saved_layer == layer_queue[0]:
                    layer_queue.pop(0)
                    if layer_queue:
                        new_z = go_to_layer(layer_queue[0])
                        if new_z is None:
                            layer_queue.clear()
                        else:
                            z, level = new_z, f"d{layer_queue[0] + 1}"
                            continue
                    else:
                        print(f"  Stack {name.upper()} done.")

                still = [n for n in range(1, stack_size(key)) if not robot.saved_angles(name, n)]
                if not robot.saved_angles(name):
                    print("  Still needs its table position: d, nudge, save.")
                elif still:
                    print("  Next: 'layers' for the blocks above, or n for the next spot.")
                else:
                    print(f"  {len(robot.missing_spots())} pose(s) left. n = next spot.")
                continue

            if command == "layers":
                if key is None or key[0] != "staging":
                    print("Go to a staging stack first (r1-r5, y1-y5).")
                    continue
                name = robot.spot_name(*key)
                if not robot.saved_angles(name):
                    print("  Save the bottom block first: d, nudge, save.")
                    continue
                layer_queue[:] = [n for n in range(1, stack_size(key))
                                  if not robot.saved_angles(name, n)]
                if not layer_queue:
                    print("  All layers saved here. To redo one, use d2 or d3, nudge, save.")
                    continue
                if level in LAYER_COMMANDS:
                    robot.move_to(x, y, lift_height(key, z), mode=1)
                    z, level = lift_height(key, z), "h"
                new_z = go_to_layer(layer_queue[0])
                if new_z is None:
                    layer_queue.clear()
                    continue
                z, level = new_z, f"d{layer_queue[0] + 1}"
                continue

            if command == "n":
                after = robot.spot_name(*key) if key else None
                found_next = robot.next_to_calibrate(after)
                if found_next is None:
                    print("Everything is saved. Use check to test spots, or q.")
                    continue
                name, what = found_next
                layer_queue.clear()
                key, x, y, z, level = go_to(find_spot(name))
                if what == "position":
                    print("  Next: d, nudge, save.")
                else:
                    print("  Bottom block saved. Next: layers.")
                continue

            if command in CHECK_COMMANDS:
                if key is None:
                    print("Choose a square or staging spot first.")
                    continue
                layer = CHECK_COMMANDS[command]
                if layer >= stack_size(key):
                    print(f"  This spot only holds {stack_size(key)} block(s).")
                    continue
                name = robot.spot_name(*key)
                angles = robot.saved_angles(name, layer)
                if angles is None:
                    down = "d" if layer == 0 else f"d{layer + 1}"
                    print(f"  {name} needs hover and down{layer} saved first ({down}, nudge, save).")
                    continue
                if level in LAYER_COMMANDS:
                    robot.move_to(x, y, lift_height(key, z), mode=1)
                hover, down = angles
                robot.move_angles(hover)
                robot.move_angles(down)
                x, y, table_z = get_spot(key)
                z = table_z + layer * BLOCK_HEIGHT
                level = "d" if layer == 0 else f"d{layer + 1}"
                print("  Replayed saved angles, exactly as the game will. Centred on the block?")
                reported = robot.read_coords()
                now_angles = robot.read_angles(fallback=False)
                errors = robot.log_check(name, f"down{layer}", reported, now_angles)
                if all(e is not None for e in errors):
                    print("  Reported vs at save: dx={:+.1f}  dy={:+.1f}  dz={:+.1f} mm "
                          "(logged to check_log.csv)".format(*errors))
                else:
                    print("  (Couldn't compare with save; logged to check_log.csv)")
                continue

            found = find_spot(command)
            if found is None:
                print("Unknown command. Try n, 13, r1, h, d, x+2, w, save, layers, check or q.")
                continue
            layer_queue.clear()
            key, x, y, z, level = go_to(found)

        except RuntimeError as error:
            print(error)
            print("  (Position unchanged.)")


def test_end_effector():
    if robot.END_EFFECTOR == "suction" and not robot.PUMP_ENABLED:
        print("The pump is disabled. Turn it on from the menu (p) first.")
        return
    print(f"Testing the {robot.END_EFFECTOR}.")
    if robot.END_EFFECTOR == "gripper":
        robot.get_ready_to_grab()
        print("Hold a block between the fingers.")
    else:
        print("Hold a block against the cup.")
    ask("Enter to grab: ")
    robot.grab()
    ask("Did it grab? Enter to release: ")
    robot.release()
    print("Done.")


def test_pick_and_place():
    if not heights_known():
        print(HEIGHT_WARNING)
        return
    names = {"r": 1, "y": 2}

    player = names.get(ask("Pick a Red or a Yellow block? (r/y): "))
    if player is None:
        print("Type r or y.")
        return

    spots = STAGING[player]
    try:
        spot = int(ask(f"Which stack? (1-{len(spots)}): ")) - 1
        size = robot.STACK_SIZES[player][spot]
        layer = 0
        if size > 1:
            layer = int(ask(f"Which block? (1 = bottom ... {size} = top): ")) - 1
        square = int(ask(f"Which square to place it on? (1-{len(SQUARES)}): ")) - 1
        SQUARES[square]  # check it exists
        if spot < 0 or square < 0 or not 0 <= layer < size:
            raise ValueError
    except (ValueError, IndexError):
        print("That stack, block or square doesn't exist.")
        return

    try:
        robot.pick_from_spot(robot.spot_name("staging", player, spot), layer)
        robot.drop_at_spot(robot.spot_name("square", square))
    except RuntimeError as error:
        print(error)
        robot.release()  # don't keep holding a block after a failed move
        return

    print("Done. Did the block land in the middle of the square?")


def show_reach():
    far, far_mm, near, near_mm, beyond, too_close = robot.reach_report()
    print(f"Sheet gap {robot.SHEET_GAP:g} mm: nearest spot {near} is {near_mm:.0f} mm "
          f"from the base, farthest {far} is {far_mm:.0f} mm (arm's rated reach "
          f"{robot.REACH_LIMIT} mm).")
    if beyond:
        print(f"  Probably out of reach: {', '.join(beyond)}.")
    if too_close:
        print(f"  Too close to the base (under {robot.NEAR_LIMIT} mm): {', '.join(too_close)}.")


# ---- Grip height and offset ----

def heights_known():
    """True once the grip height is measured or any spot is calibrated."""
    if robot.grip_z_measured():
        return True
    return any(pose == "down0" for _, pose in robot.calibration)


HEIGHT_WARNING = ("Grip height not measured yet, so every height is a guess and the\n"
                  "arm may go far too high (near the base it can hit itself).\n"
                  "Run option 4 first: it measures it.")


def save_setting(name, value):
    """Rewrite one `NAME = ...` line in robot.py so the value is kept next time."""
    path = robot.__file__
    with open(path) as f:
        text = f.read()
    if isinstance(value, dict):
        line = f"{name} = {{" + ", ".join(f'"{k}": {v!r}' for k, v in value.items()) + "}"
        pattern = rf"^{name} = \{{[^}}]*\}}"
    else:
        line = f"{name} = {value:g}"
        pattern = rf"^{name} = [\d.]+"
    new_text, count = re.subn(pattern, line, text, count=1, flags=re.MULTILINE)
    if count != 1:
        print(f"  Couldn't find {name} in robot.py. Set it by hand: {line}")
        return False
    with open(path, "w") as f:
        f.write(new_text)
    return True


def describe_offset(dx, dy):
    """Plain words for how far the end plate sits from the fingertips."""
    parts = []
    if abs(dx) >= 3:
        parts.append(f"{abs(dx):.0f} mm {'further from' if dx > 0 else 'nearer to'} the robot")
    if abs(dy) >= 3:
        # +y is the robot's left = the player's right
        parts.append(f"{abs(dy):.0f} mm towards the {'Red/Yellow' if dy > 0 else 'square 1'} side")
    return " and ".join(parts) or "within a few mm"


def measure_grip_height():
    """Hold the tool on a block at square 13 by hand: read height and offset. True if done."""
    print(f"""
MEASURE THE GRIP HEIGHT AND OFFSET  ({robot.END_EFFECTOR})

Every position the arm uses before calibration comes from this: the
height (hover included) and how far the tool sits from the end of the arm.
Measured by hand, so the arm makes no big moves. Do it with the sheet in
its final place.

1. Put one block on square 13, centred in the circle.
2. The arm will go limp. Hold it.
3. Bring the tool down onto the block, pointing straight down:""")
    if robot.END_EFFECTOR == "gripper":
        print("   gripper open, fingers either side of the block, tips a few mm above the")
        print("   table, at the height you'd grip it.")
    else:
        print("   cup resting flat on the middle of the block.")
    if ask("Enter to start, or q to cancel: ") == "q":
        return False

    robot.get_ready_to_grab()  # open the gripper first
    print("  Servos releasing - HOLD THE ARM, it will drop.")
    ask("  Enter to release: ")
    robot.mc.release_all_servos()
    ask("  Hold the tool on the block, straight down. Enter when it's there: ")
    robot.mc.power_on()
    time.sleep(1)
    coords = robot.read_coords()
    if coords is None:
        print("  Couldn't read the arm's position. Try again.")
        robot.last_target = None
        return False

    x, y, z = (round(c, 1) for c in coords[:3])
    print(f"  Grip height: z = {z:g} (it was guessing {robot.DOWN_Z:g}).")
    nx, ny = robot.nominal_position(robot.ANCHOR_SPOT)
    dx, dy = x - nx, y - ny
    print(f"  Square 13 on the layout: x={nx:g}  y={ny:g}.  End of the arm: x={x:g}  y={y:g}.")
    print(f"  So the end of the arm sits {describe_offset(dx, dy)} compared with the")
    print("  fingertips (this includes any small error in the distance or centring).")
    print("  Starting positions now allow for it.")

    robot.set_down_z(z)
    robot.set_grip_anchor(x, y)
    if save_setting("GRIP_Z", robot.GRIP_Z) and save_setting("GRIP_ANCHOR", robot.GRIP_ANCHOR):
        print(f"  Saved for the {robot.END_EFFECTOR} in robot.py.")

    # Up a little, straight, so it clears the block, then home.
    print("  Lifting and going home. Hands clear.")
    robot.last_target = None
    try:
        robot.move_to(x, y, z + 30, mode=1)
    except RuntimeError as error:
        print(f"  ({error}; going home directly)")
    robot.home()
    print(f"  Hover will be {z + HOVER_CLEARANCE:g} ({HOVER_CLEARANCE} mm above this).")
    return True


# ---- Gripper open / close values ----

def try_values(prompt, start):
    """Let the user try gripper values until they're happy. Returns the last one."""
    value = start
    robot.set_gripper(value)
    print(f"  Now at {value}. Type another number (0-100) to try, or Enter to keep {value}.")
    while True:
        text = ask(f"  {prompt} [{value}]: ")
        if not text:
            return value
        try:
            new = int(text)
            if not 0 <= new <= 100:
                raise ValueError
        except ValueError:
            print("  A whole number from 0 to 100, please.")
            continue
        value = new
        robot.set_gripper(value)


def setup_gripper():
    if robot.END_EFFECTOR != "gripper":
        print("Only for the gripper (END_EFFECTOR in robot.py is suction).")
        return
    print("""
GRIPPER: HOW FAR IT OPENS AND CLOSES

The gripper takes a number from 0 to 100. It should never open fully: the
fingers would hit the blocks either side. Three settings:
  release   opens just enough to let go of a block on the board
  pick      opens a bit wider before going down onto a stack, so a
            slightly-off approach still gets around the block
  closed    holds a block firmly, without the servo straining
""")
    robot.set_gripper(0)
    end = ask("At 0, is the gripper open or closed? (o/c): ")
    robot.set_gripper(100)
    if end not in ("o", "c"):
        print("Type o or c. Nothing changed.")
        return
    wider = "lower" if end == "o" else "higher"
    print(f"So {wider} numbers open it wider.\n")

    print("1. RELEASE. Hold a block between the fingers (don't let them grip it).")
    print("   Find the smallest opening that clears it with about 2 mm each side.")
    opened = try_values("Release value", robot.GRIPPER_OPEN)

    print("\n2. PICK. Open a bit wider: about 5 mm each side of the block. Check")
    print("   the open fingers are still well under 50 mm across (the stacks are")
    print("   45 mm apart).")
    pick = try_values("Pick value", robot.GRIPPER_PICK_OPEN)

    print("\n3. CLOSED. Keep the block between the fingers.")
    print("   Find the value that holds it firmly without straining.")
    closed = try_values("Closed value", robot.GRIPPER_CLOSED)

    robot.GRIPPER_OPEN, robot.GRIPPER_PICK_OPEN, robot.GRIPPER_CLOSED = opened, pick, closed
    if (save_setting("GRIPPER_OPEN", opened) and save_setting("GRIPPER_PICK_OPEN", pick)
            and save_setting("GRIPPER_CLOSED", closed)):
        print(f"  Saved: release {opened}, pick {pick}, closed {closed} in robot.py.")
    robot.set_gripper(opened)
    print("  Take the block out. Done.")


# ---- Setting up the sheet ----

SHEET_STEPS = """
SETTING UP THE SHEET  (do this before calibrating)

The arm remembers each spot as a set of joint angles. If the sheet moves
after you calibrate, every move will miss by that much. So get the sheet
in the right place first, then fix it down.

1. Clear all blocks off the sheet.

2. Lay the sheet LANDSCAPE (wide side towards the robot).
   Standing where the player sits: the title AVOID THREE is at the far
   side, next to the robot, and the RED and YELLOW columns are on your right.

3. Line up the middle. The centre of the robot's turntable should be in
   line with the column of squares 4, 9, 14, 19, 24. That's the middle of
   the WHOLE sheet, counting the Red and Yellow columns, not the middle of
   the 5 x 5. From the robot's side the columns run Y, R, 5, 4, 3, 2, 1.

4. Set the distance. Measure from the centre of the part of the base that
   turns (the middle of the round turntable, not the edge of the box) to
   the edge of the paper.
     - Use 60 mm: the sheet is designed for it (printed by the ROBOT mark).
     - Closer helps the far corners (squares 1 and Y1, on the player's side).
     - Too close and the arm can't bend down onto the nearest squares.
"""


def reach_out(name):
    """Move out towards a far spot, for real, until the arm can't go further.

    Steps outward at hover height along the line from the base to the spot,
    checking after each move that the arm really got there (it silently
    ignores moves it can't do). At the furthest point it then comes straight
    down to block height to check that too.

    Returns (mm reached at hover, mm the spot needs, whether block height
    worked there).
    """
    x, y, down_z = robot.start_position(name)
    needed = math.hypot(x, y)
    hover_z = down_z + HOVER_CLEARANCE
    ux, uy = x / needed, y / needed          # direction from the base to the spot
    reached = None
    distance = 150                           # comfortably inside reach
    while distance <= needed + 20:           # a little past the spot shows the spare
        try:
            robot.move_to(ux * distance, uy * distance, hover_z)
        except RuntimeError as error:
            print(f"     stopped at {distance:.0f} mm: {error}")
            break
        # The general arrival check allows 15 mm, more than one step here,
        # so check this step's distance properly.
        coords = robot.read_coords()
        if coords is not None:
            actual = math.hypot(coords[0], coords[1])
            if actual < distance - 5:
                print(f"     stopped at {distance:.0f} mm: the arm only got to {actual:.0f} mm.")
                robot.last_target = None
                break
        reached = distance
        print(f"     {distance:.0f} mm ok")
        distance += 20 if distance + 20 <= needed else 10

    if reached is None:
        return None, needed, False
    # Come down to block height at the spot itself (or as far out as it got).
    down_at = min(reached, needed)
    px, py = ux * down_at, uy * down_at
    try:
        robot.move_to(px, py, hover_z)
        robot.move_to(px, py, down_z, mode=1)   # straight down, no blocks on the sheet
        down_ok = True
        robot.move_to(px, py, hover_z, mode=1)
        print(f"     came down to block height at {down_at:.0f} mm: ok")
    except RuntimeError as error:
        print(f"     couldn't come down to block height at {down_at:.0f} mm: {error}")
        down_ok = False
        robot.last_target = None
        try:
            robot.move_to(ux * reached, uy * reached, hover_z)
        except RuntimeError:
            pass
    return reached, needed, down_ok


def near_check(name):
    """Go above the nearest spot if that's safe. Returns "ok" or why not."""
    label, _ = find_spot(name)
    x, y, down_z = robot.start_position(name)
    if math.hypot(x, y) < robot.NEAR_LIMIT:
        return f"too close: {math.hypot(x, y):.0f} mm from the base"
    hover_z = down_z + HOVER_CLEARANCE
    if not (robot.can_reach([x, y, down_z] + robot.TOOL_DOWN)
            and robot.can_reach([x, y, hover_z] + robot.TOOL_DOWN)):
        return "the arm can't point straight down there"
    robot.move_to(x, y, hover_z)
    print(f"  The arm is above {label} (its starting guess), {HOVER_CLEARANCE} mm up.")
    return "ok"


def setup_sheet():
    print(SHEET_STEPS)
    text = ask(f"Measured distance in mm (Enter to keep {robot.SHEET_GAP:g}): ")
    if text:
        try:
            gap = float(text)
            if not 0 <= gap <= 200:
                raise ValueError
        except ValueError:
            print("Type a number of mm, e.g. 55.")
            return
        robot.set_sheet_gap(gap)
        save_setting("SHEET_GAP", gap)

    if robot.grip_z_measured():
        again = ask("\nMeasure grip height and offset at square 13 again? Do it if the sheet\n"
                    "or the tool has moved. (Enter = yes, s = skip): ")
        measured = again == "s" or measure_grip_height()
    else:
        measured = measure_grip_height()
    if not measured:
        print("The measurement is needed before the reach test. Run option 4 again when ready.")
        return

    print()
    show_reach()
    _, _, near, _, _, _ = robot.reach_report()
    print()
    print("Test it. Clear all blocks off the sheet. The arm moves out towards each")
    print("far corner (square 1 and Y1) in steps until it can't go further, and")
    print("comes down to block height there; then it goes above the nearest")
    print("square. Keep hands clear, and be ready to switch the arm off if the")
    print("gripper gets close to the arm.")
    if ask("Enter to start, or q to skip: ") == "q":
        return

    far_ok = True
    try:
        for name in ("1", "y1"):
            print(f"\n  Far corner {name.upper()}: reaching out...")
            reached, needed, down_ok = reach_out(name)
            if reached is None:
                print("  -> couldn't move out at all in that direction (see above).")
                far_ok = False
                continue
            spare = reached - needed
            if spare >= 0 and down_ok:
                print(f"  -> got to {reached:.0f} mm and down to block height; "
                      f"{name.upper()} needs {needed:.0f} mm. OK.")
            elif spare >= 0:
                print(f"  -> got to {reached:.0f} mm at hover height but NOT down to block "
                      f"height; {name.upper()} needs {needed:.0f} mm.")
                far_ok = False
            else:
                print(f"  -> only got to {reached:.0f} mm; {name.upper()} needs {needed:.0f} mm. "
                      f"SHORT by {-spare:.0f} mm.")
                far_ok = False
            print("     The tool is now at that limit: look where it is compared with the corner.")
            ask("     Enter to carry on: ")

        print(f"\n  Nearest square {near}:")
        near_result = near_check(near)
        print(f"  -> {near_result}")
    except RuntimeError as error:
        print(f"  {error}")
        robot.home()
        return
    robot.home()

    print()
    near_ok = near_result == "ok"
    if near_ok and far_ok:
        print("Both ends reachable. The sheet is in a good place.")
        print("(At full stretch the arm can sag a few mm short of what it reports;")
        print("calibration nudging takes care of that.)")
        print("Fix it: tape the sheet down, and mark around the robot's base")
        print("(tape on the corners) so you can put it back in the same place.")
        print("Next: option 1 to calibrate each spot.")
        return

    if not far_ok and not near_ok:
        print("Neither end worked. Paste this output to get help working out why.")
    elif not far_ok:
        print("The far corners are out of reach. Either slide the sheet closer by")
        print("the shortfall (if the nearest square has room), or raise the robot")
        print("20-40 mm on a flat, solid block. Then rerun this.")
    else:
        print("The nearest square is too close: slide the sheet 10 mm away from")
        print("the robot, then rerun this, measuring again.")


def main():
    print(f"End effector: {robot.END_EFFECTOR}")
    show_reach()
    if not heights_known():
        print()
        print(HEIGHT_WARNING)
        print()
    print("Moving to safe start position...")
    robot.home()
    robot.release()  # gripper open / pump off

    tests = {
        "1": ("Go to a square or staging spot (hover/down)", test_go_to),
        "2": ("Grab and release", test_end_effector),
        "3": ("Pick and place (staging stack to square)", test_pick_and_place),
        "4": ("Set up: place the sheet, measure grip height and offset, reach test (do this first)",
              setup_sheet),
        "5": ("Measure grip height and offset again (after moving the sheet or changing the tool)",
              measure_grip_height),
        "6": ("Gripper: set how far it opens and closes (do this before option 4)",
              setup_gripper),
    }

    while True:
        print()
        missing = robot.missing_spots()
        if missing:
            print(f"Calibration: {len(missing)} spot(s) still to save: {', '.join(missing)}")
        else:
            print("Calibration: all spots saved. Ready to play.")
        for key, (name, _) in tests.items():
            print(f"{key}. {name}")
        if robot.END_EFFECTOR == "suction":
            state = "ON" if robot.PUMP_ENABLED else "off"
            print(f"p. Toggle suction pump (currently {state})")
        choice = ask("Choose a test, or q to quit: ")

        if choice == "q":
            if robot.END_EFFECTOR == "suction":
                robot.set_pump_enabled(False)
            robot.home()
            return
        if choice == "p":
            tool_command("pump")
            continue
        if choice in tests:
            tests[choice][1]()


if __name__ == "__main__":
    main()
