import re

with open(r"z:\FBO\VLOTUS\SP228\Web.config", "r", encoding="utf-8", errors="ignore") as f:
    text = f.read()

handlers = re.findall(r'<add\s+[^>]*type="([^"]+)"[^>]*>', text)
for h in set(handlers):
    if any(x in h.lower() for x in ["view", "fastbusiness", "controller", "filter", "query", "handler"]):
        print(h)
