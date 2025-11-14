import glob
import logging
import os
import shutil
from pathlib import Path

from storage import CONFIG_DIR, OUTPUT_DIR, config_lock, load_json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TASKS_PATH = CONFIG_DIR / "tasks.json"


def delete_files(file_list_filename=None):
    file_list_path = Path(file_list_filename) if file_list_filename else TASKS_PATH
    with config_lock:
        data = load_json(file_list_path)
    logger.info(f"Loading tasks from: {file_list_path}")

    if "tasks" not in data:
        logger.error(f"No [tasks] section found in {file_list_filename}.")
        return

    for key, command_line in data["tasks"].items():
        try:
            command, path = command_line.split(maxsplit=1)
            execute_command(command.strip(), path.strip())
        except ValueError as e:
            logger.error(f"Error processing task {key}: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error processing task {key}: {str(e)}")


def execute_command(command, path):
    logger.info(f"Executing command: {command}, path: {path}")
    base_path = OUTPUT_DIR
    if " " in path:
        source, destination = map(str.strip, path.split(" ", 1))
        source_path = base_path / source
        destination_path = base_path / destination
    else:
        source_path = base_path / path
        destination_path = ""

    logger.info(
        f"Resolved source path: {source_path}, destination path: {destination_path}"
    )

    source_paths = glob.glob(str(source_path))
    if not source_paths:
        logger.error(f"Source path does not exist or no files match: '{source_path}'")
        return

    for src in source_paths:
        logger.info(f"Processing source: {src}")
        if destination_path:
            dest = destination_path
            if os.path.isdir(src) and dest and not str(dest).endswith("/"):
                dest = Path(dest) / os.path.basename(src)
            elif not os.path.isdir(src) and dest and os.path.isdir(dest):
                dest = Path(dest) / os.path.basename(src)
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
                logger.error(f"Unknown command '{command}'")
        except OSError as e:
            logger.error(f"Error executing {command} on {path}: {str(e)}")


def delete_path(path):
    for matched_path in glob.glob(path):
        if os.path.isdir(matched_path):
            shutil.rmtree(matched_path)
            logger.info(f"Deleted folder and its contents: {matched_path}")
        elif os.path.isfile(matched_path):
            os.remove(matched_path)
            logger.info(f"Deleted file: {matched_path}")


def rename_path(source, destination):
    destination_path = Path(destination)
    source_path = Path(source)
    if destination_path.exists():
        logger.error(f"Destination already exists: '{destination}'")
        return
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    os.rename(source_path, destination_path)
    logger.info(f"Renamed '{source}' to '{destination}'")


def move_path(source, destination):
    destination_path = Path(destination)
    source_path = Path(source)
    if destination_path.exists():
        logger.error(f"Destination already exists: '{destination}'")
        return
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(source_path, destination_path)
    logger.info(f"Moved '{source}' to '{destination}'")


def copy_path(source, destination):
    destination_path = Path(destination)
    source_path = Path(source)
    if destination_path.exists():
        logger.error(f"Destination already exists: '{destination}'")
        return
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    if source_path.is_dir():
        shutil.copytree(source_path, destination_path)
        logger.info(f"Copied directory '{source}' to '{destination}'")
    else:
        shutil.copy(source_path, destination_path)
        logger.info(f"Copied file '{source}' to '{destination}'")


if __name__ == "__main__":
    delete_files()
