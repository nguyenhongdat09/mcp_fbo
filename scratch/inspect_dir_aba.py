import sys
sys.stdout.reconfigure(encoding='utf-8')

with open(r"z:\FBO\KANEMATSU2\SP228\App_Data\Controllers\Dir\AccountBalanceAdjustment.xml", "r", encoding="utf-8-sig", errors="ignore") as f:
    text = f.read()

import re
commands = re.findall(r'<command[^>]*>[\s\S]*?</command>', text)
print("Commands count in Dir:", len(commands))
for c in commands:
    print(c[:200])
    print("...")

scripts = re.findall(r'<script[^>]*>[\s\S]*?</script>', text)
print("Scripts count in Dir:", len(scripts))
for s in scripts:
    print(s[:300])
