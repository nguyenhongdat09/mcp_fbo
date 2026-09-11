import sys
sys.stdout.reconfigure(encoding='utf-8')

fpath = r"e:\CustomizeExtension\fbo-autocomplete\src\doc\doc_convert_xml\01-architecture-and-menus.md"
with open(fpath, "r", encoding="utf-8") as f:
    print(f.read())
