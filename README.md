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
| `hardware/board.scad` | Pocket board, blocks and a printable paper template. |

## The layout

Matches the printed sheet `avoid_three_final_A4_landscape.pdf`: 7 columns x 5
rows on a 40 mm grid, robot at the far (top) edge.

```
                 ROBOT
    1   2   3   4   5    R1  Y1
    6   7   8   9  10    R2  Y2
   11  12  13  14  15    R3  Y3
   16  17  18  19  20    R4  Y4
   21  22  23  24  25    R5  Y5      <- bottom row: fills first
                PLAYER
```

**Set up the sheet first:** `test_mycobot_squares.py`, option 4. It explains
where to put the sheet, asks for your measurement, and moves the arm above
the nearest square and the two far corners to check it can reach them.

- Landscape, title edge against the robot, Red and Yellow on the player's right.
- Centre of the robot's base in line with column 4 (the middle of the sheet).
- Centre of the base's turntable 40-60 mm from the paper edge (`SHEET_GAP`
  in `robot.py`; option 4 can save it for you).
- Then tape the sheet down and mark around the base. Calibration saves joint
  angles, so if the sheet moves afterwards every move misses by that much.

At a 60 mm gap the far corners (square 21 and Y5) are about 273 mm from the
base, inside the arm's rated 280 mm. Portrait would put them over 320 mm.

## End effector

`END_EFFECTOR` in `robot.py`: `"gripper"` (default) or `"suction"`.

- **Gripper**: `GRIPPER_OPEN` / `GRIPPER_CLOSED` are `set_gripper_value`
  numbers (0-100). Check which end is open with `g 0` / `g 100` in the
  calibration tool first. Open only as wide as needed, so the fingers miss
  the blocks next door. Coloured labels on top are fine.
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

After option 4, in `test_mycobot_squares.py`, option 1:

1. Type a spot (`13`, `r2`). The arm goes to hover above it.
2. `d` goes down to a block on the table. Calibrate holding a block (on the
   cup, or between the fingers), so the pick and the drop are the same pose.
3. Nudge (`x+2`, `y-1`, `z-0.5`, max 10 mm each) until it's dead centre.
   Or use `teach` to place it by hand, then nudge.
4. `save` stores `down0`, lifts straight up `HOVER_CLEARANCE` and stores `hover`.
5. Stacks only: put 2 blocks on the spot, `d2`, nudge, `save` (stores `down1`).
   Then 3 blocks, `d3`, nudge, `save` (stores `down2`).
6. `check` / `check2` / `check3` replay the saved angles exactly as the game
   does, and log any drift to `check_log.csv`.

`HOVER_CLEARANCE` is 70 mm because travel happens at hover height and must
clear a full 3-high stack (45 mm) with a block hanging below the tool.

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

At 40 mm spacing the board is 296 x 216 mm, bigger than most print beds; at
32 mm it is 240 x 176 mm.
