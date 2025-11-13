import os
import requests
import shutil
import zipfile
import json
import logging
import py7zr
from datetime import datetime
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

dl_exceptions = ["DBI", "Ultrahand Overlay"]

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
USE_GITHUB_TOKEN = bool(GITHUB_TOKEN)

if not USE_GITHUB_TOKEN:
    logger.warning(
        "GITHUB_TOKEN environment variable not set. Proceeding without authentication."
    )


def load_json(filename):
    with open(filename, "r") as file:
        return json.load(file)


def save_json(data, filename):
    with open(filename, "w") as file:
        json.dump(data, file, indent=4)


def clear_output_directory():
    output_dir = "downloads/output"
    if not os.path.isdir(output_dir):
        os.makedirs(output_dir, exist_ok=True)
        return
    for item in os.listdir(output_dir):
        item_path = os.path.join(output_dir, item)
        try:
            if os.path.isfile(item_path) or os.path.islink(item_path):
                os.remove(item_path)
            elif os.path.isdir(item_path):
                shutil.rmtree(item_path)
            logger.info(f"Cleared {item_path}")
        except Exception as e:
            logger.error(f"Failed to delete {item_path}. Reason: {e}")


def handle_download_tasks(download_url):
    filename = os.path.basename(download_url)
    download_folder = "downloads/input"
    if not os.path.exists(download_folder):
        os.makedirs(download_folder)
    destination = os.path.join(download_folder, filename)
    if download_file(download_url, destination):
        extract_folder = "downloads/output"
        if not os.path.exists(extract_folder):
            os.makedirs(extract_folder)
        try:
            if download_url.endswith(".zip"):
                extract_zip(destination, extract_folder)
            elif download_url.endswith(".7z"):
                extract_7z(destination, extract_folder)
            else:
                output_folder = "downloads/output"
                if not os.path.exists(output_folder):
                    os.makedirs(output_folder)
                output_destination = os.path.join(output_folder, filename)
                shutil.copyfile(destination, output_destination)
            logger.info(f"File handled successfully: {filename}")
        except Exception as e:
            logger.error(f"Failed to extract or copy file {filename}: {e}")


def download_file(download_url, destination):
    try:
        headers = {"Authorization": f"token {GITHUB_TOKEN}"} if USE_GITHUB_TOKEN else {}
        response = requests.get(download_url, headers=headers, stream=True)
        response.raise_for_status()
        with open(destination, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        logger.info(f"File downloaded successfully: {destination}")
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to download file: {e}")
        return False


def extract_zip(zip_file, destination_folder):
    try:
        with zipfile.ZipFile(zip_file, "r") as zip_ref:
            zip_ref.extractall(destination_folder)
        logger.info(f"Zip file extracted successfully: {zip_file}")
    except Exception as e:
        logger.error(f"Failed to extract zip file {zip_file}: {e}")


def extract_7z(archive_file, destination_folder):
    try:
        logger.info(f"Starting extraction of 7z file: {archive_file}")
        with py7zr.SevenZipFile(archive_file, mode="r") as z:
            z.extractall(path=destination_folder)
        logger.info(f"7z file extracted successfully: {archive_file}")
    except Exception as e:
        logger.error(f"Failed to extract 7z file {archive_file}: {e}")


def download_from_github_api(project_name, project_details):
    url = project_details["url"]
    try:
        headers = {"Authorization": f"token {GITHUB_TOKEN}"} if USE_GITHUB_TOKEN else {}
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        if not response.content:
            logger.error(f"Empty response for project {project_name}. URL: {url}")
            return

        try:
            releases = response.json()
        except json.JSONDecodeError as e:
            logger.error(
                f"Failed to parse JSON for {project_name}. URL: {url}, Error: {e}"
            )
            return

        if isinstance(releases, list) and releases:
            latest_release = releases[0]
            asset_index = 1 if project_name in dl_exceptions else 0

            if len(latest_release["assets"]) > asset_index:
                download_url = latest_release["assets"][asset_index][
                    "browser_download_url"
                ]
                handle_download_tasks(download_url)
    except requests.RequestException as e:
        logger.error(f"Failed to process URL {url}: {e}")


def check_for_updates():
    data = load_json("config/sources.json")
    updates_available = False

    for project_name, project_details in data["GitHub"].items():
        url = project_details["url"]
        last_updated = project_details.get("last_updated")

        if url.endswith(".zip") or url.endswith(".7z"):
            logger.info(f"Skipping direct file URL for {project_name}: {url}")
            continue

        try:
            headers = (
                {"Authorization": f"token {GITHUB_TOKEN}"} if USE_GITHUB_TOKEN else {}
            )
            response = requests.get(url, headers=headers)
            response.raise_for_status()

            if not response.content:
                logger.error(f"Empty response for project {project_name}. URL: {url}")
                continue

            try:
                releases = response.json()
            except json.JSONDecodeError as e:
                logger.error(
                    f"Failed to parse JSON for {project_name}. URL: {url}, Error: {e}"
                )
                continue

            if isinstance(releases, list) and releases:
                latest_release = releases[0]
                asset_index = 1 if project_name in dl_exceptions else 0

                if len(latest_release["assets"]) > asset_index:
                    updated_at = latest_release["assets"][asset_index].get("updated_at")
                    if updated_at:
                        updated_at = updated_at.replace("T", " ").replace("Z", "")
                        if not last_updated or updated_at > last_updated:
                            project_details["last_updated"] = updated_at
                            project_details["updated"] = True
                            updates_available = True
                        else:
                            project_details["updated"] = False

        except requests.RequestException as e:
            logger.error(f"Failed to check updates for {project_name}: {e}")

    return updates_available, data


def perform_download_tasks(data):
    clear_output_directory()

    for project_name, project_details in data["GitHub"].items():
        url = project_details["url"]

        try:
            if url.endswith(".zip") or url.endswith(".7z"):
                handle_download_tasks(url)
            else:
                download_from_github_api(project_name, project_details)
        except Exception as e:
            logger.error(f"Failed to process URL {url}: {e}")


def main(force_download=False):
    logger.info("Starting download tasks...")
    data = load_json("config/sources.json")

    if force_download:
        logger.info("Force download. Performing download tasks...")
        perform_download_tasks(data)
    else:
        updates_available, data = check_for_updates()
        if updates_available:
            logger.info("Updates found. Performing download tasks...")
            perform_download_tasks(data)
        else:
            logger.info("No updates found.")

    save_json(data, "config/sources.json")


def check_and_update_sources():
    updates_available, data = check_for_updates()
    data["last_checked"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if updates_available:
        logger.info("Updates found. Updating sources.json...")
        for project_name, project_details in data["GitHub"].items():
            if project_details.get("updated"):
                project_details["highlight"] = True
            else:
                project_details.pop("highlight", None)
        save_json(data, "config/sources.json")
    else:
        logger.info("No updates found.")
        for project_details in data["GitHub"].values():
            project_details.pop("highlight", None)

    save_json(data, "config/sources.json")


if __name__ == "__main__":
    main(force_download=True)
