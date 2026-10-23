"""Make the printable Avoid 3 sheet (A4 landscape PDF), matching robot.py.

    pip install reportlab        # once
    python3 make_sheet.py        # writes avoid3_sheet_A4.pdf next to this file

Page 1 is the board: 5 x 5 squares plus a Red and a Yellow column of 5
stacking spots, with the robot at the top edge. Page 2 is cut-out labels
for the tops of the blocks.

The layout is compressed towards the middle: rows close together, columns
wider apart, because the gripper's fingers close left-right (across the
columns) and never reach forwards or back. That keeps the far corners
inside the arm's reach and the near row away from the base.

If you change ROW_PITCH, COLUMN_PITCH or EDGE_TO_TOP_ROW here, change the
same numbers in robot.py (and hardware/board.scad if 3D printing).
"""

import os

from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

# ---- Layout (must match robot.py) ----
ROW_PITCH = 25          # mm between row centres (towards / away from the robot)
COLUMN_PITCH = 35       # mm between column centres (left / right)
EDGE_TO_TOP_ROW = 55    # mm from the robot edge of the paper to the centre of row 1-5
SHEET_GAP = 60          # mm from the robot's turntable centre to the robot edge

SQUARE = 20             # mm, outline square
CIRCLE = 15             # mm, where the block sits

ROWS = 5
COLUMNS = 5
STAGING = {"RED": 5, "YELLOW": 6}   # sheet column (0-6) of each staging column
CENTRE_COLUMN = 3                   # in line with the robot: squares 4, 9, 14, 19, 24

# ---- Style (from avoid_three_final_A4_landscape.pdf) ----
GREY = (0.4, 0.439, 0.522)
RED = (0.839, 0.239, 0.263)
YELLOW = (0.878, 0.686, 0.141)
INK = (0.12, 0.16, 0.22)
LINE = 0.75

PAGE_W, PAGE_H = 297, 210   # A4 landscape, mm

HERE = os.path.dirname(os.path.abspath(__file__))
OUTPUT = os.path.join(HERE, "avoid3_sheet_A4.pdf")


def column_x(sheet_column):
    """Centre of a column, mm from the page's left edge."""
    return PAGE_W / 2 + (sheet_column - CENTRE_COLUMN) * COLUMN_PITCH


def row_y(row):
    """Centre of a row, mm down from the robot (top) edge."""
    return EDGE_TO_TOP_ROW + row * ROW_PITCH


def spot(c, x, y, colour, label):
    """One square + circle, centred at (x, y) mm from the top-left of the page."""
    c.setStrokeColorRGB(*colour)
    c.setLineWidth(LINE)
    c.rect((x - SQUARE / 2) * mm, (PAGE_H - y - SQUARE / 2) * mm, SQUARE * mm, SQUARE * mm)
    c.circle(x * mm, (PAGE_H - y) * mm, CIRCLE / 2 * mm)
    # Small name in the top-left corner, outside the circle.
    c.setFillColorRGB(*colour)
    c.setFont("Helvetica-Bold", 5.5)
    c.drawString((x - SQUARE / 2 + 1.2) * mm, (PAGE_H - y + SQUARE / 2 - 3.2) * mm, label)


def text(c, x, y, words, size=8, bold=False, colour=INK, align="left"):
    c.setFillColorRGB(*colour)
    c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
    draw = {"left": c.drawString, "centre": c.drawCentredString, "right": c.drawRightString}
    draw[align](x * mm, (PAGE_H - y) * mm, words)


def board_page(c):
    centre = column_x(CENTRE_COLUMN)

    # Robot edge: alignment mark and instructions.
    c.setFillColorRGB(*INK)
    path = c.beginPath()
    path.moveTo(centre * mm, PAGE_H * mm)
    path.lineTo((centre - 3) * mm, (PAGE_H - 5) * mm)
    path.lineTo((centre + 3) * mm, (PAGE_H - 5) * mm)
    path.close()
    c.drawPath(path, fill=1, stroke=0)
    text(c, centre, 9, "ROBOT", 8, bold=True, align="centre")
    text(c, centre, 13.5, f"Turntable centre {SHEET_GAP} mm from this edge, in line with the mark",
         6.5, colour=GREY, align="centre")
    c.setStrokeColorRGB(*GREY)
    c.setLineWidth(0.4)
    c.setDash(2, 2)
    top_of_grid = row_y(0) - SQUARE / 2
    c.line(centre * mm, (PAGE_H - 16) * mm, centre * mm, (PAGE_H - top_of_grid + 1) * mm)
    c.setDash()

    text(c, 15, 28, "AVOID THREE  |  5 x 5", 12, bold=True)
    for name, column in STAGING.items():
        colour = RED if name == "RED" else YELLOW
        text(c, column_x(column), top_of_grid - 3, name, 8, bold=True, colour=colour,
             align="centre")

    for row in range(ROWS):
        for column in range(COLUMNS):
            number = row * COLUMNS + column + 1
            spot(c, column_x(column), row_y(row), GREY, str(number))
        for name, column in STAGING.items():
            colour = RED if name == "RED" else YELLOW
            spot(c, column_x(column), row_y(row), colour, f"{name[0]}{row + 1}")

    # Column numbers on the player's side.
    bottom = row_y(ROWS - 1) + SQUARE / 2
    for column in range(COLUMNS):
        text(c, column_x(column), bottom + 6, str(column + 1), 10, bold=True, align="centre")
    text(c, column_x(0) - SQUARE / 2, bottom + 13,
         "Lowest available square in chosen column (row 21-25 fills first); "
         "3 of your colour in a line loses.", 7, colour=GREY)

    # Footer: sizes and a scale check.
    footer = PAGE_H - 8
    text(c, 15, footer,
         f"{SQUARE} x {SQUARE} mm squares  |  {CIRCLE} mm circles  |  rows {ROW_PITCH} mm, "
         f"columns {COLUMN_PITCH} mm apart  |  Print at 100% (not 'fit to page')",
         6.5, colour=GREY)
    bar_x = PAGE_W - 15 - 50
    c.setStrokeColorRGB(*INK)
    c.setLineWidth(0.6)
    y = (PAGE_H - footer + 1) * mm
    c.line(bar_x * mm, y, (bar_x + 50) * mm, y)
    for tick in (0, 50):
        c.line((bar_x + tick) * mm, y - 1.2 * mm, (bar_x + tick) * mm, y + 1.2 * mm)
    text(c, bar_x + 25, footer - 2, "this bar should measure 50 mm", 6, colour=GREY, align="centre")


def labels_page(c):
    text(c, 15, 12, "AVOID THREE  |  CUTOUT LABELS", 12, bold=True)
    text(c, 15, 20, f"{SQUARE} x {SQUARE} mm squares  |  {CIRCLE} mm diameter circles  |  "
         "28 red + 28 yellow", 8)
    text(c, 15, 25, "Print at 100%. Stick one on top of each block (15 per colour, plus spares).", 8)
    per_row, pitch = 7, 22
    start_x = PAGE_W / 2 - (per_row - 1) * pitch / 2
    for i in range(56):
        row, column = divmod(i, per_row)
        x, y = start_x + column * pitch, 40 + row * pitch
        c.setStrokeColorRGB(*GREY)
        c.setLineWidth(0.65)
        c.rect((x - SQUARE / 2) * mm, (PAGE_H - y - SQUARE / 2) * mm, SQUARE * mm, SQUARE * mm)
        c.setFillColorRGB(*(RED if i < 28 else YELLOW))
        c.circle(x * mm, (PAGE_H - y) * mm, CIRCLE / 2 * mm, stroke=0, fill=1)


def main():
    c = canvas.Canvas(OUTPUT, pagesize=(PAGE_W * mm, PAGE_H * mm))
    c.setTitle("Avoid Three - board and labels")
    board_page(c)
    c.showPage()
    labels_page(c)
    c.showPage()
    c.save()
    print(f"Wrote {OUTPUT}")
    far = ((SHEET_GAP + row_y(ROWS - 1)) ** 2 + ((CENTRE_COLUMN) * COLUMN_PITCH) ** 2) ** 0.5
    near = SHEET_GAP + row_y(0)
    print(f"From the turntable centre: nearest square {near:.0f} mm, far corners {far:.0f} mm.")


if __name__ == "__main__":
    main()
