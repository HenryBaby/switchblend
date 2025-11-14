import logging
import os
import zipfile
from datetime import datetime
from pathlib import Path

from storage import DOWNLOADS_DIR, OUTPUT_DIR

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def package_contents():
    directory_to_zip = OUTPUT_DIR
    timestamp = datetime.now().strftime("%Y%m%d")
    output_zip_file = DOWNLOADS_DIR / f"AIO-{timestamp}.zip"

    if not directory_to_zip.is_dir():
        logger.info(
            f"No files to package because {directory_to_zip} does not exist."
        )
        return

    if not any(directory_to_zip.iterdir()):
        logger.info(f"No files to package in {directory_to_zip}.")
        return

    DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(output_zip_file, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(directory_to_zip):
            for file in files:
                full_path = Path(root) / file
                relative_path = full_path.relative_to(directory_to_zip)
                zipf.write(full_path, arcname=relative_path)
                logger.info(f"Added file {full_path} as {relative_path} to the zip.")

            for dir in dirs:
                empty_dir_path = Path(root) / dir
                if not any(empty_dir_path.iterdir()):
                    zipf.write(empty_dir_path, arcname=empty_dir_path.relative_to(directory_to_zip))
                    logger.info(f"Added empty directory {empty_dir_path} to the zip.")

    logger.info(f"Packaged into {output_zip_file} successfully.")


if __name__ == "__main__":
    package_contents()
