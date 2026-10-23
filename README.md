# avoid3_ui

"Avoid 3" on a myCobot 280 Pi: play on screen, against the computer, or with
the arm placing every piece. Adapted from
[tic_tac_toe_ui](https://github.com/cggs-matthew-pham/tic_tac_toe_ui), with
the gravity idea from
[connect4_ui](https://github.com/cggs-matthew-pham/connect4_ui).

## Rules

- 5 x 5 board with gravity: a move is a column (1-5), and the piece drops to
  the lowest empty square in it.
- Make **3 in a line** of your colour (across, down or diagonal) and you
  **lose**. 4 or more in a line also loses.
- A full board with no line is a draw.
- Red goes first. Each player stages 15 pieces (5 stacks of 3), but only
  13 Red and 12 Yellow can ever be played; the rest are spares.

## Running it

```
python3 main.py              # the game (runs on screen only if there's no arm)
python3 test_game.py         # checks the rules, the computer player and move typing
python3 test_mycobot_squares.py   # calibrate the arm (on the Pi, over SSH is fine)
python3 calibrate_zero.py    # only if the joint zeros have drifted
```

Moves can be clicked (anywhere in a column, or its number) or typed: `3`,
`three`, `column 3`, `left`, `far right`, `middle`, `left of centre`. Voice
input only needs to turn speech into text and call `moves.parse_move()`.

Modes: two player, computer easy (any move that doesn't lose straight away),
computer hard (looks ahead as far as `THINK_SECONDS` in `game.py` allows;
2 s by default).

## Files

| File | What it does |
| --- | --- |
| `game.py` | Rules and the computer player. Plain functions, same names as tic-tac-toe. |
| `moves.py` | Typed (later spoken) moves to a column number. |
| `ui.py` | Tkinter window. |
| `main.py` | Joins them up. The robot is optional. |
| `robot.py` | Layout, calibration file, gripper/suction, pick and place. |
| `test_mycobot_squares.py` | Calibration tool. |
| `calibrate_zero.py` | Joint zero calibration (unchanged from tic-tac-toe). |
| `hardware/avoid3_sheet_A4.pdf` | The printable board and block labels. |
| `hardware/make_sheet.py` | Makes that PDF. |
| `hardware/board.scad` | 3D-printable pocket board and blocks (same layout). |

## The layout

Print `hardware/avoid3_sheet_A4.pdf` at 100% (page 1 is the board, page 2 is
labels for the block tops). Remake it with `python3 hardware/make_sheet.py`
(needs `pip install reportlab`) after changing the spacing. 7 columns x 5
rows, robot at the top edge:

```
                 ROBOT
    1   2   3   4   5    R1  Y1
    6   7   8   9  10    R2  Y2
   11  12  13  14  15    R3  Y3
   16  17  18  19  20    R4  Y4
   21  22  23  24  25    R5  Y5      <- bottom row: fills first
                PLAYER
```

Rows are 25 mm apart and columns 40 mm apart. The gripper closes
left-right (across the columns), so the fingers never reach forwards or
back and the rows can be close. That keeps the far corners about 246 mm from
the base (inside the 280 mm rated reach) and the nearest row about 115 mm out
(well clear of the base). If your gripper closes towards / away from the
robot, change `TOOL_DOWN`'s rz to 90 in `robot.py`.

Spacing lives in three places that must match: `ROW_PITCH` / `COLUMN_PITCH`
/ `EDGE_TO_TOP_ROW` in `robot.py`, the same names in `hardware/make_sheet.py`,
and `row_pitch` / `column_pitch` in `hardware/board.scad`.

**Set up first:** `test_mycobot_squares.py`, option 4. It:

1. Explains where to put the sheet and asks for your measurement
   (`SHEET_GAP`).
2. Measures the grip height and offset: you hold the open gripper (or cup)
   on a block on square 13 by hand, and it reads where the end of the arm
   is. The arm's coordinates are for its end plate, not the fingertips, and
   the gripper can sit off to one side, so every starting position is
   shifted by the measured difference. Until this is done the tool won't
   travel to spots: a guessed height can send the arm too high and make it
   hit itself near the base. Saved to `GRIP_Z` and `GRIP_ANCHOR` in
   `robot.py`; option 5 measures again after moving the sheet or tool.
3. Moves the arm above the two far corners and the nearest square to check
   it can reach them. Coordinate moves closer than 80 mm to the base
   (`NEAR_LIMIT`) are refused, because the arm folds over itself there.

The sheet is designed for a 60 mm gap: the far corners are then about
246 mm from the base and the nearest squares about 115 mm.

## End effector

`END_EFFECTOR` in `robot.py`: `"gripper"` (default) or `"suction"`.

- **Gripper**: it should only ever open enough to go around a block, never
  fully, or the fingers hit the blocks next door. Set `GRIPPER_OPEN` /
  `GRIPPER_CLOSED` (`set_gripper_value` numbers, 0-100) with option 6 in
  `test_mycobot_squares.py`: it shows which end is open, lets you try values
  with a block in the fingers, and saves them. Do this before option 4.
  Coloured labels on top are fine.
- **Suction**: the pump is on GPIO 20 and the valve on GPIO 21, set up
  HIGH (LOW = on). `PUMP_ENABLED = False` by default; tick "Suction pump on"
  in the window, or use `pump` in the calibration tool. Keep block tops
  plain for a good seal.

Calibrate with the one you'll play with. They hold a block at different
heights, so the saved angles aren't interchangeable.

## Calibrating

The game moves **only** by replaying saved joint angles from
`calibration.csv`, and refuses to move until every spot is saved:

- squares `1`-`25`: `hover` + `down0`
- stacks `r1`-`r5`, `y1`-`y5`: `hover` + `down0`, `down1`, `down2` (one per
  block in the stack)

After option 4, in `test_mycobot_squares.py`, option 1. The quick loop is
**`n`, `d`, nudge, `save`**, repeated:

1. `n` goes to the next spot that still needs saving (or type one: `13`, `r2`).
   Spots not yet saved start from a guess corrected by the saved spots
   around them, so later spots usually need only a nudge or two.
2. `d` goes down to block height. Calibrate holding a block (on the cup, or
   between the fingers), so the pick and the drop are the same pose.
3. Nudge (`x+2`, `y-1`, `z-0.5`, max 10 mm each) until it's dead centre.
   Or use `teach` to place it by hand, then nudge.
4. `save` stores `down0`, lifts straight up `HOVER_CLEARANCE` and stores `hover`.
5. Stacks: after the bottom block, type `layers`. It asks you to stack 2
   blocks, comes down onto the top one; nudge, `save`; then the same for 3.
6. `check` / `check2` / `check3` replay the saved angles exactly as the game
   does, and log any drift to `check_log.csv`.

`HOVER_CLEARANCE` is 60 mm because travel happens at hover height and must
clear a full 3-high stack (3 x 12 = 36 mm) with a 12 mm block hanging
below the tool, plus a margin.

### Lessons from tic-tac-toe (don't relearn these)

- Coordinate moves are only accurate to a few mm (gravity, approximate IK,
  coords are the flange not the tool tip, tool tilt). Replaying saved angles
  is repeatable, so: nudge with coords, save angles.
- Calibrate drop positions with a block held; put pockets or guides at the
  staging spots; self-centring pockets absorb the last 2-3 mm.
- Stacked blocks: calibrate each layer.
- Make big x/y moves at hover; only fine-tune z (and small x/y, lifted
  slightly) at block height.

## If the robot has a problem mid-move

The move shows on screen first, then the arm places it. If the arm raises an
error, the move is undone on screen and the gripper/pump lets go. Check the
real board matches the screen before carrying on: the block may already be
off its stack (the stack count isn't reduced, so the next move would reach
for it again), or already on the board. If it's out of step, press New game
and restack.

## hardware/board.scad

Self-centring tapered pockets for the 25 squares and the 10 staging spots,
on the same grid as the sheet. `depth` is shallow (3 mm) so gripper fingers
clear the rim; staging pockets are 4 mm to steady a 3-high stack. The
console prints the board size and a reach check. `PART`: `board`, `blocks`
(15 + 15), `both`, or `template` (2D outlines to export as SVG/PDF and print
at 100%).

With the default spacing the board is 261 x 141 mm.
