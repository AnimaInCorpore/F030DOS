#!/usr/bin/env python3
"""Drive a QEMU run over QMP; run HMP commands, dump state."""
import subprocess, time, sys, socket, json, os
exe = r'C:\Program Files\Qemu\qemu-system-i386.exe'
args = [exe, '-M', 'pc', '-m', '8', '-hda', 'img/dos622.hdd', '-boot', 'c',
        '-display', 'none', '-nodefaults', '-serial', 'none',
        '-qmp', 'tcp:localhost:4555,server=on,wait=off']
q = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
s = None
for _ in range(30):
    time.sleep(1)
    try:
        s = socket.create_connection(('127.0.0.1', 4555), timeout=2)
        break
    except OSError:
        pass
if s is None:
    print('no QMP; qemu output:', q.stdout.read(2000))
    sys.exit(1)
f = s.makefile('r')
while True:
    line = f.readline()
    if line and 'QMP' in line:
        s.sendall(b'{"execute":"qmp_capabilities"}\n')
        break

def hmp(cmd):
    s.sendall(json.dumps({"execute": "human-monitor-command",
                          "arguments": {"command-line": cmd}}).encode() + b'\n')
    out = []
    while True:
        line = f.readline()
        if not line:
            break
        try:
            m = json.loads(line)
        except Exception:
            continue
        r = m.get('return')
        if r is not None:
            if isinstance(r, dict) and 'data' in r:
                out.append(r['data'])
            else:
                out.append(str(r))
        if 'error' in m:
            out.append('ERR: ' + m['error'].get('desc', '?'))
            break
    return '\n'.join(out)

print('=== set bp at 0x7ced (error path) ===')
print(hmp('break 0x7ced'))
time.sleep(4)
print('=== regs (at bp / running) ===')
print(hmp('info registers'))
print('=== mem @0x500 (root dir load area) ===')
print(hmp('xp 16xw 0x500'))
print('=== BPB @0x7c0b ===')
print(hmp('xp 10xw 0x7c0b'))
print('=== code @0x7ce0 ===')
print(hmp('xp /8i 0x7ce0'))
s.close()
q.kill()
