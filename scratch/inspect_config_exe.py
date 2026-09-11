import os
import pefile

exe_path = r"z:\FBO\VLOTUS\SP228\FastBusiness.Config.exe"
pe = pefile.PE(exe_path)
print("Sections:")
for s in pe.sections:
    print("  ", s.Name.decode('ascii', 'ignore').strip('\x00'), s.SizeOfRawData)

with open(exe_path, "rb") as f:
    data = f.read()

import re
strings = re.findall(rb'[A-Za-z0-9_/\.\-]{6,}', data)
print(f"Total ASCII strings > 6 chars: {len(strings)}")
matches = [s.decode('ascii') for s in strings if any(k in s.lower() for k in [b'encrypt', b'decrypt', b'key', b'secret', b'password', b'rijndael', b'aes'])]
print("Relevant strings in FastBusiness.Config.exe:")
for m in matches[:30]:
    print("  ", m)
