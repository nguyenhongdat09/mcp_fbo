import os
import json
import time
import datetime
import threading
from pathlib import Path

from xml_fbograph.save_disk import touch_kuzu_access, cleanup_stale_kuzu_projects
from xml_fbograph.save_disk.access_log import LOG_FILE_NAME, _read_log_no_lock
from xml_fbograph.utils.path_helper import resolve_kuzu_db_base, _encode_project_root, reset_config_caches

def test_touch_creates_json(monkeypatch, tmp_path):
    reset_config_caches()
    monkeypatch.setenv("FBOGRAPH_KUZU_BASE", str(tmp_path))
    
    project_root = r"\\172.168.5.14\CustomerPro\FBI\CNNB_FBI\FBISP229"
    encoded = _encode_project_root(project_root)
    
    touch_kuzu_access(project_root)
    
    log_file = tmp_path / LOG_FILE_NAME
    assert log_file.exists()
    
    data = _read_log_no_lock(log_file)
    assert encoded in data["entries"]
    assert data["entries"][encoded]["project_root"] == project_root
    assert "last_access" in data["entries"][encoded]

def test_concurrent_touch_no_corruption(monkeypatch, tmp_path):
    reset_config_caches()
    monkeypatch.setenv("FBOGRAPH_KUZU_BASE", str(tmp_path))
    
    project_roots = [
        rf"\\172.168.5.14\CustomerPro\Project{i}"
        for i in range(10)
    ]
    
    def touch_thread(pr):
        for _ in range(5):
            touch_kuzu_access(pr)
            
    threads = []
    for pr in project_roots:
        t = threading.Thread(target=touch_thread, args=(pr,))
        threads.append(t)
        t.start()
        
    for t in threads:
        t.join()
        
    # Verify the JSON is not corrupted and contains all entries
    log_file = tmp_path / LOG_FILE_NAME
    assert log_file.exists()
    
    data = _read_log_no_lock(log_file)
    assert len(data["entries"]) == 10
    
    for pr in project_roots:
        encoded = _encode_project_root(pr)
        assert encoded in data["entries"]
        assert data["entries"][encoded]["project_root"] == pr

def test_cleanup_stale_kuzu_projects(monkeypatch, tmp_path):
    reset_config_caches()
    monkeypatch.setenv("FBOGRAPH_KUZU_BASE", str(tmp_path))
    
    # Create two projects: one fresh, one stale
    fresh_project = r"\\172.168.5.14\CustomerPro\Fresh"
    stale_project = r"\\172.168.5.14\CustomerPro\Stale"
    
    fresh_encoded = _encode_project_root(fresh_project)
    stale_encoded = _encode_project_root(stale_project)
    
    # Touch fresh project
    touch_kuzu_access(fresh_project)
    
    # Manually create stale project entry simulating 40 days ago
    log_file = tmp_path / LOG_FILE_NAME
    data = _read_log_no_lock(log_file)
    
    forty_days_ago = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=40)
    data["entries"][stale_encoded] = {
        "last_access": forty_days_ago.isoformat(),
        "project_root": stale_project
    }
    
    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        
    # Create physical folders
    fresh_dir = tmp_path / fresh_encoded / ".fbograph"
    fresh_dir.mkdir(parents=True)
    
    stale_dir = tmp_path / stale_encoded / ".fbograph"
    stale_dir.mkdir(parents=True)
    
    assert fresh_dir.exists()
    assert stale_dir.exists()
    
    # Run cleanup (retention 30 days)
    cleanup_stale_kuzu_projects(retention_days=30)
    
    # Fresh should exist, stale should be deleted
    assert fresh_dir.exists()
    assert not stale_dir.exists()
    
    # Stale entry should be removed from JSON
    data_after = _read_log_no_lock(log_file)
    assert fresh_encoded in data_after["entries"]
    assert stale_encoded not in data_after["entries"]

def test_cleanup_unlogged_but_stale_folder(monkeypatch, tmp_path):
    reset_config_caches()
    monkeypatch.setenv("FBOGRAPH_KUZU_BASE", str(tmp_path))
    
    unlogged_stale_project = r"\\172.168.5.14\CustomerPro\UnloggedStale"
    unlogged_fresh_project = r"\\172.168.5.14\CustomerPro\UnloggedFresh"
    
    encoded_stale = _encode_project_root(unlogged_stale_project)
    encoded_fresh = _encode_project_root(unlogged_fresh_project)
    
    dir_stale = tmp_path / encoded_stale / ".fbograph"
    dir_fresh = tmp_path / encoded_fresh / ".fbograph"
    
    dir_stale.mkdir(parents=True)
    dir_fresh.mkdir(parents=True)
    
    # Modify mtime of stale dir to 40 days ago
    forty_days_ago = time.time() - 40 * 86400
    os.utime(dir_stale, (forty_days_ago, forty_days_ago))
    
    # Run cleanup
    cleanup_stale_kuzu_projects(retention_days=30)
    
    assert not dir_stale.exists()
    assert dir_fresh.exists()
    
    # Unlogged fresh should now be tracked
    log_file = tmp_path / LOG_FILE_NAME
    data = _read_log_no_lock(log_file)
    assert encoded_fresh in data["entries"]
    assert encoded_stale not in data["entries"]
