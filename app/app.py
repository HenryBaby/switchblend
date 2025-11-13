import json
import logging
import os
import shutil
from datetime import datetime
from threading import Thread

import requests
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, render_template, request, url_for
from flask_cors import CORS

import cleanup_manager
import download_manager
import package_manager
import upload_manager

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

CORS(app)
scheduler = BackgroundScheduler()


UPDATE_INTERVAL = int(os.getenv("UPDATE_INTERVAL", 60))


def load_json(filename):
    with open(filename, "r") as file:
        return json.load(file)


def save_json(data, filename):
    with open(filename, "w") as file:
        json.dump(data, file, indent=4)


def load_devices():
    return load_json("config/devices.json").get("devices", [])


def save_devices(devices):
    save_json({"devices": devices}, "config/devices.json")


def get_devices():
    return load_devices()


def run_background_task(func, *args):
    thread = Thread(target=func, args=args)
    thread.start()


def get_urls():
    data = load_json("config/sources.json")
    return [
        {
            "name": key,
            "url": project["url"],
            "last_updated": project.get("last_updated", "Not available"),
            "updated": project.get("updated", False),
        }
        for key, project in data["GitHub"].items()
    ], data.get("last_checked", "Never")


def get_directory_contents(path):
    if not os.path.isdir(path):
        return []
    contents = []
    for entry in os.scandir(path):
        if entry.is_dir():
            contents.append(
                {
                    "type": "folder",
                    "name": f"{entry.name}/",
                    "path": entry.path,
                    "children": get_directory_contents(entry.path),
                }
            )
        else:
            contents.append({"type": "file", "name": entry.name, "path": entry.path})
    return contents


def get_tasks():
    data = load_json("config/tasks.json")
    tasks = []
    for key, task_string in sorted(data["tasks"].items(), key=lambda x: int(x[0])):
        command, path = task_string.split(maxsplit=1)
        source, destination = path.split(" ", 1) if " " in path else (path, "")
        tasks.append({"command": command, "source": source, "destination": destination})
    return tasks


def update_urls():
    try:
        data = load_json("config/sources.json")
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

            data["GitHub"][new_name] = new_entry
            save_json(data, "config/sources.json")
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
        data = load_json("config/tasks.json")
        command = request.form.get("new_command")
        source = request.form.get("new_source")
        destination = request.form.get("new_destination", "")
        if command == "delete":
            if command and source:
                next_index = len(data["tasks"]) + 1
                data["tasks"][str(next_index)] = f"{command} {source}"
        else:
            if command and source and destination:
                next_index = len(data["tasks"]) + 1
                data["tasks"][str(next_index)] = f"{command} {source} {destination}"
        save_json(data, "config/tasks.json")
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
    input_dir = "downloads/input/"
    if not os.path.isdir(input_dir):
        os.makedirs(input_dir, exist_ok=True)
        return
    for item in os.listdir(input_dir):
        item_path = os.path.join(input_dir, item)
        if os.path.isfile(item_path):
            os.remove(item_path)
            print(f"Deleted file: {item_path}")
        elif os.path.isdir(item_path):
            shutil.rmtree(item_path)
            print(f"Deleted directory and its contents: {item_path}")


@app.route("/")
def index():
    projects, last_checked = get_urls()
    devices = get_devices()
    next_run_time = None

    job = scheduler.get_jobs()[0] if scheduler.get_jobs() else None
    if job:
        next_run_time = job.next_run_time

    return render_template(
        "index.html",
        projects=projects,
        last_checked=last_checked,
        next_run_time=next_run_time,
        current_page="home",
        devices=devices,
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
    data = load_json("config/sources.json")

    if project_name in data["GitHub"]:
        del data["GitHub"][project_name]

    save_json(data, "config/sources.json")
    return redirect(url_for("manage_urls"))


@app.route("/delete-task", methods=["POST"])
def delete_task():
    task_index = int(request.form.get("delete_task_index")) - 1
    data = load_json("config/tasks.json")

    new_data = {
        key: task
        for i, (key, task) in enumerate(data["tasks"].items())
        if i != task_index
    }

    new_data = {str(i + 1): task for i, task in enumerate(new_data.values())}

    data["tasks"] = new_data
    save_json(data, "config/tasks.json")
    return redirect(url_for("manage_tasks"))


@app.route("/run-downloads")
def run_downloads():
    run_background_task(download_manager.main, True)
    referer = request.headers.get("Referer")
    return redirect(referer if referer else url_for("index"))


@app.route("/download-source", methods=["POST"])
def download_source():
    project_name = request.form.get("project_name")
    data = load_json("config/sources.json")
    project = data["GitHub"].get(project_name)

    if project:
        url = project["url"]
        try:
            if url.endswith(".zip") or url.endswith(".7z"):
                success = download_manager.handle_download_tasks(url)
                release_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            else:
                success, release_timestamp = download_manager.download_from_github_api(
                    project_name, project
                )
            if success:
                download_manager.mark_download_complete(project, release_timestamp)
                save_json(data, "config/sources.json")
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
    base_path = "downloads/output"
    try:
        contents = get_directory_contents(base_path)
        return jsonify({"status": "success", "contents": contents})
    except Exception as e:
        logger.error(f"Error fetching directory contents: {e}")
        return jsonify(
            {"status": "error", "message": "Failed to fetch directory contents"}
        )


@app.route("/run-cleanup")
def run_cleanup():
    print("Running cleanup tasks")
    run_background_task(cleanup_manager.delete_files, "config/tasks.json")
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
    files = request.form.getlist("files[]")

    logger.info(f"Selected files: {files}")
    if not files:
        return jsonify({"status": "error", "message": "No files selected for upload."})

    devices = load_json("config/devices.json").get("devices", [])
    device = next((d for d in devices if d["name"] == device_name), None)
    if device:
        success, message = upload_manager.upload_to_device(
            device["ip"],
            device["port"],
            device["username"],
            device["password"],
            "downloads/output",
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
