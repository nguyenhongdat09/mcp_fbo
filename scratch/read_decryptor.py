import sys
sys.stdout.reconfigure(encoding='utf-8')

fpath = r"e:\CustomizeExtension\fbo-autocomplete\src\TreeFile\ConvertXml\FboEncryptedDecryptor.js"
with open(fpath, "r", encoding="utf-8") as f:
    print(f.read())
