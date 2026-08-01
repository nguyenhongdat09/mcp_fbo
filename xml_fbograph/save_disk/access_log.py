import os
import json
import time
import uuid
import datetime
from pathlib import Path
import sys

from xml_fbograph.utils.path_helper import resolve_kuzu_db_base, _encode_project_root

LOG_FILE_NAME = "justify_project_log.json"
LOCK_FILE_NAME = "justify_project_log.json.lock"

# Determine OS for locking
if sys.platform == "win32":
    import msvcrt
    
    def lock_file(f):
        try:
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            return True
        except OSError:
            return False
            
    def unlock_file(f):
        try:
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
else:
    import fcntl
    
    def lock_file(f):
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except OSError:
            return False
            
    def unlock_file(f):
        try:
            fcntl.flock(f, fcntl.LOCK_UN)
        except OSError:
            pass

def _get_log_paths():
    base_dir = resolve_kuzu_db_base()
    log_file = base_dir / LOG_FILE_NAME
    lock_file = base_dir / LOCK_FILE_NAME
    return log_file, lock_file

def _read_log_no_lock(log_file: Path) -> dict:
    if not log_file.exists():
        return {"updated_at": "", "entries": {}}
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "entries" not in data:
                data["entries"] = {}
            return data
    except Exception:
        # Corrupted or unreadable, start fresh
        return {"updated_at": "", "entries": {}}

def touch_kuzu_access(project_root: str) -> None:
    """
    Updates the access log for a given project.
    Creates or updates an entry with the current timestamp.
    Fail-soft: handles locking gracefully and does not crash on errors.
    """
    try:
        log_file, lock_path = _get_log_paths()
        
        # Ensure base directory exists
        base_dir = log_file.parent
        base_dir.mkdir(parents=True, exist_ok=True)
        
        encoded_folder = _encode_project_root(project_root)
        now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
        # Retry loop for locking
        max_retries = 10
        delay = 0.1
        lock_fd = None
        
        try:
            for attempt in range(max_retries):
                try:
                    # Open lock file (create if not exists)
                    lock_fd = open(lock_path, "a")
                    if lock_file(lock_fd):
                        # Lock acquired successfully
                        break
                    else:
                        lock_fd.close()
                        lock_fd = None
                except Exception:
                    if lock_fd:
                        lock_fd.close()
                        lock_fd = None
                
                time.sleep(delay)
                
            if not lock_fd:
                # Could not acquire lock, fail softly
                sys.stderr.write(f"[SaveDisk] Could not acquire lock to touch access log for {project_root}\n")
                return
                
            # Read current data
            data = _read_log_no_lock(log_file)
            
            # Update data
            data["updated_at"] = now_str
            if encoded_folder not in data["entries"]:
                data["entries"][encoded_folder] = {}
                
            data["entries"][encoded_folder]["last_access"] = now_str
            data["entries"][encoded_folder]["project_root"] = str(project_root)
            
            # Atomic write
            tmp_file = log_file.with_name(f"{LOG_FILE_NAME}.{uuid.uuid4().hex}.tmp")
            try:
                with open(tmp_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                
                os.replace(tmp_file, log_file)
            finally:
                if tmp_file.exists():
                    try:
                        tmp_file.unlink()
                    except Exception:
                        pass
        finally:
            if lock_fd:
                unlock_file(lock_fd)
                lock_fd.close()
    except Exception as e:
        sys.stderr.write(f"[SaveDisk] Error in touch_kuzu_access: {e}\n")
