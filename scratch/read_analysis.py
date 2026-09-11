import sys
sys.stdout.reconfigure(encoding='utf-8')

with open(r"e:\CustomizeExtension\fbo-autocomplete\src\doc\doc_convert_xml\02-fastbusiness-encryption-analysis.md", "r", encoding="utf-8") as f:
    print(f.read())

print("="*50)

with open(r"e:\CustomizeExtension\fbo-autocomplete\src\TreeFile\ConvertXml\tests\FboEncryptedDecryptor.test.js", "r", encoding="utf-8") as f:
    print(f.read())
