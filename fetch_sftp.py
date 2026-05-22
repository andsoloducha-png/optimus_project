import posixpath
from datetime import datetime

import paramiko

from config import REMOTE_DIR, TIMEOUT_SEC


def build_today_target_prefix():
    today = datetime.today().strftime("%Y-%m-%d")
    return f"{today}_alarmlog"


def is_matching_alarmlog(filename: str, target_prefix: str) -> bool:
    lower = filename.lower()
    return target_prefix.lower() in lower and lower.endswith((".txt", ".csv"))


def connect_sftp(host: str, port: int, username: str, password: str):
    transport = paramiko.Transport((host, port))
    transport.banner_timeout = TIMEOUT_SEC
    transport.connect(username=username, password=password)
    sftp = paramiko.SFTPClient.from_transport(transport)
    return transport, sftp


def find_today_remote_file(sftp, remote_dir: str):
    target_prefix = build_today_target_prefix()
    entries = sftp.listdir_attr(remote_dir)

    candidates = []
    for entry in entries:
        filename = entry.filename
        if is_matching_alarmlog(filename, target_prefix):
            full_path = posixpath.join(remote_dir, filename)
            candidates.append((entry.st_mtime, full_path, filename, entry.st_size))

    if not candidates:
        return None

    candidates.sort(reverse=True, key=lambda x: x[0])
    _, full_path, filename, file_size = candidates[0]
    return {
        "remote_path": full_path,
        "filename": filename,
        "size": file_size,
    }


def read_remote_text_file(sftp, remote_path: str) -> str:
    with sftp.open(remote_path, "r") as remote_file:
        raw = remote_file.read()

    if isinstance(raw, bytes):
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return raw.decode("cp1252", errors="replace")
    return str(raw)


def fetch_today_logs_from_all_sorters(sorters: dict, username: str, password: str, port: int, remote_dir: str = REMOTE_DIR):
    results = {}
    errors = {}

    for sorter_name, host in sorters.items():
        transport = None
        sftp = None
        try:
            transport, sftp = connect_sftp(host=host, port=port, username=username, password=password)
            found = find_today_remote_file(sftp, remote_dir)

            if not found:
                errors[sorter_name] = f"Brak dzisiejszego pliku alarmlog w {remote_dir}"
                continue

            content = read_remote_text_file(sftp, found["remote_path"])

            results[sorter_name] = {
                "host": host,
                "filename": found["filename"],
                "remote_path": found["remote_path"],
                "content": content,
                "size": found["size"],
            }

        except Exception as e:
            errors[sorter_name] = str(e)

        finally:
            try:
                if sftp:
                    sftp.close()
            except Exception:
                pass
            try:
                if transport:
                    transport.close()
            except Exception:
                pass

    return results, errors