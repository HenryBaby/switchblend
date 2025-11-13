import os
import ftplib
import logging
import time
import posixpath

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ERROR_MESSAGES = {"Errno 113": "Error: Device not found. Is it offline?"}


def upload_to_device(ip, port, username, password, local_directory, files):
    try:
        ftp = ftplib.FTP()
        ftp.connect(ip, int(port))
        ftp.login(username, password)
        for file in files:
            full_path = os.path.join(local_directory, file)
            if os.path.isdir(full_path):
                upload_directory(ftp, full_path, file)
            else:
                upload_file(ftp, full_path, file)
        ftp.quit()
        return True, "Upload successful"
    except ftplib.all_errors as e:
        error_message = str(e)
        for err, user_message in ERROR_MESSAGES.items():
            if err in error_message:
                error_message = user_message
                break
        logger.error(f"FTP error: {str(e)}")
        return False, error_message
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return False, f"Unexpected error: {str(e)}"


def upload_file(ftp, local_path, remote_path, retries=3):
    attempt = 0
    while attempt < retries:
        try:
            ensure_remote_parent_directories(ftp, remote_path)
            delete_remote_file(ftp, remote_path)
            with open(local_path, "rb") as f:
                ftp.storbinary(f"STOR {remote_path}", f)
                logger.info(f"Uploaded {remote_path}")
                return True
        except ftplib.error_perm as e:
            if "450" in str(e):
                attempt += 1
                logger.warning(f"Retrying upload for {remote_path}, attempt {attempt}")
                time.sleep(2)
            else:
                logger.error(f"FTP error: {str(e)}")
                return False
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            return False
    logger.error(f"Failed to upload {remote_path} after {retries} attempts")
    return False


def delete_remote_file(ftp, remote_path):
    try:
        ftp.delete(remote_path)
        logger.info(f"Deleted remote file {remote_path}")
    except ftplib.error_perm as e:
        if "550" in str(e):
            logger.info(f"Remote file {remote_path} does not exist, no need to delete.")
        else:
            logger.error(f"Error deleting remote file {remote_path}: {str(e)}")
            raise


def ensure_remote_parent_directories(ftp, remote_path):
    directory = posixpath.dirname(remote_path)
    if not directory:
        return
    parts = directory.split("/")
    current_path = ""
    for part in parts:
        if not part:
            continue
        current_path = f"{current_path}/{part}" if current_path else part
        try:
            ftp.mkd(current_path)
            logger.info(f"Created remote directory {current_path}")
        except ftplib.error_perm as e:
            if not e.args[0].startswith("550"):
                logger.error(f"Error creating remote directory {current_path}: {str(e)}")
                raise


def upload_directory(ftp, local_directory, remote_directory):
    try:
        ftp.mkd(remote_directory)
    except ftplib.error_perm as e:
        if not e.args[0].startswith("550"):
            raise
    for entry in os.listdir(local_directory):
        local_path = os.path.join(local_directory, entry)
        remote_path = posixpath.join(remote_directory, entry)
        if os.path.isdir(local_path):
            upload_directory(ftp, local_path, remote_path)
        else:
            success = upload_file(ftp, local_path, remote_path)
            if not success:
                logger.error(f"Failed to upload {local_path}")
