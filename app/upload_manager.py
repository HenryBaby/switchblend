import os
import ftplib
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ERROR_MESSAGES = {"Errno 113": "Error: Device not found. Is it offline?"}


def upload_to_device(ip, port, username, password, local_directory):
    try:
        ftp = ftplib.FTP()
        ftp.connect(ip, int(port))
        ftp.login(username, password)
        upload_directory(ftp, local_directory)
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


def upload_directory(ftp, local_directory):
    for root, dirs, files in os.walk(local_directory):
        for dirname in dirs:
            local_path = os.path.join(root, dirname)
            relative_path = os.path.relpath(local_path, local_directory)
            try:
                ftp.mkd(relative_path)
            except ftplib.error_perm as e:
                if not e.args[0].startswith("550"):
                    raise
        for filename in files:
            local_path = os.path.join(root, filename)
            relative_path = os.path.relpath(local_path, local_directory)
            with open(local_path, "rb") as file:
                ftp.storbinary(f"STOR {relative_path}", file)
                logger.info(f"Uploaded {relative_path}")
