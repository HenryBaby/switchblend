import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from threading import Thread

import requests
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
from flask import (
    Flask,
    abort,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from flask_cors import CORS

import cleanup_manager
import download_manager
import package_manager
import upload_manager

from storage import (
    CONFIG_DIR,
    DOWNLOADS_DIR,
    INPUT_DIR,
    OUTPUT_DIR,
    config_lock,
    load_json,
    save_json,
    update_json,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

CORS(app)
scheduler = BackgroundScheduler()

SOURCES_PATH = CONFIG_DIR / "sources.json"
TASKS_PATH = CONFIG_DIR / "tasks.json"
DEVICES_PATH = CONFIG_DIR / "devices.json"

load_dotenv()
UPDATE_INTERVAL = int(os.getenv("UPDATE_INTERVAL", 60))


def load_devices():
    if not DEVICES_PATH.exists():
        return []
    with config_lock:
        return load_json(DEVICES_PATH).get("devices", [])


def save_devices(devices):
    with config_lock:
        save_json({"devices": devices}, DEVICES_PATH)


def get_devices():
    return load_devices()


def run_background_task(func, *args):
    thread = Thread(target=func, args=args)
    thread.start()


def get_latest_aio_zip():
    if not DOWNLOADS_DIR.exists():
        return None
    zip_files = sorted(
        DOWNLOADS_DIR.glob("AIO-*.zip"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return zip_files[0] if zip_files else None


def get_urls():
    with config_lock:
        data = load_json(SOURCES_PATH)
    return [
        {
            "name": key,
            "url": project["url"],
            "last_updated": project.get("last_updated", "Not available"),
            "updated": project.get("updated", False),
        }
        for key, project in data["GitHub"].items()
    ], data.get("last_checked", "Never")


def get_directory_contents(path: Path, base_path: Path | None = None):
    path = Path(path)
    if not path.is_dir():
        return []
    base_path = base_path or path
    contents = []
    for entry in sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
        relative_path = entry.relative_to(base_path)
        if entry.is_dir():
            contents.append(
                {
                    "type": "folder",
                    "name": f"{entry.name}/",
                    "path": relative_path.as_posix(),
                    "children": get_directory_contents(entry, base_path),
                }
            )
        else:
            contents.append(
                {"type": "file", "name": entry.name, "path": relative_path.as_posix()}
            )
    return contents


def get_tasks():
    with config_lock:
        data = load_json(TASKS_PATH)
    tasks = []
    for key, task_string in sorted(data["tasks"].items(), key=lambda x: int(x[0])):
        command, path = task_string.split(maxsplit=1)
        source, destination = path.split(" ", 1) if " " in path else (path, "")
        tasks.append({"command": command, "source": source, "destination": destination})
    return tasks


def update_urls():
    try:
        new_name = request.form.get("new_name")
        new_url = request.form.get("new_url")

        if new_url and new_name:
            new_entry = {"url": new_url, "name": new_name, "updated": True}

            if "api.github.com" in new_url:
                try:
                    response = requests.get(new_url)
                    response.raise_for_status()
                    releases = response.json()

                    if isinstance(releases, list) and releases:
                        latest_release = releases[0]
                        asset_index = 1 if new_name == "DBI" else 0

                        if len(latest_release["assets"]) > asset_index:
                            last_updated = latest_release["assets"][asset_index].get(
                                "updated_at"
                            )
                            if last_updated:
                                last_updated = last_updated.replace("T", " ").replace(
                                    "Z", ""
                                )
                                new_entry["last_updated"] = last_updated
                except requests.RequestException as e:
                    logger.error(f"Error fetching release info: {e}")
                    return jsonify(
                        {
                            "status": "error",
                            "message": "Failed to fetch release information from GitHub.",
                        }
                    )

            def mutator(data):
                data["GitHub"][new_name] = new_entry

            update_json(SOURCES_PATH, mutator)
            return jsonify(
                {"status": "success", "message": "URL updated successfully."}
            )
        else:
            return jsonify({"status": "error", "message": "Name and URL are required."})
    except Exception as e:
        logger.error(f"Error updating URLs: {e}")
        return jsonify(
            {
                "status": "error",
                "message": "An unexpected error occurred while updating URLs.",
            }
        )


def update_tasks():
    try:
        command = request.form.get("new_command")
        source = request.form.get("new_source")
        destination = request.form.get("new_destination", "")
        if command == "delete":
            if not (command and source):
                return jsonify(
                    {"status": "error", "message": "Command and source are required."}
                )

            def mutator(data):
                next_index = len(data.get("tasks", {})) + 1
                data.setdefault("tasks", {})[str(next_index)] = f"{command} {source}"

            update_json(TASKS_PATH, mutator)
        else:
            if command and source and destination:
                def mutator(data):
                    next_index = len(data.get("tasks", {})) + 1
                    data.setdefault("tasks", {})[
                        str(next_index)
                    ] = f"{command} {source} {destination}"

                update_json(TASKS_PATH, mutator)
            else:
                return jsonify(
                    {
                        "status": "error",
                        "message": "Command, source, and destination are required.",
                    }
                )
        return jsonify({"status": "success", "message": "Task updated successfully."})
    except Exception as e:
        logger.error(f"Error updating tasks: {e}")
        return jsonify(
            {
                "status": "error",
                "message": "An unexpected error occurred while updating tasks.",
            }
        )


def clear_input_directory():
    input_dir = INPUT_DIR
    input_dir.mkdir(parents=True, exist_ok=True)
    for item in input_dir.iterdir():
        if item.is_file() or item.is_symlink():
            item.unlink()
            logger.info(f"Deleted file: {item}")
        elif item.is_dir():
            shutil.rmtree(item)
            logger.info(f"Deleted directory and its contents: {item}")


def validate_requested_files(files):
    base_path = OUTPUT_DIR.resolve()
    sanitized = []

    for requested_path in files:
        if not requested_path:
            continue
        relative = requested_path.strip().lstrip("/\\")
        candidate = (OUTPUT_DIR / relative).resolve()
        if not candidate.exists():
            raise ValueError(f"Selected path does not exist: {relative}")
        if not candidate.is_relative_to(base_path):
            raise ValueError("Invalid path selected.")
        sanitized.append(candidate.relative_to(base_path).as_posix())

    if not sanitized:
        raise ValueError("Select at least one valid file or folder before uploading.")

    return sanitized


@app.route("/")
def index():
    projects, last_checked = get_urls()
    devices = get_devices()
    next_run_time = None
    latest_aio_zip = get_latest_aio_zip()

    job = scheduler.get_jobs()[0] if scheduler.get_jobs() else None
    if job:
        next_run_time = job.next_run_time

    return render_template(
        "index.html",
        projects=projects,
        last_checked=last_checked,
        next_run_time=next_run_time,
        latest_aio_zip=latest_aio_zip,
        current_page="home",
        devices=devices,
    )


@app.route("/latest-package")
def latest_package():
    latest_zip = get_latest_aio_zip()
    if not latest_zip:
        abort(404, description="No packaged archive found.")
    return send_from_directory(
        latest_zip.parent, latest_zip.name, as_attachment=True, max_age=0
    )


@app.route("/sources", methods=["GET", "POST"])
def manage_urls():
    if request.method == "POST":
        update_urls()
    projects, last_checked = get_urls()
    devices = get_devices()
    return render_template(
        "sources.html",
        projects=projects,
        last_checked=last_checked,
        current_page="sources",
        devices=devices,
    )


@app.route("/tasks", methods=["GET", "POST"])
def manage_tasks():
    if request.method == "POST":
        update_tasks()
    tasks = get_tasks()
    devices = get_devices()
    return render_template(
        "tasks.html", tasks=tasks, title="Tasks", current_page="tasks", devices=devices
    )


@app.route("/delete-url", methods=["POST"])
def delete_url():
    project_name = request.form.get("delete_project_name")

    def mutator(data):
        if project_name in data["GitHub"]:
            del data["GitHub"][project_name]

    update_json(SOURCES_PATH, mutator)
    return redirect(url_for("manage_urls"))


@app.route("/delete-task", methods=["POST"])
def delete_task():
    task_index = int(request.form.get("delete_task_index")) - 1

    def mutator(data):
        tasks = data.get("tasks", {})
        new_data = {
            key: task for i, (key, task) in enumerate(tasks.items()) if i != task_index
        }
        reordered = {str(i + 1): task for i, task in enumerate(new_data.values())}
        data["tasks"] = reordered

    update_json(TASKS_PATH, mutator)
    return redirect(url_for("manage_tasks"))


@app.route("/run-downloads")
def run_downloads():
    run_background_task(download_manager.main, True)
    referer = request.headers.get("Referer")
    return redirect(referer if referer else url_for("index"))


@app.route("/download-source", methods=["POST"])
def download_source():
    project_name = request.form.get("project_name")
    with config_lock:
        data = load_json(SOURCES_PATH)
        project = data["GitHub"].get(project_name)

    if project:
        url = project["url"]

        def persist_success(release_timestamp):
            def mutator(fresh_data):
                project_details = fresh_data["GitHub"].get(project_name)
                if project_details:
                    download_manager.mark_download_complete(
                        project_details, release_timestamp
                    )

            update_json(SOURCES_PATH, mutator)

        try:
            if url.endswith(".zip") or url.endswith(".7z"):
                success = download_manager.handle_download_tasks(url)
                release_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            else:
                success, release_timestamp = download_manager.download_from_github_api(
                    project_name, project
                )
            if success:
                persist_success(release_timestamp)
                return jsonify(
                    {
                        "status": "success",
                        "message": f"Downloaded {project_name} successfully.",
                    }
                )
            else:
                return jsonify(
                    {
                        "status": "error",
                        "message": f"Failed to download {project_name}.",
                    }
                )
        except Exception as e:
            logger.error(f"Error downloading source {project_name}: {e}")
            return jsonify(
                {"status": "error", "message": f"Failed to download {project_name}."}
            )
    else:
        return jsonify({"status": "error", "message": "Project not found"})


@app.route("/fetch-directory-contents")
def fetch_directory_contents():
    try:
        contents = get_directory_contents(OUTPUT_DIR)
        return jsonify({"status": "success", "contents": contents})
    except Exception as e:
        logger.error(f"Error fetching directory contents: {e}")
        return jsonify(
            {"status": "error", "message": "Failed to fetch directory contents"}
        )


@app.route("/run-cleanup")
def run_cleanup():
    print("Running cleanup tasks")
    run_background_task(cleanup_manager.delete_files)
    should_clear_input = request.args.get("clear") == "true"
    if should_clear_input:
        clear_input_directory()
    referer = request.headers.get("Referer")
    return redirect(referer if referer else url_for("index"))


@app.route("/run-package")
def run_package():
    run_background_task(package_manager.package_contents)
    referer = request.headers.get("Referer")
    return redirect(referer if referer else url_for("index"))


@app.route("/devices", methods=["GET", "POST"])
def manage_devices():
    if request.method == "POST":
        devices = load_devices()
        new_device = {
            "name": request.form.get("device_name"),
            "model": request.form.get("device_model"),
            "hos_version": request.form.get("hos_version"),
            "ams_version": request.form.get("ams_version"),
            "ip": request.form.get("ip"),
            "port": request.form.get("port"),
            "username": request.form.get("username"),
            "password": request.form.get("password"),
        }
        devices.append(new_device)
        save_devices(devices)
        return redirect(url_for("manage_devices"))

    devices = get_devices()
    return render_template("devices.html", devices=devices, current_page="devices")


@app.route("/edit-device", methods=["POST"])
def edit_device():
    original_name = request.form.get("original_device_name")
    devices = load_devices()
    for device in devices:
        if device["name"] == original_name:
            device["name"] = request.form.get("device_name")
            device["model"] = request.form.get("device_model")
            device["hos_version"] = request.form.get("hos_version")
            device["ams_version"] = request.form.get("ams_version")
            device["ip"] = request.form.get("ip")
            device["port"] = request.form.get("port")
            device["username"] = request.form.get("username")
            device["password"] = request.form.get("password")
            break
    save_devices(devices)
    return redirect(url_for("manage_devices"))


@app.route("/delete-device", methods=["POST"])
def delete_device():
    device_name = request.form.get("device_name")
    devices = load_devices()
    devices = [device for device in devices if device["name"] != device_name]
    save_devices(devices)
    return redirect(url_for("manage_devices"))


@app.route("/upload", methods=["POST"])
def upload():
    device_name = request.form.get("device_name")
    raw_files = request.form.getlist("files[]")

    logger.info(f"Selected files: {raw_files}")
    if not raw_files:
        return jsonify({"status": "error", "message": "No files selected for upload."})

    try:
        files = validate_requested_files(raw_files)
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)})

    devices = load_devices()
    device = next((d for d in devices if d["name"] == device_name), None)
    if device:
        success, message = upload_manager.upload_to_device(
            device["ip"],
            device["port"],
            device["username"],
            device["password"],
            str(OUTPUT_DIR),
            files,
        )
        if success:
            return jsonify({"status": "success", "message": message})
        else:
            return jsonify({"status": "error", "message": message})
    else:
        return jsonify({"status": "error", "message": "Device not found"})


def scheduled_job():
    try:
        download_manager.check_and_update_sources()
    except Exception as e:
        logger.error(f"Error running scheduled job: {e}")


if __name__ == "__main__":
    scheduler.add_job(scheduled_job, "interval", minutes=UPDATE_INTERVAL)
    scheduler.start()
    logger.info(f"Scheduler started with interval: {UPDATE_INTERVAL} minutes")

    app.run(debug=True, host="0.0.0.0", use_reloader=False)
