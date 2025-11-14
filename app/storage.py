import json
from pathlib import Path
from threading import Lock

BASE_DIR = Path(__file__).resolve().parent
CONFIG_DIR = BASE_DIR / "config"
DOWNLOADS_DIR = BASE_DIR / "downloads"
INPUT_DIR = DOWNLOADS_DIR / "input"
OUTPUT_DIR = DOWNLOADS_DIR / "output"

config_lock = Lock()


def load_json(path: Path):
    with open(path, "r") as file:
        return json.load(file)


def save_json(data, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as file:
        json.dump(data, file, indent=4)


def update_json(path: Path, mutator):
    with config_lock:
        data = load_json(path)
        mutator(data)
        save_json(data, path)
