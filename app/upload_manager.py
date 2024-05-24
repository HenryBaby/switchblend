import os
import ftplib
import logging

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


def upload_file(ftp, local_path, remote_path):
    with open(local_path, "rb") as f:
        ftp.storbinary(f"STOR {remote_path}", f)
        logger.info(f"Uploaded {remote_path}")


def upload_directory(ftp, local_directory, remote_directory):
    try:
        ftp.mkd(remote_directory)
    except ftplib.error_perm as e:
        if not e.args[0].startswith("550"):
            raise
    for root, dirs, files in os.walk(local_directory):
        for dirname in dirs:
            local_path = os.path.join(root, dirname)
            rel_path = os.path.relpath(local_path, local_directory)
            remote_path = os.path.join(remote_directory, rel_path)
            upload_directory(ftp, local_path, remote_path)
        for filename in files:
            local_path = os.path.join(root, filename)
            rel_path = os.path.relpath(local_path, local_directory)
            remote_path = os.path.join(remote_directory, rel_path)
            upload_file(ftp, local_path, remote_path)
