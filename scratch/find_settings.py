import os
import json

paths = [
    os.path.expandvars(r"%APPDATA%\Code\User\settings.json"),
    os.path.expandvars(r"%APPDATA%\Antigravity\User\settings.json"),
    os.path.expandvars(r"%USERPROFILE%\.gemini\antigravity-ide\settings.json"),
    r"e:\CustomizeExtension\fbo-autocomplete\.vscode\settings.json",
    r"e:\PythonProject\mcp_fbo\.vscode\settings.json",
]

for p in paths:
    if os.path.exists(p):
        print("Found settings file:", p)
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
                for k, v in data.items():
                    if "convertxml" in k.lower() or "fbo" in k.lower() or "encrypt" in k.lower():
                        print(f"   {k}: {v}")
        except Exception as e:
            print("   Error reading:", e)
    else:
        print("Not found:", p)
