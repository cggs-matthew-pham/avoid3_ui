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

    Names count from 1. Returns (label, key) where key holds the list index
    (from 0): "13" -> ("square", 12), "r1" -> ("staging", 1, 0). None if the
    name doesn't match anything.
    """
    if name.isdigit():
        index = int(name) - 1
        if 0 <= index < len(SQUARES):
            return f"square {index + 1}", ("square", index)
        return None

    players = {"r": 1, "y": 2}
    if name[:1] in players and name[1:].isdigit():
        player = players[name[0]]
        index = int(name[1:]) - 1
        if 0 <= index < len(STAGING[player]):
            return f"{name[0].upper()}{index + 1}", ("staging", player, index)

    return None


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

    if command in ("open", "close") or command.startswith("g "):
        if robot.END_EFFECTOR != "gripper":
            print("  No gripper fitted (END_EFFECTOR is suction).")
            return True
        if command == "open":
            value = robot.GRIPPER_OPEN
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
        print(f"  Gripper set to {value}. (GRIPPER_OPEN={robot.GRIPPER_OPEN}, "
              f"GRIPPER_CLOSED={robot.GRIPPER_CLOSED} in robot.py)")
        return True

    return False


MAX_NUDGE = 10  # mm; stops a typo like x+40 swinging the arm across the board
NUDGE = re.compile(r"^([xyz])([+-])(\d+(?:\.\d+)?)?$")


def print_layout():
    print("Squares, seen from the player (robot at the top):")
    for row in range(5):
        cells = "".join(f"{row * 5 + c + 1:4d}" for c in range(5))
        print(f"  {cells}     R{row + 1}  Y{row + 1}")


def test_go_to():
    print_layout()
    print("Type a spot: 1-25, r1-r5, y1-y5. Then:")
    print(f"  h = hover ({HOVER_CLEARANCE} mm above the bottom block: clears a full stack)")
    print("  d = down to a block on the table; d2 / d3 = 2nd / 3rd block of a stack")
    print("  x+ x- y+ y- z+ z- = nudge 1 mm; add mm for more, up to 10 (x+4, z-0.5)")
    print("  teach = go limp, you hold the tool on the spot, Enter to read it")
    if robot.END_EFFECTOR == "gripper":
        print("  open / close / g 40 = gripper (0-100)")
    else:
        print("  pump / pump on / pump off = allow the suction pump (off by default)")
    print("  w = show where the arm is, save = keep this spot, q = back to menu")
    print("  check / check2 / check3 = replay the saved angles for layer 1 / 2 / 3,")
    print("                            exactly as the game moves: tests repeatability")
    print("Save at d (holding a block where it sits on the table): records the joint")
    print("angles the game will replay, then lifts straight up and records hover.")
    print("Staging stacks: also save at d2 and d3 with 2 and 3 blocks stacked.")
    print("Big moves happen at hover; only fine-tune near the block.")

    key = None        # which spot we're working on
    x = y = z = None  # where the arm was last sent
    level = None      # "h", "d", "d2" or "d3"

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
                          "Lower DOWN_Z in robot.py if the table really is that low.")
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
                still = ["d" if n == 0 else f"d{n + 1}" for n in range(stack_size(key))
                         if not robot.saved_angles(name, n)]
                if still:
                    print(f"  Still to save here: {', '.join(still)} (go down, nudge, save).")
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
                print("Unknown command. Try 13, r1, y2, h, d, d2, d3, x+2, w, save, check or q.")
                continue

            if level in LAYER_COMMANDS:  # always lift before moving sideways
                robot.move_to(x, y, lift_height(key, z), mode=1)

            label, key = found
            x, y, _ = get_spot(key)
            z = hover_height(key)
            level = "h"
            robot.move_to(x, y, z)
            print(f"Over {label}" + (f" (stack of {stack_size(key)})" if key[0] == "staging" else ""))
            show_position(x, y, z)

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
    far, far_mm, near, near_mm, beyond = robot.reach_report()
    print(f"Starting positions: nearest {near} at {near_mm:.0f} mm, "
          f"farthest {far} at {far_mm:.0f} mm from the base.")
    if beyond:
        print(f"  Beyond REACH_LIMIT ({robot.REACH_LIMIT} mm): {', '.join(beyond)}")
        print("  Move the board closer (GRID_NEAR_X), or use a smaller PITCH.")


def main():
    print(f"End effector: {robot.END_EFFECTOR}")
    show_reach()
    print("Moving to safe start position...")
    robot.home()
    robot.release()  # gripper open / pump off

    tests = {
        "1": ("Go to a square or staging spot (hover/down)", test_go_to),
        "2": ("Grab and release", test_end_effector),
        "3": ("Pick and place (staging stack to square)", test_pick_and_place),
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
