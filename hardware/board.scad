// Avoid 3 board with self-centring pockets, for the myCobot 280.
//
// A 5 x 5 board plus a Red and a Yellow staging column of 5 pockets, each
// holding a stack of 3 blocks. Same layout as the printed sheet
// (avoid3_sheet_A4.pdf, from make_sheet.py): 7 columns by 5 rows, rows
// 25 mm apart and columns 40 mm apart. The gripper closes left-right, so
// only the columns need room for the open fingers.
//
// A block dropped a couple of mm off-centre lands on a sloped wall and
// slides down onto the flat floor. Staging pockets do the same for the
// bottom block of each stack, so every stack starts in the same place.
//
// Open in OpenSCAD: F5 to preview, F6 to render, then File > Export > STL.
// Set PART below to export the board and the blocks separately.
// PART = "template" draws a flat paper template from the same numbers:
// render (F6), then File > Export > SVG or PDF, and print at 100%.
//
// Layout, seen from the player's side with the robot at the far edge:
//
//                  ROBOT
//     1   2   3   4   5    R1  Y1
//     6   7   8   9  10    R2  Y2
//    11  12  13  14  15    R3  Y3
//    16  17  18  19  20    R4  Y4
//    21  22  23  24  25    R5  Y5      <- bottom row: fills first
//
// The engraved labels match the names in test_mycobot_squares.py, so
// calibrate "13" at the pocket labelled 13, "r1" at R1, and so on.
//
// robot.py uses the same layout for its starting positions. If you change
// row_pitch, column_pitch or staging_gap here, change ROW_PITCH and
// COLUMN_PITCH in robot.py (and make_sheet.py) to match.
//
// REACH: the console line "Reach:" gives the distance from the robot base
// to the farthest pocket. Keep it under about 280 mm (the rated reach; the
// arm has to point straight down there). With these defaults it is about
// 246 mm. Check the gripper fingers still fit between neighbouring blocks
// before making the pitches smaller.

/* [What to show / export] */
PART = "both";          // "board", "blocks", "both" (preview only) or "template"

/* [Block] */
block      = 15;        // block width (mm). Measure real blocks if not printing them.
block_h    = 12;        // block height
block_cham = 1.5;       // chamfer on the block's bottom edges, so it slides in
blocks_per_player = 15; // 5 stacks of 3

/* [Pockets] */
clearance  = 0.8;       // floor = block + this. 0.6-1.0 for FDM; less wedges, more rattles.
flare      = 3.5;       // extra opening width per side at the top = capture range
depth      = 3;         // board pocket depth. Shallow, so gripper fingers clear the rim.
                        // 5 is fine for the suction cup.
staging_depth = 4;      // staging pockets: a little deeper to steady a 3-high stack

/* [Layout] */
row_pitch      = 25;    // centre-to-centre, towards / away from the robot. Sheet: 25.
column_pitch   = 40;    // centre-to-centre, left / right. Sheet: 40. Room for the open fingers.
staging_gap    = 5;     // extra room before Red and again before Yellow (= STAGING_EXTRA)
margin         = 8;     // border around everything
thickness      = 7;     // board thickness (floor under pockets = thickness - depth)

/* [Robot position, for the reach check only] */
robot_gap          = 115; // base centre to the centre of the top row (= GRID_NEAR_X = SHEET_GAP + EDGE_TO_TOP_ROW)
robot_centre_column = 3;  // pocket column (0-6) in line with the base: 3 = board column 4

/* [Labels] */
labels       = true;
label_size   = 4;       // text height on the pocket floor
label_depth  = 0.4;     // engraved depth; too deep and the block may rock

/* [Template] */
template_square = 20;   // outline square size on the paper template (sheet: 20)
template_line   = 0.4;

$fn = 48;

rows       = 5;
columns    = 5;
stacks     = 5;

floor_w   = block + clearance;
opening_w = floor_w + 2 * flare;

// Column centres across the board, left to right from the player's side:
// 5 board columns, then Red, then Yellow.
function column_x(c) = margin + column_pitch / 2 + c * column_pitch
                       + (c >= columns ? staging_gap : 0) + (c >= columns + 1 ? staging_gap : 0);
function row_y(r)    = board_len - margin - row_pitch / 2 - r * row_pitch;   // row 0 nearest the robot

board_w   = 2 * margin + (columns + 2) * column_pitch + 2 * staging_gap;   // left -> right
board_len = 2 * margin + rows * row_pitch;                       // player -> robot

function grid_xy(i)          = [column_x(i % columns), row_y(floor(i / columns))];
function staging_xy(side, i) = [column_x(columns + side), row_y(i)];  // side 0 = Red, 1 = Yellow

assert(opening_w < min(row_pitch, column_pitch) - 2, "Pockets overlap: raise the pitch or lower flare");
assert(depth < thickness - 1 && staging_depth < thickness - 1, "Pocket too deep for the board thickness");

// ---- Reach check ----
function robot_dist(c, r) =
    let(dx = (c - robot_centre_column) * column_pitch + (c >= columns ? staging_gap : 0)
             + (c >= columns + 1 ? staging_gap : 0)
             - (robot_centre_column >= columns ? staging_gap : 0),
        dy = robot_gap + r * row_pitch)
    sqrt(dx * dx + dy * dy);

reach = max([for (c = [0:columns + 1], r = [0:rows - 1]) robot_dist(c, r)]);

echo(str("Board ", board_w, " x ", board_len, " mm. Floor ", floor_w,
         " mm, opening ", opening_w, " mm, capture range +/-", flare, " mm."));
echo(str("Reach: farthest pocket ", round(reach), " mm from the robot base",
         reach > 280 ? "  <-- probably too far: lower row_pitch or robot_gap" : ""));
echo(str("Stack of 3: ", 3 * block_h, " mm tall. HOVER_CLEARANCE in robot.py must clear it."));

// ---- Pocket: flat floor, walls sloping outward to the opening ----
module pocket(label = "", d = depth) {
    translate([0, 0, thickness - d]) {
        linear_extrude(height = d + 0.01, scale = opening_w / floor_w)
            square(floor_w, center = true);
        if (labels && label != "")
            translate([0, 0, -label_depth])
                linear_extrude(height = label_depth + 0.01)
                    text(label, size = label_size, halign = "center", valign = "center",
                         font = "Liberation Sans:style=Bold");
    }
}

module board() {
    difference() {
        cube([board_w, board_len, thickness]);

        for (i = [0:rows * columns - 1])
            translate(grid_xy(i)) pocket(str(i + 1));

        for (side = [0:1], i = [0:stacks - 1])
            translate(staging_xy(side, i)) pocket(str(side == 0 ? "R" : "Y", i + 1), staging_depth);

        // Robot edge label, so the board goes down the right way round.
        if (labels)
            translate([column_x(robot_centre_column), board_len - margin / 2,
                       thickness - label_depth])
                linear_extrude(height = label_depth + 0.01)
                    text("ROBOT", size = 3.5, halign = "center", valign = "center",
                         font = "Liberation Sans:style=Bold");
    }
}

// ---- Block: flat top for the suction cup, chamfered bottom edges ----
module block_piece() {
    hull() {
        translate([block_cham, block_cham, 0])
            cube([block - 2 * block_cham, block - 2 * block_cham, 0.01]);
        translate([0, 0, block_cham])
            cube([block, block, block_h - block_cham]);
    }
}

module blocks() {
    // 15 Red + 15 Yellow. Print each set in its own colour (or stick on the
    // sheet's coloured labels; keep the tops plain if using the suction cup).
    per_row = 5;
    for (set = [0:1], i = [0:blocks_per_player - 1])
        translate([(i % per_row) * (block + 5),
                   (set * 3 + floor(i / per_row)) * (block + 5), 0])
            block_piece();
}

// ---- Paper template: outlines and labels, 1:1 ----
module outline(size) {
    difference() {
        square(size, center = true);
        square(size - 2 * template_line, center = true);
    }
}

module template_spot(label) {
    outline(template_square);
    difference() {                      // where the block sits
        circle(d = block);
        circle(d = block - 2 * template_line);
    }
    translate([0, -template_square / 2 - 3])
        text(label, size = 2.5, halign = "center", valign = "center",
             font = "Liberation Sans");
}

module template() {
    difference() {                      // board edge, for lining up the robot
        square([board_w, board_len]);
        translate([template_line, template_line])
            square([board_w - 2 * template_line, board_len - 2 * template_line]);
    }
    for (i = [0:rows * columns - 1])
        translate(grid_xy(i)) template_spot(str(i + 1));
    for (side = [0:1], i = [0:stacks - 1])
        translate(staging_xy(side, i)) template_spot(str(side == 0 ? "R" : "Y", i + 1));
    translate([column_x(robot_centre_column), board_len - margin / 2])
        text("ROBOT", size = 3.5, halign = "center", valign = "center",
             font = "Liberation Sans:style=Bold");
}

if (PART == "board") board();
else if (PART == "blocks") blocks();
else if (PART == "template") template();
else {
    board();
    translate([0, -6 * (block + 5) - 10, 0]) color("orange") blocks();
}
