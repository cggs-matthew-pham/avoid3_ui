"""Avoid 3 rules. Plain functions, no classes.

Same function names as tic_tac_toe_ui/game.py, so main.py works the same way.

THE GAME
5 x 5 board with gravity, like Connect 4: a move is a column, and the piece
drops to the lowest empty square in it. Make 3 of your colour in a line
(across, down or diagonal) and you LOSE. 4 or more in a line also loses,
because it contains 3. A full board with no line is a draw.

Red goes first, so Red plays 13 pieces and Yellow 12 in a full game.

THE BOARD LIST
25 squares, row by row from the top, as the board looks from the player's
side (the top row is the far edge, nearest the robot):

     1  2  3  4  5        indexes  0  1  2  3  4
     6  7  8  9 10                 5  6  7  8  9
    11 12 13 14 15                10 11 12 13 14
    16 17 18 19 20                15 16 17 18 19
    21 22 23 24 25                20 21 22 23 24   <- bottom row, fills first

Players see squares numbered from 1 and columns 1-5; lists count from 0.
"""

import random
import time

EMPTY = 0
RED = 1
YELLOW = 2

# The tic-tac-toe names, so code written for that game still reads right.
X = RED
O = YELLOW

ROWS = 5
COLUMNS = 5
SIZE = ROWS * COLUMNS
LINE_LENGTH = 3  # this many in a line loses


def square_at(row, column):
    return row * COLUMNS + column


def _all_lines():
    """Every run of 3 squares in a straight line: 48 on a 5 x 5 board."""
    lines = []
    for row in range(ROWS):
        for column in range(COLUMNS):
            for d_row, d_column in ((0, 1), (1, 0), (1, 1), (1, -1)):
                end_row = row + d_row * (LINE_LENGTH - 1)
                end_column = column + d_column * (LINE_LENGTH - 1)
                if 0 <= end_row < ROWS and 0 <= end_column < COLUMNS:
                    lines.append(tuple(
                        square_at(row + d_row * i, column + d_column * i)
                        for i in range(LINE_LENGTH)
                    ))
    return lines


LINES = _all_lines()

# The lines through each square. After a move, only these can be new.
LINES_THROUGH = [[line for line in LINES if square in line] for square in range(SIZE)]

board = [EMPTY] * SIZE
current_player = RED


def other(player):
    if player == RED:
        return YELLOW
    return RED


# ---- Moves ----

def landing_square(column, squares=None):
    """Where a piece dropped in this column lands, or None if it's full."""
    if squares is None:
        squares = board
    if not 0 <= column < COLUMNS:
        return None
    for row in range(ROWS - 1, -1, -1):  # from the bottom up
        square = square_at(row, column)
        if squares[square] == EMPTY:
            return square
    return None


def valid_columns(squares=None):
    if squares is None:
        squares = board
    # A column has room if its top square is empty.
    return [column for column in range(COLUMNS) if squares[column] == EMPTY]


def is_valid_move(column):
    return landing_square(column) is not None


def make_move(column):
    """Drop the current player's piece in a column (0-4).

    Returns the square (0-24) it landed on, or None if the column is full.
    main.py needs the square: the robot places the piece there, and an
    error means setting that square back to EMPTY.
    """
    square = landing_square(column)
    if square is None:
        return None
    board[square] = current_player
    return square


# ---- Who has lost ----

def makes_line(squares, square, player):
    """True if `player` has 3 in a line through `square`."""
    for a, b, c in LINES_THROUGH[square]:
        if squares[a] == squares[b] == squares[c] == player:
            return True
    return False


def losing_line(squares=None):
    """The first line of 3 on the board, or None. For highlighting."""
    if squares is None:
        squares = board
    for a, b, c in LINES:
        if squares[a] != EMPTY and squares[a] == squares[b] == squares[c]:
            return (a, b, c)
    return None


def winner_of(squares):
    """The WINNER: the player who did not make 3 in a line. EMPTY if nobody yet.

    The game stops at the first line, and only the player who just moved can
    have made one, so there is never a line of each colour.
    """
    line = losing_line(squares)
    if line is None:
        return EMPTY
    return other(squares[line[0]])


def loser_of(squares):
    line = losing_line(squares)
    if line is None:
        return EMPTY
    return squares[line[0]]


def check_winner():
    return winner_of(board)


def is_full():
    return EMPTY not in board


def next_player():
    global current_player
    current_player = other(current_player)


def reset():
    global current_player
    for square in range(SIZE):
        board[square] = EMPTY
    current_player = RED


# ---- Computer player ----
#
# Tic-tac-toe can look at every possible game. Avoid 3 can't: there are far
# too many. So "hard" looks a set number of moves ahead (alpha-beta search,
# a faster minimax), scores the positions it reaches with a rule of thumb,
# and keeps looking one move deeper until its time runs out.

THINK_SECONDS = 2.0   # time limit for a hard move; the Pi is slower than a laptop
WIN = 1000            # score for a won game; a quicker win scores a bit more

CENTRE_FIRST = [2, 1, 3, 0, 4]  # try the middle columns first: speeds up the search


def safe_columns(squares, player):
    """Columns `player` can play without making 3 in a line."""
    safe = []
    for column in valid_columns(squares):
        square = landing_square(column, squares)
        squares[square] = player
        if not makes_line(squares, square, player):
            safe.append(column)
        squares[square] = EMPTY
    return safe


def evaluate(squares, me):
    """Rule of thumb: how good this position looks for `me` (no look-ahead).

    An empty square where a piece would make 3 for one player is "poisoned"
    for that player: they can never play there, so they will run out of
    safe moves sooner. Count the squares poisoned for each side; more for
    the opponent is better for me.
    """
    you = other(me)
    score = 0
    for square in range(SIZE):
        if squares[square] != EMPTY:
            continue
        for player, sign in ((me, -1), (you, 1)):
            squares[square] = player
            if makes_line(squares, square, player):
                score += sign
            squares[square] = EMPTY
    return score


def _search(squares, player, depth, alpha, beta, ply, deadline, memo):
    """Alpha-beta search. Returns the score for `player`, who is to move.

    Scores are from the mover's point of view, so the opponent's score is
    the negative of ours ("negamax"). alpha/beta are the best scores each
    side is already sure of; a move that can't beat them isn't explored.
    """
    if time.monotonic() > deadline:
        raise TimeoutError  # caught in best_move

    key = tuple(squares)
    remembered = memo.get(key)
    if remembered is not None and remembered[0] >= depth:
        _, flag, value = remembered
        if flag == "exact":
            return value
        if flag == "low":
            alpha = max(alpha, value)
        else:
            beta = min(beta, value)
        if alpha >= beta:
            return value

    columns = valid_columns(squares)
    if not columns:
        return 0  # board full, nobody made 3: draw

    start_alpha = alpha
    best = -WIN - 1
    for column in sorted(columns, key=CENTRE_FIRST.index):
        square = landing_square(column, squares)
        squares[square] = player
        if makes_line(squares, square, player):
            score = -(WIN - ply)                       # I just lost
        elif EMPTY not in squares:
            score = 0                                  # draw
        elif depth <= 1:
            score = evaluate(squares, player)
        else:
            score = -_search(squares, other(player), depth - 1,
                             -beta, -alpha, ply + 1, deadline, memo)
        squares[square] = EMPTY

        best = max(best, score)
        alpha = max(alpha, score)
        if alpha >= beta:
            break  # the opponent won't allow this line, so stop looking

    if best <= start_alpha:
        flag = "high"   # at most this good
    elif best >= beta:
        flag = "low"    # at least this good
    else:
        flag = "exact"
    memo[key] = (depth, flag, best)
    return best


def score_columns(player, depth, deadline, memo, order):
    """Score every column at this depth. Raises TimeoutError if time runs out."""
    squares = list(board)
    scores = {}
    for column in order:
        square = landing_square(column, squares)
        squares[square] = player
        if makes_line(squares, square, player):
            score = -WIN
        elif EMPTY not in squares:
            score = 0
        elif depth <= 1:
            score = evaluate(squares, player)
        else:
            score = -_search(squares, other(player), depth - 1,
                             -WIN - 1, WIN + 1, 1, deadline, memo)
        squares[square] = EMPTY
        scores[column] = score
    return scores


def best_move(player, seconds=None):
    """Hard: look as many moves ahead as time allows. Returns a column (0-4)."""
    if seconds is None:
        seconds = THINK_SECONDS
    deadline = time.monotonic() + seconds
    memo = {}
    order = sorted(valid_columns(), key=CENTRE_FIRST.index)
    scores = {column: 0 for column in order}
    empty = board.count(EMPTY)

    for depth in range(1, empty + 1):
        try:
            scores = score_columns(player, depth, deadline, memo, order)
        except TimeoutError:
            break  # keep the scores from the last depth that finished
        # Look at the best column first next time: alpha-beta then cuts more.
        order.sort(key=lambda column: -scores[column])
        top = max(scores.values())
        if abs(top) > WIN - SIZE:
            break  # the result is already certain (a forced win or loss)

    top = max(scores.values())
    # Several columns can be equally good; pick one at random for variety.
    return random.choice([column for column, score in scores.items() if score == top])


def easy_move(player):
    """Easy: any column that doesn't lose straight away, if there is one."""
    safe = safe_columns(list(board), player)
    if safe:
        return random.choice(safe)
    return random.choice(valid_columns())  # every move loses


def computer_move(player, level):
    if level == "hard":
        return best_move(player)
    return easy_move(player)
