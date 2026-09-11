import sys
sys.stdout.reconfigure(encoding='utf-8')

fpath = r"e:\CustomizeExtension\fbo-autocomplete\src\doc\doc_fix_convert_xml\FIX-02-key-config-errors-tests.md"
with open(fpath, "r", encoding="utf-8") as f:
    print(f.read())
