import pefile

dll_path = r"z:\FBO\VLOTUS\SP228\bin\FastBusiness.Crypto.dll"
pe = pefile.PE(dll_path)
print("Sections:")
for s in pe.sections:
    print("  ", s.Name.decode('ascii', 'ignore').strip('\x00'), s.SizeOfRawData)

with open(dll_path, "rb") as f:
    data = f.read()

import re
strings = re.findall(rb'[A-Za-z0-9_/\.\-]{6,}', data)
matches = [s.decode('ascii') for s in strings if any(k in s.lower() for k in [b'encrypt', b'decrypt', b'key', b'secret', b'password', b'rijndael', b'aes', b'iv'])]
print("Relevant strings in FastBusiness.Crypto.dll:")
for m in set(matches):
    print("  ", m)
