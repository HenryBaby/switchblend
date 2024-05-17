import os
import shutil
import glob
import json


def load_json(filename):
    with open(filename, "r") as file:
        return json.load(file)


def delete_files(file_list_filename):
    data = load_json(file_list_filename)

    if "tasks" not in data:
        print(f"Error: No [tasks] section found in {file_list_filename}.")
        return

    for key, command_line in data["tasks"].items():
        try:
            command, path = command_line.split(maxsplit=1)
            execute_command(command.strip(), path.strip())
        except ValueError as e:
            print(f"Error processing task {key}: {str(e)}")
        except Exception as e:
            print(f"Unexpected error processing task {key}: {str(e)}")


def execute_command(command, path):
    base_path = "downloads/output/"
    if " " in path:
        source, destination = map(str.strip, path.split(" ", 1))
        source_path = os.path.join(base_path, source)
        destination_path = os.path.join(base_path, destination)
    else:
        source_path = os.path.join(base_path, path)
        destination_path = ""

    source_paths = glob.glob(source_path)
    if not source_paths:
        print(f"Error: Source path does not exist or no files match: '{source_path}'")
        return

    for src in source_paths:
        if destination_path:
            dest = destination_path
            if os.path.isdir(src) and not dest.endswith("/"):
                dest = os.path.join(dest, os.path.basename(src))
            elif not os.path.isdir(src) and os.path.isdir(dest):
                dest = os.path.join(dest, os.path.basename(src))
        else:
            dest = destination_path

        try:
            if command == "delete":
                delete_path(src)
            elif command == "rename":
                rename_path(src, dest)
            elif command == "move":
                move_path(src, dest)
            elif command == "copy":
                copy_path(src, dest)
            else:
                print(f"Error: Unknown command '{command}'")
        except OSError as e:
            print(f"Error executing {command} on {path}: {str(e)}")


def delete_path(path):
    for matched_path in glob.glob(path):
        if os.path.isdir(matched_path):
            shutil.rmtree(matched_path)
            print(f"Deleted folder and its contents: {matched_path}")
        elif os.path.isfile(matched_path):
            os.remove(matched_path)
            print(f"Deleted file: {matched_path}")


def rename_path(source, destination):
    if os.path.exists(destination):
        print(f"Error: Destination already exists: '{destination}'")
        return
    if not os.path.exists(os.path.dirname(destination)):
        os.makedirs(os.path.dirname(destination), exist_ok=True)
    os.rename(source, destination)
    print(f"Renamed '{source}' to '{destination}'")


def move_path(source, destination):
    if os.path.exists(destination):
        print(f"Error: Destination already exists: '{destination}'")
        return
    if not os.path.exists(os.path.dirname(destination)):
        os.makedirs(os.path.dirname(destination), exist_ok=True)
    shutil.move(source, destination)
    print(f"Moved '{source}' to '{destination}'")


def copy_path(source, destination):
    if os.path.exists(destination):
        print(f"Error: Destination already exists: '{destination}'")
        return
    if not os.path.exists(os.path.dirname(destination)):
        os.makedirs(os.path.dirname(destination), exist_ok=True)
    shutil.copy(source, destination)
    print(f"Copied '{source}' to '{destination}'")


if __name__ == "__main__":
    file_list_filename = "config/tasks.json"
    delete_files(file_list_filename)
