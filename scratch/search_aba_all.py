import os

found = []
for p in [r"z:\FBO", r"z:\FBI", r"e:\PythonProject"]:
    if not os.path.exists(p):
        continue
    for root, dirs, files in os.walk(p):
        for f in files:
            if "accountbalanceadjustment" in f.lower():
                found.append(os.path.join(root, f))

print("Found files:")
for f in found:
    print(f)
