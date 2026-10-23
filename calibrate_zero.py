"""Check and reset the joint zero positions on the myCobot 280.

Run this if coordinates seem off: the arm lands at different heights
over different squares even though the same z was sent. Cartesian
coords are computed from joint angles, so a joint whose zero has
drifted throws everything out.

Run on the Pi, no window needed (fine over SSH):

    python3 calibrate_zero.py

What it does:
  1. Sends every joint to 0 so you can look at the alignment marks
     (a small notch/line on each half of every joint housing).
  2. If any marks are off, goes limp so you can align them by hand.
  3. Records the held position as zero for the joints you choose.
  4. Returns to 0 so you can confirm the marks line up.

Only calibrate joints that are actually off. Hold the arm steady at
the marks while it records - a limp arm sags, especially joints 2 and 3.
The new zero is written to the servo and survives power cycles.

The same thing can be done in myStudio (Tools -> Calibrate) on the Pi's
desktop, which shows all six angles live. Use whichever is handier.
"""

import time

from pymycobot import MyCobot280

PORT = "/dev/ttyAMA0"
BAUD = "1000000"
SPEED = 30

ZERO = [0, 0, 0, 0, 0, 0]


def ask(message):
    return input(message).strip().lower()


def go_to_zero(mc):
    mc.send_angles(ZERO, SPEED)
    time.sleep(4)
    print("Angles reported:", mc.get_angles())


def main():
    mc = MyCobot280(PORT, BAUD)

    print("Moving all joints to 0. Check that the marks on every joint line up.")
    go_to_zero(mc)

    if ask("Do all six joint marks line up? (y/n): ") == "y":
        print("Zero is fine. Nothing to do.")
        return

    joints_text = ask("Which joints are off? (e.g. 5 6, or 'all'): ")
    if joints_text == "all":
        joints = [1, 2, 3, 4, 5, 6]
    else:
        try:
            joints = [int(j) for j in joints_text.split()]
            if any(j < 1 or j > 6 for j in joints):
                raise ValueError
        except ValueError:
            print("Enter joint numbers between 1 and 6, separated by spaces.")
            return

    print("Releasing servos. The arm will go limp - support it.")
    mc.release_all_servos()
    ask(
        f"Align the marks on joint(s) {joints} by hand, hold the arm there, "
        "then press Enter: "
    )

    for joint in joints:
        mc.set_servo_calibration(joint)
        time.sleep(0.2)
        print(f"Joint {joint}: current position recorded as zero.")

    print("Re-engaging servos and returning to 0.")
    mc.power_on()
    time.sleep(1)
    go_to_zero(mc)
    print("Marks should now line up. If not, run this again for the joints still off.")


if __name__ == "__main__":
    main()
