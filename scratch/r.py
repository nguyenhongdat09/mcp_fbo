import socket, sys
code = sys.stdin.read()
s = socket.socket(); s.settimeout(600); s.connect(('127.0.0.1', 58731))
s.sendall(code.encode('utf-8') + b'<END>')
out = b''
while True:
    d = s.recv(65536)
    if not d: break
    out += d
sys.stdout.buffer.write(out)
