import os
import json
import requests
import shutil
import download_manager
import cleanup
import package_manager
import logging
from flask import Flask, render_template, request, redirect, url_for
from threading import Thread
from apscheduler.schedulers.background import BackgroundScheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
scheduler = BackgroundScheduler()


def load_json(filename):
    with open(filename, "r") as file:
        return json.load(file)


def save_json(data, filename):
    with open(filename, "w") as file:
        json.dump(data, file, indent=4)


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


def get_tasks():
    data = load_json("config/tasks.json")
    tasks = []
    for key, task_string in sorted(data["tasks"].items(), key=lambda x: int(x[0])):
        command, path = task_string.split(maxsplit=1)
        source, destination = path.split(" ", 1) if " " in path else (path, "")
        tasks.append({"command": command, "source": source, "destination": destination})
    return tasks


def update_urls():
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
            except requests.RequestException:
                pass

        data["GitHub"][new_name] = new_entry
        save_json(data, "config/sources.json")


def update_tasks():
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


def clear_input_directory():
    input_dir = "downloads/input/"
    for item in os.listdir(input_dir):
        item_path = os.path.join(input_dir, item)
        if os.path.isfile(item_path):
            os.remove(item_path)
            print(f"Deleted file: {item_path}")
        elif os.path.isdir(item_path):
            shutil.rmtree(item_path)
            print(f"Deleted directory and its contents: {item_path}")


def reset_updated_fields():
    data = load_json("config/sources.json")
    for project in data["GitHub"].values():
        project["updated"] = False
    save_json(data, "config/sources.json")


@app.route("/")
def index():
    projects, last_checked = get_urls()
    return render_template(
        "index.html", projects=projects, last_checked=last_checked, current_page="home"
    )


@app.route("/sources", methods=["GET", "POST"])
def manage_urls():
    if request.method == "POST":
        update_urls()
    projects, last_checked = get_urls()
    return render_template(
        "sources.html",
        projects=projects,
        last_checked=last_checked,
        current_page="sources",
    )


@app.route("/tasks", methods=["GET", "POST"])
def manage_tasks():
    if request.method == "POST":
        update_tasks()
    tasks = get_tasks()
    return render_template(
        "tasks.html", tasks=tasks, title="Tasks", current_page="tasks"
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
    def download_and_reset():
        download_manager.main(True)
        reset_updated_fields()

    run_background_task(download_and_reset)
    referer = request.headers.get("Referer")
    return redirect(referer if referer else url_for("index"))


@app.route("/run-cleanup")
def run_cleanup():
    run_background_task(cleanup.delete_files, "config/tasks.json")
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


def scheduled_job():
    download_manager.check_and_update_sources()


if __name__ == "__main__":
    scheduler.add_job(scheduled_job, "interval", hours=1)
    scheduler.start()
    logger.info("Scheduler started")

    app.run(debug=True, host="0.0.0.0", use_reloader=False)
