"""Checks for game.py and moves.py. No robot or window needed:

    python3 test_game.py

Prints OK at the end if everything passed.
"""

import game
import moves


def board_from(rows):
    """Build a board from 5 strings, top row first: R, Y or . for empty."""
    pieces = {".": game.EMPTY, "R": game.RED, "Y": game.YELLOW}
    return [pieces[ch] for row in rows for ch in row]


def drop(*columns):
    """Reset, then play these columns (numbered 1-5) in turn."""
    game.reset()
    for column in columns:
        assert game.make_move(column - 1) is not None, f"column {column} full"
        game.next_player()


def test_gravity():
    game.reset()
    assert game.make_move(2) == 22        # column 3, bottom row
    game.next_player()
    assert game.make_move(2) == 17        # lands on top of it
    drop(1, 1, 1, 1, 1)
    assert game.board[0] != game.EMPTY    # column 1 now full to the top
    assert not game.is_valid_move(0)
    assert game.make_move(0) is None
    assert game.valid_columns() == [1, 2, 3, 4]


def test_three_loses():
    across = board_from([".....", ".....", ".....", "YY...", "RRR.."])
    assert game.loser_of(across) == game.RED
    assert game.winner_of(across) == game.YELLOW

    down = board_from([".....", ".....", "Y....", "Y.R..", "Y.R.."])
    assert game.winner_of(down) == game.RED

    diagonal = board_from([".....", ".....", "..R..", ".RY..", "RYY.."])
    assert game.winner_of(diagonal) == game.YELLOW

    other_diagonal = board_from([".....", ".....", "Y....", "RY...", "RRY.."])
    assert game.winner_of(other_diagonal) == game.RED

    two = board_from([".....", ".....", ".....", ".....", "RR.RR"])
    assert game.winner_of(two) == game.EMPTY  # gap in the middle: no line


def test_four_loses():
    four = board_from([".....", ".....", ".....", ".....", "YYYY."])
    assert game.winner_of(four) == game.RED


def test_played_game():
    # Red: 1, 2, 3 along the bottom loses.
    drop(1, 1, 2, 2)
    game.make_move(2)
    assert game.check_winner() == game.YELLOW
    assert game.losing_line() == (20, 21, 22)


def test_draw():
    full = board_from(["RRYYR", "YYRRY", "RRYYR", "YYRRY", "RRYYR"])
    assert game.winner_of(full) == game.EMPTY
    assert full.count(game.RED) == 13 and full.count(game.YELLOW) == 12
    game.board[:] = full
    assert game.is_full()


def test_lines():
    assert len(game.LINES) == 48          # 15 across, 15 down, 18 diagonal
    assert len(game.LINES_THROUGH[12]) == 12   # the centre square
    assert len(game.LINES_THROUGH[0]) == 3     # a corner


def test_easy_avoids_losing():
    # Red to move. Columns 1 and 3 complete a line of 3 for Red.
    game.board[:] = board_from([".....", ".....", ".....", "YY...", "RR.YY"])
    for _ in range(50):
        assert game.easy_move(game.RED) != 2


def test_hard_avoids_losing():
    game.board[:] = board_from([".....", ".....", ".....", "YY...", "RR.YY"])
    for _ in range(5):
        assert game.best_move(game.RED, seconds=0.3) != 2


def test_computer_always_legal():
    game.reset()
    game.board[:] = board_from(["R.YYR", "Y.RRY", "RRYYR", "YYRRY", "RRYYR"])
    assert game.winner_of(game.board) == game.EMPTY
    for level in ("easy", "hard"):
        assert game.computer_move(game.RED, level) == 1  # only column left


def test_moves():
    cases = {
        "3": 2, "three": 2, "Column 3": 2, "col 5": 4, "drop it in 1": 0,
        "  4 ": 3, "two": 1, "too": 1, "for": 3, "tree": 2, "fifth": 4,
        "left": 0, "far left": 0, "right": 4, "far right": 4,
        "middle": 2, "centre": 2, "the middle column": 2,
        "left of centre": 1, "centre left": 1, "middle right": 3,
        "right of middle": 3, "go to 3": 2, "for": 3, "number for": 3,
        "6": None, "0": None, "banana": None, "": None, "top left": None,
    }
    for text, expected in cases.items():
        got = moves.parse_move(text)
        assert got == expected, f"{text!r}: expected {expected}, got {got}"


if __name__ == "__main__":
    tests = [value for name, value in list(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
        print(f"  passed {test.__name__}")
    game.reset()
    print("OK")
