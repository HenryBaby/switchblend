import ftplib
import logging
import os
import posixpath
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class UploadError(Exception):
    """Raised when an FTP upload step fails."""


ERROR_MESSAGES = {
    "Errno 113": "Error: Device not found. Is it offline?",
    "Errno 111": "Error: Connection refused by the device.",
    "timed out": "Error: Connection timed out while reaching the device.",
}


def upload_to_device(ip, port, username, password, local_directory, files):
    ftp = ftplib.FTP()
    try:
        ftp.connect(ip, int(port))
        ftp.login(username, password)
        for file in files:
            full_path = os.path.join(local_directory, file)
            if os.path.isdir(full_path):
                upload_directory(ftp, full_path, file)
            else:
                upload_file(ftp, full_path, file)
        return True, "Upload successful"
    except UploadError as e:
        logger.error(f"Upload error: {str(e)}")
        return False, str(e)
    except ftplib.all_errors as e:
        error_message = _resolve_error_message(e)
        logger.error(f"FTP error: {str(e)}")
        return False, error_message
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return False, f"Unexpected error: {str(e)}"
    finally:
        _close_ftp(ftp)


def upload_file(ftp, local_path, remote_path, retries=3):
    attempt = 0
    while attempt < retries:
        try:
            ensure_remote_parent_directories(ftp, remote_path)
            delete_remote_file(ftp, remote_path)
            with open(local_path, "rb") as f:
                ftp.storbinary(f"STOR {remote_path}", f)
                logger.info(f"Uploaded {remote_path}")
                return
        except ftplib.error_perm as e:
            if "450" in str(e):
                attempt += 1
                logger.warning(f"Retrying upload for {remote_path}, attempt {attempt}")
                time.sleep(2)
            else:
                raise UploadError(f"FTP error while uploading {remote_path}: {str(e)}") from e
        except UploadError:
            raise
        except Exception as e:
            raise UploadError(f"Unexpected error while uploading {remote_path}: {str(e)}") from e
    raise UploadError(f"Failed to upload {remote_path} after {retries} attempts")


def delete_remote_file(ftp, remote_path):
    try:
        ftp.delete(remote_path)
        logger.info(f"Deleted remote file {remote_path}")
    except ftplib.error_perm as e:
        if "550" in str(e):
            logger.info(f"Remote file {remote_path} does not exist, no need to delete.")
        else:
            raise UploadError(f"Error deleting remote file {remote_path}: {str(e)}") from e


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
                raise UploadError(
                    f"Error creating remote directory {current_path}: {str(e)}"
                ) from e


def upload_directory(ftp, local_directory, remote_directory):
    try:
        ftp.mkd(remote_directory)
    except ftplib.error_perm as e:
        if not e.args[0].startswith("550"):
            raise UploadError(
                f"Error creating remote directory {remote_directory}: {str(e)}"
            ) from e
    try:
        entries = os.listdir(local_directory)
    except OSError as e:
        raise UploadError(
            f"Unable to read local directory {local_directory}: {str(e)}"
        ) from e
    for entry in entries:
        local_path = os.path.join(local_directory, entry)
        remote_path = posixpath.join(remote_directory, entry)
        if os.path.isdir(local_path):
            upload_directory(ftp, local_path, remote_path)
        else:
            upload_file(ftp, local_path, remote_path)


def _resolve_error_message(error):
    message = str(error)
    for signature, user_message in ERROR_MESSAGES.items():
        if signature in message:
            return user_message
    return message


def _close_ftp(ftp):
    if ftp is None:
        return
    try:
        ftp.quit()
    except ftplib.all_errors:
        try:
            ftp.close()
        except Exception:
            pass
    except Exception:
        try:
            ftp.close()
        except Exception:
            pass
