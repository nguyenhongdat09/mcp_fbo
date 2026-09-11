import os
import json
import sys
sys.stdout.reconfigure(encoding='utf-8')

base = r"e:\CustomizeExtension\fbo-autocomplete"

# 1. Check ConvertXml folder
convert_xml_dir = os.path.join(base, "src", "TreeFile", "ConvertXml")
print("ConvertXml dir exists:", os.path.exists(convert_xml_dir))
if os.path.exists(convert_xml_dir):
    for root, dirs, files in os.walk(convert_xml_dir):
        for f in files:
            print("  File in ConvertXml:", os.path.relpath(os.path.join(root, f), base))

# 2. Check package.json
pkg_path = os.path.join(base, "package.json")
with open(pkg_path, "r", encoding="utf-8") as f:
    pkg = json.load(f)

print("\nCommands related to ConvertXml in package.json:")
for cmd in pkg.get("contributes", {}).get("commands", []):
    if "convertxml" in cmd.get("command", "").lower():
        print(" ", cmd)

print("\nMenus related to ConvertXml in package.json:")
menus = pkg.get("contributes", {}).get("menus", {})
for menu_name, items in menus.items():
    for item in items:
        if "convertxml" in item.get("command", "").lower():
            print(f"  [{menu_name}]", item)

print("\nSettings related to convertXml in package.json:")
props = pkg.get("contributes", {}).get("configuration", {}).get("properties", {})
for p, v in props.items():
    if "convertxml" in p.lower():
        print(f"  {p}")

# 3. Check ContextMenu.js and other files
print("\nCode files referencing ConvertXml or convertXmlFromF:")
for root, dirs, files in os.walk(os.path.join(base, "src")):
    if "node_modules" in root or "dist" in root: continue
    for f in files:
        if f.endswith(".js"):
            fpath = os.path.join(root, f)
            with open(fpath, "r", encoding="utf-8", errors="ignore") as fp:
                txt = fp.read()
                if "convertxml" in txt.lower() or "fboencrypteddecryptor" in txt.lower():
                    print(" ", os.path.relpath(fpath, base))

# 4. Check package.json scripts
print("\nScripts in package.json:")
for s, cmd in pkg.get("scripts", {}).items():
    if "convert" in s.lower() or "convert" in cmd.lower():
        print(f"  {s}: {cmd}")
