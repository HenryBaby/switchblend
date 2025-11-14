import logging
import os
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

import py7zr
import requests
from dotenv import load_dotenv

from storage import (
    CONFIG_DIR,
    INPUT_DIR,
    OUTPUT_DIR,
    config_lock,
    load_json,
    update_json,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

dl_exceptions = ["DBI", "Ultrahand Overlay"]

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
USE_GITHUB_TOKEN = bool(GITHUB_TOKEN)

SOURCES_PATH = CONFIG_DIR / "sources.json"

if not USE_GITHUB_TOKEN:
    logger.warning(
        "GITHUB_TOKEN environment variable not set. Proceeding without authentication."
    )


def mark_download_complete(project_details, release_timestamp=None):
    timestamp = release_timestamp or project_details.get("last_updated")
    if not timestamp:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    project_details["last_updated"] = timestamp
    project_details["downloaded_release"] = timestamp
    project_details["updated"] = False
    project_details.pop("highlight", None)


def handle_download_tasks(download_url, output_dir=OUTPUT_DIR):
    filename = os.path.basename(download_url)
    download_folder = INPUT_DIR
    download_folder.mkdir(parents=True, exist_ok=True)
    destination = download_folder / filename
    if download_file(download_url, destination):
        extract_folder = Path(output_dir)
        extract_folder.mkdir(parents=True, exist_ok=True)
        try:
            if download_url.endswith(".zip"):
                extract_zip(destination, extract_folder)
            elif download_url.endswith(".7z"):
                extract_7z(destination, extract_folder)
            else:
                output_folder = Path(output_dir)
                output_folder.mkdir(parents=True, exist_ok=True)
                output_destination = output_folder / filename
                shutil.copyfile(destination, output_destination)
            logger.info(f"File handled successfully: {filename}")
            return True
        except Exception as e:
            logger.error(f"Failed to extract or copy file {filename}: {e}")
    return False


def download_file(download_url, destination: Path):
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


def extract_zip(zip_file: Path, destination_folder: Path):
    try:
        with zipfile.ZipFile(zip_file, "r") as zip_ref:
            zip_ref.extractall(destination_folder)
        logger.info(f"Zip file extracted successfully: {zip_file}")
    except Exception as e:
        logger.error(f"Failed to extract zip file {zip_file}: {e}")


def extract_7z(archive_file: Path, destination_folder: Path):
    try:
        logger.info(f"Starting extraction of 7z file: {archive_file}")
        with py7zr.SevenZipFile(archive_file, mode="r") as z:
            z.extractall(path=destination_folder)
        logger.info(f"7z file extracted successfully: {archive_file}")
    except Exception as e:
        logger.error(f"Failed to extract 7z file {archive_file}: {e}")


def download_from_github_api(project_name, project_details, output_dir=OUTPUT_DIR):
    url = project_details["url"]
    try:
        headers = {"Authorization": f"token {GITHUB_TOKEN}"} if USE_GITHUB_TOKEN else {}
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        if not response.content:
            logger.error(f"Empty response for project {project_name}. URL: {url}")
            return False, None

        try:
            releases = response.json()
        except ValueError as e:
            logger.error(
                f"Failed to parse JSON for {project_name}. URL: {url}, Error: {e}"
            )
            return False, None

        if isinstance(releases, list) and releases:
            latest_release = releases[0]
            asset_index = 1 if project_name in dl_exceptions else 0

            if len(latest_release["assets"]) > asset_index:
                download_url = latest_release["assets"][asset_index][
                    "browser_download_url"
                ]
                updated_at = latest_release["assets"][asset_index].get("updated_at")
                if updated_at:
                    updated_at = updated_at.replace("T", " ").replace("Z", "")
                return handle_download_tasks(download_url, output_dir), updated_at
    except requests.RequestException as e:
        logger.error(f"Failed to process URL {url}: {e}")
    return False, None


def check_for_updates():
    with config_lock:
        data = load_json(SOURCES_PATH)
    updates_available = False
    project_updates = {}

    for project_name, project_details in data["GitHub"].items():
        url = project_details["url"]
        last_updated = project_details.get("last_updated")
        needs_download = project_details.get("updated", False)

        if url.endswith(".zip") or url.endswith(".7z"):
            logger.info(f"Skipping direct file URL for {project_name}: {url}")
            project_updates[project_name] = {"updated": needs_download}
            updates_available = updates_available or needs_download
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
            except ValueError as e:
                logger.error(
                    f"Failed to parse JSON for {project_name}. URL: {url}, Error: {e}"
                )
                continue

            if isinstance(releases, list) and releases:
                latest_release = releases[0]
                asset_index = 1 if project_name in dl_exceptions else 0

                if len(latest_release["assets"]) > asset_index:
                    updated_at = latest_release["assets"][asset_index].get("updated_at")
                    comparison_target = project_details.get("last_updated")
                    if updated_at:
                        updated_at = updated_at.replace("T", " ").replace("Z", "")
                        if not last_updated or updated_at > last_updated:
                            project_updates.setdefault(project_name, {})[
                                "last_updated"
                            ] = updated_at
                            comparison_target = updated_at
                    needs_download = (
                        project_details.get("downloaded_release") != comparison_target
                    )

        except requests.RequestException as e:
            logger.error(f"Failed to check updates for {project_name}: {e}")

        project_updates.setdefault(project_name, {})["updated"] = needs_download
        updates_available = updates_available or needs_download

    def mutator(fresh_data):
        for project_name, fields in project_updates.items():
            project = fresh_data["GitHub"].get(project_name)
            if not project:
                continue
            if "last_updated" in fields:
                project["last_updated"] = fields["last_updated"]
            project["updated"] = fields.get("updated", project.get("updated", False))

    if project_updates:
        update_json(SOURCES_PATH, mutator)

    return updates_available, project_updates


def perform_download_tasks(projects):
    staging_dir = OUTPUT_DIR.parent / ".output_staging"
    if staging_dir.exists():
        shutil.rmtree(staging_dir)
    staging_dir.mkdir(parents=True, exist_ok=True)

    download_results = {}
    all_successful = True

    for project_name, project_details in projects.items():
        url = project_details["url"]

        success = False
        release_timestamp = None
        try:
            if url.endswith(".zip") or url.endswith(".7z"):
                success = handle_download_tasks(url, staging_dir)
                release_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            else:
                success, release_timestamp = download_from_github_api(
                    project_name, project_details, staging_dir
                )
            if success:
                download_results[project_name] = release_timestamp
            else:
                logger.error(f"Failed to process URL {url}")
                all_successful = False
        except Exception as e:
            logger.error(f"Failed to process URL {url}: {e}")
            all_successful = False

    if all_successful:
        if OUTPUT_DIR.exists():
            shutil.rmtree(OUTPUT_DIR)
        shutil.move(staging_dir, OUTPUT_DIR)
        return True, download_results

    shutil.rmtree(staging_dir, ignore_errors=True)
    logger.error("Download run failed; preserving existing output directory.")
    return False, download_results


def main(force_download=False):
    logger.info("Starting download tasks...")

    if force_download:
        logger.info("Force download. Performing download tasks...")
        with config_lock:
            data = load_json(SOURCES_PATH)
        success, download_results = perform_download_tasks(data.get("GitHub", {}))
        if success:
            apply_download_results(download_results)
    else:
        updates_available, _ = check_for_updates()
        if updates_available:
            logger.info("Updates found. Performing download tasks...")
            with config_lock:
                data = load_json(SOURCES_PATH)
            success, download_results = perform_download_tasks(data.get("GitHub", {}))
            if success:
                apply_download_results(download_results)
        else:
            logger.info("No updates found.")


def check_and_update_sources():
    updates_available, project_updates = check_for_updates()

    if updates_available:
        logger.info("Updates found. Updating sources.json...")
    else:
        logger.info("No updates found.")

    def mutator(data):
        for project_name, fields in project_updates.items():
            project = data["GitHub"].get(project_name)
            if not project:
                continue
            project["updated"] = fields.get("updated", project.get("updated", False))
            if "last_updated" in fields:
                project["last_updated"] = fields["last_updated"]
        data["last_checked"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for project_details in data["GitHub"].values():
            if project_details.get("updated"):
                project_details["highlight"] = True
            else:
                project_details.pop("highlight", None)

    update_json(SOURCES_PATH, mutator)


def apply_download_results(download_results):
    if not download_results:
        return

    def mutator(data):
        for project_name, release_timestamp in download_results.items():
            project = data["GitHub"].get(project_name)
            if not project:
                continue
            mark_download_complete(project, release_timestamp)
        for project_details in data["GitHub"].values():
            if project_details.get("updated"):
                project_details["highlight"] = True
            else:
                project_details.pop("highlight", None)

    update_json(SOURCES_PATH, mutator)


if __name__ == "__main__":
    main(force_download=True)
