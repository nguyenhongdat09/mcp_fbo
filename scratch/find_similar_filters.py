import os
import re

filter_dir = r"z:\FBO\VLOTUS\SP228\App_Data\Controllers\Filter"
found = []

for f in os.listdir(filter_dir):
    if f.endswith(".xml"):
        fpath = os.path.join(filter_dir, f)
        try:
            with open(fpath, "r", encoding="utf-8", errors="ignore") as fp:
                txt = fp.read()
                if 'name="nam"' in txt and ('table="vdc' in txt or 'table="cd' in txt or 'table="sd' in txt or 'nam' in f.lower() or 'balance' in f.lower() or 'adjustment' in f.lower()):
                    found.append(f)
        except:
            pass

print("Matching Filter XML files:", found)
