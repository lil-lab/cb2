"""A monitor script to display exceptions occurring on the server live.

Uses a TUI interface.
"""
import os
import sys
import time

import fire
from blessed import Terminal
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from cb2game.server.config.config import Config, ReadConfigOrDie


class ExceptionViewer:
    def __init__(self, config_filepath=""):
        if config_filepath == "":
            self.config = Config()
        else:
            self.config = ReadConfigOrDie(config_filepath)
        self.exception_dir = self.config.exception_directory()
        self.term = Terminal()
        self.data = []
        self.current_selection = 0
        self.filter_string = ""

    def get_exception_files(self):
        # Scan directory and return list of exception files
        return [
            f
            for f in os.listdir(self.exception_dir)
            if os.path.isfile(os.path.join(self.exception_dir, f))
        ]

    def parse_filename(self, filename):
        # Split filename to get game_id, exception_type and date
        parts = filename.split("_")
        game_id = parts[0]
        exception_type = parts[2]
        # Get the creation date from the file metadata.
        date = time.ctime(os.path.getctime(os.path.join(self.exception_dir, filename)))
        return game_id, exception_type, date

    def update_data(self):
        # Update the data with parsed filenames
        self.data = []
        for file in self.get_exception_files():
            # Ignore hidden files.
            if file.startswith("."):
                continue
            game_id, exception_type, date = self.parse_filename(file)
            self.data.append(
                {
                    "game_id": game_id,
                    "exception_type": exception_type,
                    "date": date,
                    "filename": file,
                }
            )

    def sort_data(self, column):
        # Make sure column is valid
        if column not in self.data[0].keys():
            print("Invalid column")
            return
        # Handle sorting by date
        if column == "date":
            self.data = sorted(
                self.data,
                key=lambda k: time.mktime(
                    time.strptime(k[column], "%a %b %d %H:%M:%S %Y")
                ),
            )
            return
        # Sort data by column
        self.data = sorted(self.data, key=lambda k: k[column])

    def reverse_data(self):
        if self.data:
            self.data.reverse()

    def filter_data(self, string):
        # Filter data by string
        self.data = [
            row
            for row in self.data
            if any(string in str(value) for value in row.values())
        ]

    def print_data(self):
        # Print data in a grid using blessed. Print maximum 10 rows. If there are more rows, print row_selected - 5 to row_selected + 5.
        # Clear the screen.
        print(self.term.clear)
        with self.term.location(0, 0):
            # Print location of exceptions.
            print(
                self.term.bold
                + self.term.center("Exceptions: " + str(self.exception_dir))
                + self.term.normal
            )
            # Print column names.
            print(
                self.term.hide_cursor()
                + "{:<10} {:<30} {:<20}".format("Game ID", "Exception Type", "Date")
            )
            # Truncate the data to a maximum of 10 rows, centered around the current selection. If there are less than 10 on either side, print more on the other side.
            truncated_data = self.data[
                max(0, self.current_selection - 5) : min(
                    len(self.data), self.current_selection + 5
                )
            ]
            if self.current_selection > 5:
                print("...")
            for i, row in enumerate(truncated_data):
                extended_i = i + max(0, self.current_selection - 5)
                # Print each row. If the row is selected, reverse the colors and add a ">" to the left of the line.
                if extended_i == self.current_selection:
                    print(
                        "> "
                        + self.term.reverse
                        + " {:<10} {:<30} {:<20}".format(
                            row["game_id"], row["exception_type"], row["date"]
                        )
                        + self.term.normal
                    )
                else:
                    print(
                        "{:<10} {:<30} {:<20}".format(
                            row["game_id"], row["exception_type"], row["date"]
                        )
                    )
            if len(self.data) > self.current_selection + 5:
                print("...")
            print(
                self.term.normal
                + "\nPress q to quit, s to sort, f to filter, r to reverse sort, enter to view exception"
            )

    def print_exception(self, filename):
        # Print the full exception to the right of the data grid in a fixed-size box.
        with open(os.path.join(self.exception_dir, filename), "r") as file:
            exception = file.read()
        # For each line in exception, if it's longer than the width of the box, split it into multiple lines.
        # This is to prevent the exception from overflowing the box.
        exception_lines = []
        max_line_length = int(self.term.width)
        for line in exception.split("\n"):
            if len(line) > max_line_length:
                for segment in [
                    line[i : i + max_line_length]
                    for i in range(0, len(line), max_line_length)
                ]:
                    exception_lines.append(segment)
            else:
                exception_lines.append(line)
        # Remove all lines after "_run_module_as_main"
        for i, line in enumerate(exception_lines):
            if "Locals by frame, innermost last" in line:
                exception_lines = exception_lines[:i]
                break
        # Print the exception box. If the exception is longer than the height of the box, truncate it.
        with self.term.location(0, len(self.data) + 2):
            print(self.term.clear_eos)
            print("\n".join(exception_lines))

    def run(self):
        # Run the application
        self.update_data()
        self.filter_data(self.filter_string)
        self.print_data()


class FileChangeHandler(FileSystemEventHandler):
    def __init__(self, viewer):
        self.viewer = viewer

    def on_any_event(self, event):
        # Update the view whenever a file is added to the directory
        self.viewer.run()


def main(config_filepath=""):
    viewer = ExceptionViewer(config_filepath)
    observer = Observer()
    observer.schedule(
        FileChangeHandler(viewer), path=viewer.exception_dir, recursive=False
    )
    observer.start()
    try:
        viewer.run()
        with viewer.term.cbreak():
            while True:
                key = viewer.term.inkey(timeout=10)
                if key == "q":
                    sys.stdout.write(viewer.term.clear)
                    observer.stop()
                    break
                elif key == "s":
                    with viewer.term.location(0, viewer.term.height - 5):
                        print("Select column to sort by:")
                        print("1: game_id")
                        print("2: exception_type")
                        print("3: date")
                    column_key = viewer.term.inkey(timeout=10)
                    if column_key == "1":
                        column = "game_id"
                    elif column_key == "2":
                        column = "exception_type"
                    elif column_key == "3":
                        column = "date"
                    else:
                        with viewer.term.location(0, viewer.term.height - 2):
                            print(viewer.term.clear)
                            print("Invalid selection")
                            # Reset column_key to default.
                            column_key = ""
                            column = ""
                        continue
                    if column_key:
                        viewer.sort_data(column)
                    viewer.print_data()
                elif key == "r":
                    viewer.reverse_data()
                    viewer.print_data()
                elif key == "f":
                    string = ""
                    while True:
                        with viewer.term.location(0, viewer.term.height - 2):
                            print(viewer.term.clear_eol)
                            print(
                                f"Filter string: {string}"
                            )  # added line to print filter string
                        key = viewer.term.inkey()
                        if key.is_sequence:
                            if key.name == "KEY_ENTER":
                                break
                            elif key.name == "KEY_BACKSPACE":
                                string = string[:-1]
                            else:
                                continue
                        else:
                            string += key
                        viewer.filter_string = string
                        viewer.run()
                    viewer.filter_string = string
                    viewer.run()
                elif key.name == "KEY_UP":
                    viewer.current_selection = max(0, viewer.current_selection - 1)
                    # Log
                    string_to_print = f"selected item: {viewer.current_selection}"
                    with viewer.term.location(
                        viewer.term.width - len(string_to_print), viewer.term.height - 1
                    ):
                        sys.stdout.write(string_to_print)
                    viewer.print_data()
                elif key.name == "KEY_DOWN":
                    viewer.current_selection = min(
                        len(viewer.data) - 1, viewer.current_selection + 1
                    )
                    # Log
                    string_to_print = f"selected item: {viewer.current_selection}"
                    with viewer.term.location(
                        viewer.term.width - len(string_to_print), viewer.term.height - 1
                    ):
                        sys.stdout.write(string_to_print)
                    viewer.print_data()
                elif key.name == "KEY_ENTER":
                    viewer.print_exception(
                        viewer.data[viewer.current_selection]["filename"]
                    )
                else:
                    # Print the key out in the bottom right corner
                    string_to_print = f"Unknown key: {key.code}"
                    with viewer.term.location(
                        viewer.term.width - len(string_to_print), viewer.term.height - 1
                    ):
                        sys.stdout.write(string_to_print)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


if __name__ == "__main__":
    fire.Fire(main)
