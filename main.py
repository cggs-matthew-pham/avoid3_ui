"""Avoid 3: two player or against the computer, with or without the robot.

Every move shows on screen first, then (if the robot is on) the arm places
the piece. Moves can be clicked or typed (see moves.py).

Settings in the window apply when you press New game. The suction pump
checkbox (suction cup only) applies immediately.
"""

import game
import moves
import ui

# The robot connects to the arm as soon as it's imported, so try it here:
# on a laptop with no arm, the game still runs on screen.
try:
    import robot
except Exception as error:  # no pymycobot, no serial port, no GPIO...
    robot = None
    print(f"Robot not available, playing on screen only: {error}")

COMPUTER_LEVELS = {1: "easy", 2: "hard"}

robot_active = False   # set on New game from the checkbox
computer = None        # game.RED, game.YELLOW, or None for two player
level = None
game_over = False
busy = False


def player_name(player):
    return ui.NAMES[player]


def turn_message():
    name = player_name(game.current_player)
    if computer is None:
        return f"{name} to move"
    if game.current_player == computer:
        return f"Computer ({name}) thinking..."
    return f"Your move ({name})"


def set_busy(value):
    global busy
    busy = value
    ui.set_busy(value)


def play(column):
    """Make a move for whoever's turn it is. Returns True if it happened."""
    global game_over

    square = game.make_move(column)
    if square is None:
        ui.set_status(f"Column {column + 1} is full.")
        return False

    ui.update_board(game.board)  # on screen first, so you see what's coming

    if robot_active:
        ui.set_status(f"Robot placing {player_name(game.current_player)} "
                      f"in column {column + 1}...")
        set_busy(True)
        ui.refresh()
        try:
            robot.place_piece(square, game.current_player)
        except Exception as error:
            game.board[square] = game.EMPTY  # undo: the piece never got placed
            ui.update_board(game.board)
            ui.set_status(f"Robot problem: {error}")
            print(error)
            set_busy(False)
            return False
        set_busy(False)

    winner = game.check_winner()
    if winner != game.EMPTY:
        game_over = True
        ui.update_board(game.board, game.losing_line())
        loser = game.other(winner)
        if computer is None:
            ui.set_status(f"{player_name(loser)} made 3 in a row. {player_name(winner)} wins!")
        elif winner == computer:
            ui.set_status("You made 3 in a row. Computer wins!")
        else:
            ui.set_status("Computer made 3 in a row. You win!")
        return True

    if game.is_full():
        game_over = True
        ui.set_status("Board full, nobody made 3. Draw!")
        return True

    game.next_player()
    ui.set_status(turn_message())
    return True


def computer_turn():
    if game_over or game.current_player != computer:
        return
    set_busy(True)
    ui.refresh()  # show "thinking..." before the search blocks the window
    column = game.computer_move(computer, level)
    set_busy(False)
    if not play(column):
        ui.set_status(ui.status_label.cget("text") + " Press New game to restart.")


def human_move(column):
    if busy or game_over:
        return
    if game.current_player == computer:
        ui.set_status("Wait for the computer's move.")
        return
    if play(column) and not game_over and computer is not None:
        set_busy(True)
        ui.set_status(turn_message())
        ui.later(400, computer_turn)  # short pause so the move reads as a reply


def column_clicked(column):
    human_move(column)


def move_typed(text):
    column = moves.parse_move(text)
    if column is None:
        ui.set_status(f'Didn\'t understand "{text}". Try 1-5 or "middle".')
        return
    human_move(column)


def pump_toggled(on):
    if robot is not None:
        robot.set_pump_enabled(on)


def new_game():
    global robot_active, computer, level, game_over

    game.reset()
    game_over = False

    mode = ui.get_mode()
    if mode == 0:
        computer = None
        level = None
    else:
        level = COMPUTER_LEVELS[mode]
        computer = game.RED if ui.computer_first() else game.YELLOW

    robot_active = robot is not None and ui.robot_on()
    ui.update_board(game.board)

    if robot_active:
        ui.set_status("Robot going home... put the pieces back in their stacks.")
        set_busy(True)
        ui.refresh()
        try:
            robot.reset()
        except Exception as error:
            robot_active = False
            ui.set_status(f"Robot problem, playing on screen: {error}")
            print(error)
            set_busy(False)
            return
        set_busy(False)

    ui.set_status(turn_message())
    if computer == game.RED:
        set_busy(True)
        ui.later(400, computer_turn)


suction = robot is not None and robot.END_EFFECTOR == "suction"

ui.build(
    on_column=column_clicked,
    on_text=move_typed,
    on_reset=new_game,
    on_pump=pump_toggled,
    robot_available=robot is not None,
    pump_available=suction,
    pump_on=suction and robot.PUMP_ENABLED,
)

new_game()
ui.run()
