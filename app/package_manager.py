import os
import zipfile
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def package_contents():
    directory_to_zip = "downloads/output/"
    timestamp = datetime.now().strftime("%Y%m%d")
    output_zip_file = f"downloads/AIO-{timestamp}.zip"

    if not any(os.scandir(directory_to_zip)):
        logger.info(f"No files to package in {directory_to_zip}.")
        return

    if not os.path.exists("downloads/"):
        os.makedirs("downloads/")

    with zipfile.ZipFile(output_zip_file, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(directory_to_zip):
            for file in files:
                full_path = os.path.join(root, file)
                relative_path = os.path.relpath(full_path, directory_to_zip)
                zipf.write(full_path, arcname=relative_path)
                logger.info(f"Added file {full_path} as {relative_path} to the zip.")

            for dir in dirs:
                empty_dir_path = os.path.join(root, dir)
                if not os.listdir(empty_dir_path):
                    zipf.write(
                        empty_dir_path,
                        arcname=os.path.relpath(empty_dir_path, directory_to_zip),
                    )
                    logger.info(f"Added empty directory {empty_dir_path} to the zip.")

    logger.info(f"Packaged into {output_zip_file} successfully.")


if __name__ == "__main__":
    package_contents()
