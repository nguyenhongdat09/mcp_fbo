import os

bin_dir = r"z:\FBO\VLOTUS\SP228\bin"
results = []

for fname in os.listdir(bin_dir):
    if not fname.lower().endswith(".dll"):
        continue
    fpath = os.path.join(bin_dir, fname)
    try:
        with open(fpath, "rb") as f:
            data = f.read()
            if b"Encrypted" in data or b"E\x00n\x00c\x00r\x00y\x00p\x00t\x00e\x00d" in data:
                results.append(fname)
    except Exception as e:
        pass

print("DLLs containing 'Encrypted':", results)
