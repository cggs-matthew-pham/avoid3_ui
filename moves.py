"""Turn what a player types (or later, says) into a column number 0-4.

In Avoid 3 a move is just a column: the piece drops to the lowest empty
square. Columns are numbered 1-5 for players, left to right as the player
sees the board:

    1   2   3   4   5
    far         far
    left middle right

Accepted: "3", "three", "column 3", "col 3", "drop it in 3", "third",
"left", "far left", "middle", "centre", "right", "left of centre",
"centre left", "middle right". Returns None if it can't tell which column.

Voice input only needs to turn speech into text and call parse_move().
"""

COLUMNS = 5

NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
    "1st": 1, "2nd": 2, "3rd": 3, "4th": 4, "5th": 5,
    # common speech-to-text slips
    "won": 1, "to": 2, "too": 2, "tree": 3, "free": 3,
    "for": 4, "fore": 4, "fight": 5,
}
SLIPS = {"won", "to", "too", "tree", "free", "for", "fore", "fight"}

LEFT = {"left"}
RIGHT = {"right"}
MIDDLE = {"middle", "centre", "center", "mid", "central"}
FAR = {"far", "edge", "outside"}

FILLER = {
    "column", "col", "the", "in", "into", "drop", "it", "go", "please",
    "number", "put", "piece", "a", "my", "play", "of", "one's", "lane",
}


def _number(word):
    if word.isdigit():
        return int(word)
    return NUMBER_WORDS.get(word)


def parse_move(text):
    words = (
        text.lower()
        .replace("-", " ")
        .replace(",", " ")
        .replace(".", " ")
        .split()
    )
    words = [w for w in words if w not in FILLER]

    # "to" and "for" can be slips for 2 and 4, or ordinary words, as in
    # "go to 3". If a clear number is there, it's the move.
    clear = [w for w in words if w.isdigit() or (w in NUMBER_WORDS and w not in SLIPS)]
    if len(words) > 1 and len(clear) == 1:
        words = clear

    if not words:
        return None

    # A single number or position word.
    if len(words) == 1:
        word = words[0]
        number = _number(word)
        if number is not None:
            if 1 <= number <= COLUMNS:
                return number - 1
            return None
        if word in LEFT:
            return 0
        if word in RIGHT:
            return COLUMNS - 1
        if word in MIDDLE:
            return COLUMNS // 2
        return None

    # Two words: "far left", "left middle", "middle right", "right of centre".
    if len(words) == 2:
        pair = set(words)
        sides = pair & (LEFT | RIGHT)
        if len(sides) != 1 or len(pair) != 2:
            return None
        rest = (pair - sides).pop()
        side = sides.pop()
        if rest in FAR:
            return 0 if side in LEFT else COLUMNS - 1
        if rest in MIDDLE:
            return COLUMNS // 2 - 1 if side in LEFT else COLUMNS // 2 + 1

    return None
