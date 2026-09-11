import os

found = []
base = r"z:\FBO"
for proj in os.listdir(base):
    proj_dir = os.path.join(base, proj)
    if not os.path.isdir(proj_dir): continue
    for root, dirs, files in os.walk(proj_dir):
        if "filter" in root.lower() and "accountbalanceadjustment.xml" in [f.lower() for f in files]:
            found.append(os.path.join(root, "AccountBalanceAdjustment.xml"))
        if root.count(os.sep) - proj_dir.count(os.sep) > 4:
            dirs.clear()

print("Found Filter XMLs:", found)
