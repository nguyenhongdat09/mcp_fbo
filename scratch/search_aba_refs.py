import os

controllers_dir = r"z:\FBO\VLOTUS\SP228\App_Data\Controllers"
found = []

for root, dirs, files in os.walk(controllers_dir):
    for f in files:
        fpath = os.path.join(root, f)
        try:
            with open(fpath, "r", encoding="utf-8", errors="ignore") as fp:
                content = fp.read()
                if "accountbalanceadjustment" in content.lower():
                    found.append((fpath, [l.strip() for l in content.splitlines() if "accountbalanceadjustment" in l.lower()][:3]))
        except Exception:
            pass

for p, lines in found:
    print("Found in:", p)
    for l in lines:
        print("   ", l)
