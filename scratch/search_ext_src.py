import os

base = r"e:\CustomizeExtension\fbo-autocomplete"
src_dir = os.path.join(base, "src")
found = []

for root, dirs, files in os.walk(src_dir):
    for f in files:
        if f.endswith((".ts", ".js", ".json")):
            fpath = os.path.join(root, f)
            with open(fpath, "r", encoding="utf-8", errors="ignore") as fp:
                content = fp.read()
                if "keyBase64" in content or "MD5 KDF" in content or "Convert Xml" in content or "<Encrypted>" in content or "decrypt" in content.lower():
                    found.append((fpath, [line for line in content.splitlines() if any(k in line.lower() for k in ["keybase64", "kdf", "convert xml", "encrypted", "decrypt"])][:5]))

for fpath, lines in found:
    print("FILE:", fpath)
    for l in lines:
        print("   ", l.strip())
