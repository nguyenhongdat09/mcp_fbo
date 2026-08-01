import os
import sys
import time
import datetime
import shutil
import uuid
import json
from pathlib import Path
from typing import Optional

from xml_fbograph.utils.path_helper import resolve_kuzu_db_base
from xml_fbograph.save_disk.retention_config import get_access_log_retention_days
from xml_fbograph.save_disk.access_log import _get_log_paths, _read_log_no_lock, LOG_FILE_NAME

CLEANUP_MARKER_NAME = ".last_cleanup"
CLEANUP_LOCK_NAME = ".cleanup.lock"

# Reuse the locking mechanism from access_log
from xml_fbograph.save_disk.access_log import lock_file, unlock_file

def _get_cleanup_paths():
    base_dir = resolve_kuzu_db_base()
    marker_file = base_dir / CLEANUP_MARKER_NAME
    lock_file = base_dir / CLEANUP_LOCK_NAME
    return marker_file, lock_file

def _is_time_for_cleanup() -> bool:
    """Check if 24 hours have passed since the last cleanup."""
    marker_file, _ = _get_cleanup_paths()
    if not marker_file.exists():
        return True
    
    try:
        mtime = marker_file.stat().st_mtime
        now = time.time()
        # 24 hours = 86400 seconds
        return (now - mtime) > 86400
    except Exception:
        return True

def _mark_cleanup_done():
    """Touch the marker file to update its mtime."""
    marker_file, _ = _get_cleanup_paths()
    try:
        marker_file.parent.mkdir(parents=True, exist_ok=True)
        marker_file.touch()
    except Exception as e:
        sys.stderr.write(f"[SaveDisk] Could not touch cleanup marker: {e}\n")

def _safe_remove_entry(log_file: Path, lock_path: Path, encoded_folder: str):
    """Remove a stale entry from the JSON log atomically under short lock."""
    max_retries = 10
    delay = 0.1
    lock_fd = None
    
    try:
        for attempt in range(max_retries):
            try:
                lock_fd = open(lock_path, "a")
                if lock_file(lock_fd):
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
            return
            
        data = _read_log_no_lock(log_file)
        if "entries" in data and encoded_folder in data["entries"]:
            del data["entries"][encoded_folder]
            
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
    except Exception:
        pass
    finally:
        if lock_fd:
            unlock_file(lock_fd)
            lock_fd.close()

def _physical_delete_folder(folder_path: Path) -> bool:
    """Safe delete a directory, ignoring errors from active locks."""
    try:
        shutil.rmtree(folder_path)
        return True
    except (PermissionError, OSError) as e:
        sys.stderr.write(f"[SaveDisk] Skip deleting {folder_path.name} (locked/in-use): {e}\n")
        return False
    except Exception as e:
        sys.stderr.write(f"[SaveDisk] Error deleting {folder_path.name}: {e}\n")
        return False

def cleanup_stale_kuzu_projects(retention_days: Optional[int] = None) -> None:
    """
    Main logic to scan and delete stale Kuzu DB projects.
    Can be run via CLI or background throttled task.
    """
    if retention_days is None:
        retention_days = get_access_log_retention_days()
        
    base_dir = resolve_kuzu_db_base()
    if not base_dir.exists() or not base_dir.is_dir():
        return
        
    log_file, log_lock_path = _get_log_paths()
    
    # 1. Read snapshot of log without locking (it's safe enough for making decisions)
    data = _read_log_no_lock(log_file)
    entries = data.get("entries", {})
    
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    threshold = now_utc - datetime.timedelta(days=retention_days)
    
    # 2. Scan all subfolders with .fbograph
    for item in base_dir.iterdir():
        if not item.is_dir() or item.name.startswith("."):
            continue
            
        fbograph_dir = item / ".fbograph"
        if not fbograph_dir.is_dir():
            continue
            
        encoded_folder = item.name
        stale = False
        
        if encoded_folder in entries:
            last_access_str = entries[encoded_folder].get("last_access")
            if last_access_str:
                try:
                    last_access_dt = datetime.datetime.fromisoformat(last_access_str)
                    if last_access_dt < threshold:
                        stale = True
                except ValueError:
                    stale = True
        else:
            # Not in log, check physical mtime of .fbograph
            try:
                mtime = fbograph_dir.stat().st_mtime
                mtime_dt = datetime.datetime.fromtimestamp(mtime, tz=datetime.timezone.utc)
                if mtime_dt < threshold:
                    stale = True
                else:
                    # Not stale yet but not in log -> touch it so it gets tracked
                    # We can decode the project root from the folder name, but since we just need it tracked,
                    # we will just add a dummy entry or let it be touched on next access.
                    # It's better to just touch it with the folder name as project root for now.
                    from xml_fbograph.utils.path_helper import decode_project_root
                    project_root = decode_project_root(encoded_folder)
                    if project_root:
                        from xml_fbograph.save_disk.access_log import touch_kuzu_access
                        touch_kuzu_access(project_root)
            except Exception:
                pass
                
        if stale:
            sys.stderr.write(f"[SaveDisk] Found stale project: {encoded_folder} (unused for > {retention_days} days). Deleting...\n")
            if _physical_delete_folder(item):
                if encoded_folder in entries:
                    _safe_remove_entry(log_file, log_lock_path, encoded_folder)


def maybe_cleanup_stale_kuzu() -> None:
    """
    Throttled entry point to cleanup stale Kuzu DB projects.
    Uses a lock to prevent concurrent cleanups across processes.
    """
    # Quick check without lock
    if not _is_time_for_cleanup():
        return
        
    _, lock_path = _get_cleanup_paths()
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    
    lock_fd = None
    try:
        lock_fd = open(lock_path, "a")
        # Non-blocking lock. If another process is cleaning up, just skip.
        if lock_file(lock_fd):
            # Double check after acquiring lock
            if _is_time_for_cleanup():
                try:
                    cleanup_stale_kuzu_projects()
                finally:
                    _mark_cleanup_done()
    except Exception as e:
        sys.stderr.write(f"[SaveDisk] Error in maybe_cleanup_stale_kuzu: {e}\n")
    finally:
        if lock_fd:
            unlock_file(lock_fd)
            lock_fd.close()
