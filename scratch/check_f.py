import re
import os

fpath = r"z:\FBO\VLOTUS\SP228\App_Data\Controllers\Filter\AccountBalanceAdjustment.f"
with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
    content = f.read()

print(f"File length: {len(content)}")
tags = re.findall(r'<Encrypted>([\s\S]*?)</Encrypted>', content)
print(f"Found {len(tags)} <Encrypted> tags")

matches = re.finditer(r'([a-zA-Z0-9_:]*encrypt[a-zA-Z0-9_:]*)\s*=\s*"([^"]+)"', content, re.IGNORECASE)
attr_list = list(matches)
print(f"Found {len(attr_list)} encrypt attributes")
for m in attr_list[:5]:
    print(f"Attr: {m.group(1)} -> {m.group(2)[:30]}...")

matches_tag = re.finditer(r'<([a-zA-Z0-9_:]*encrypt[a-zA-Z0-9_:]*)[^>]*>([\s\S]*?)</\1>', content, re.IGNORECASE)
tag_list = list(matches_tag)
print(f"Found {len(tag_list)} encrypt tags (case-insensitive)")
for m in tag_list:
    print(f"Tag: {m.group(1)} -> content length {len(m.group(2))}")
