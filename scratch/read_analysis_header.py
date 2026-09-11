import sys
sys.stdout.reconfigure(encoding='utf-8')

with open(r"e:\CustomizeExtension\fbo-autocomplete\src\doc\doc_convert_xml\02-fastbusiness-encryption-analysis.md", "r", encoding="utf-8") as f:
    lines = f.readlines()
    print("".join(lines[:100]))

print("="*50)

with open(r"e:\CustomizeExtension\fbo-autocomplete\src\doc\doc_fix_convert_xml\FIX-01-decrypt-encrypted-blocks.md", "r", encoding="utf-8") as f:
    print(f.read()[:2000])
