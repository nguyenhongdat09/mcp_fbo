import os
import sys
sys.stdout.reconfigure(encoding='utf-8')

src_dir = r"e:\CustomizeExtension\fbo-autocomplete\src"
for root, dirs, files in os.walk(src_dir):
    if "node_modules" in root or "dist" in root:
        continue
    for f in files:
        fpath = os.path.join(root, f)
        with open(fpath, "r", encoding="utf-8", errors="ignore") as fp:
            content = fp.read()
            if any(k in content for k in ["keyBase64", "MD5 KDF", "Convert Xml", "<Encrypted>", "decrypt"]):
                print("FOUND IN TS/SRC:", fpath)
