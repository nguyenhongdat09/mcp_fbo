import os

search_name = "accountbalanceadjustment.xml"
found = []

def search_dir(base_dir, max_depth=6):
    for root, dirs, files in os.walk(base_dir):
        depth = root[len(base_dir):].count(os.sep)
        if depth > max_depth:
            dirs.clear()
            continue
        for f in files:
            if f.lower() == search_name:
                found.append(os.path.join(root, f))

for drive in [r"e:\PythonProject", r"z:\FBO", r"z:\FBI"]:
    if os.path.exists(drive):
        try:
            search_dir(drive)
        except Exception:
            pass

print("Found XML files:", found)
