import curses
import time

# Define the QDATA list with the ASCII art
QDATA = [
    "                 _/_/_/      _/_/_/                          ",
    "               _/     _/   _/     _/     _/_/     _/   _/    ",
    "              _/      _/  _/ _/_/_/    _/    _/   _/  _/     ",
    "             _/      _/  _/       _/  _/     _/    _/  _/    ",
    "              _/_/_/\_\ _/_/_/_/_/     _/_/_/     _/   _/    ",
    "                      loading QBox...                        ",
    "                 Copyleft (C) 2025 Nafiu Shaibu.             ",
    "                                                             ",
]


def draw_characters(stdscr, x_cord, y_cord):
    # This function draws the characters from the QDATA list
    for c in range(7):
        for x in range(len(QDATA[0])):
            for y in range(8):
                stdscr.addstr(
                    y_cord + y, x_cord + x, QDATA[y][x], curses.color_pair(c + 1)
                )
                stdscr.refresh()
                time.sleep(0.01)


def display_ascii_tree(stdscr):
    """
    Function to display the ASCII tree and animate it on the terminal using curses.
    """
    # Set up the terminal window
    curses.curs_set(0)  # Hide cursor
    curses.start_color()  # Enable color
    curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)
    curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)
    curses.init_pair(3, curses.COLOR_BLUE, curses.COLOR_BLACK)
    curses.init_pair(4, curses.COLOR_YELLOW, curses.COLOR_BLACK)
    curses.init_pair(5, curses.COLOR_MAGENTA, curses.COLOR_BLACK)
    curses.init_pair(6, curses.COLOR_CYAN, curses.COLOR_BLACK)
    curses.init_pair(7, curses.COLOR_WHITE, curses.COLOR_BLACK)

    # Get terminal dimensions
    max_y, max_x = stdscr.getmaxyx()

    # Calculate coordinates to center the ASCII art
    x_cord_art = len(QDATA[0])
    x_cord = (max_x - x_cord_art) // 2
    y_cord = (max_y - 8) // 2  # 8 rows of the ASCII art

    # Loop to animate the art
    while True:
        for c in range(7):
            stdscr.clear()  # Clear the screen
            stdscr.attron(curses.color_pair(c + 1))  # Set color
            draw_characters(stdscr, x_cord, y_cord)  # Draw ASCII art
            stdscr.attroff(curses.color_pair(c + 1))  # Reset color
            time.sleep(0.5)  # Pause before moving to next color

        stdscr.refresh()


# Run the function using curses.wrapper
if __name__ == "__main__":
    curses.wrapper(display_ascii_tree)
