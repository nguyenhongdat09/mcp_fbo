import os
import sys
sys.stdout.reconfigure(encoding='utf-8')

base = r"e:\CustomizeExtension\fbo-autocomplete"
for root, dirs, files in os.walk(os.path.join(base, "src")):
    if "node_modules" in root or "dist" in root: continue
    for f in files:
        if f.endswith(".js"):
            fpath = os.path.join(root, f)
            with open(fpath, "r", encoding="utf-8", errors="ignore") as fp:
                txt = fp.read()
                if "file_f" in txt:
                    print("file_f in:", os.path.relpath(fpath, base))
