#!/usr/bin/env python3
"""N/A - compare original DOS unit-class state with the native contract body."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
ROOT=Path(__file__).resolve().parents[1]
def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args()
out=args.out.resolve()
out.mkdir(parents=True,exist_ok=False)
fixture_path=ROOT/'tests/fixtures/dos-unit-classes.json'
fixture=json.loads(fixture_path.read_text())
if sha(ROOT/'game/EXE/PANZER.EXE')!=fixture['authority']:
    raise ValueError('wrong DOS build')
state=bytearray(0x33240)
for span in fixture['input']['stateSpans']:
    data=bytes.fromhex(span['hex'])
    state[span['offset']:span['offset']+len(data)]=data
(out/'unit-input.bin').write_bytes(state)
spans,expected=bytearray(),bytearray()
for span in fixture['output']['stateSpans']:
    data=bytes.fromhex(span['hex'])
    spans.extend(struct.pack('>II',span['offset'],len(data)))
    expected.extend(data)
expected.extend(struct.pack('<I',fixture['output']['eax']))
(out/'unit-spans.bin').write_bytes(spans)
(out/'expected.bin').write_bytes(expected)
toolroot=ROOT.parent/'F030Arcade/third_party/chorensha/tools'
vasm=Path(os.environ.get('VASM',toolroot/'vasmm68k_mot_mac')).resolve()
vlink=Path(os.environ.get('VLINK',toolroot/'vlink_mac')).resolve()
hatari=Path(shutil.which(os.environ.get('HATARI','hatari'))).resolve()
tos=Path(os.environ.get('TOS',ROOT.parent/'F030Comanche/tools/toolchain/tos402.rom')).resolve()
assemble=[str(vasm),str(ROOT/'src/target/falcon/unit-classes-fixture.s'),'-quiet','-Felf',
          '-m68000','-I'+str(ROOT/'src/common'),'-o',str(out/'unit.o'),'-L',str(out/'unit.lst')]
link=[str(vlink),str(out/'unit.o'),'-q','-Rstd','-b','ataritos','-tos-flags','1',
      '-e','_main','-M','-o',str(out/'PGUNIT.TOS')]
subprocess.run(assemble,cwd=out,check=True)
with (out/'PGUNIT.map').open('w') as log:
    subprocess.run(link,cwd=out,check=True,stdout=log,stderr=subprocess.STDOUT)
command=[str(hatari),'--machine','falcon','--cpulevel','3','--cpuclock','16',
         '--cpu-exact','true','--compatible','true','--frameskips','0','--fpu','none',
         '--memsize','4','--tos',str(tos),'--patch-tos','true','--mmu','true','--dsp','off',
         '--monitor','rgb','--sound','off','--fast-boot','true','--fast-forward','true',
         '--confirm-quit','off','--disable-video','on','--run-vbls','1200','--alert-level','fatal',
         'PGUNIT.TOS']
sources=[ROOT/'src/common/unit-classes.s',ROOT/'src/common/rng.s',
         ROOT/'src/target/falcon/unit-classes-fixture.s',Path(__file__)]
record={'status':'Unproven','assemble':assemble,'link':link,'command':command,
        'sha256':{str(p):sha(p) for p in [vasm,vlink,hatari,tos,fixture_path,out/'PGUNIT.TOS',*sources]}}
try:
    with (out/'hatari.log').open('w') as log:
        proc=subprocess.run(command,cwd=out,stdin=subprocess.DEVNULL,
                            stdout=log,stderr=subprocess.STDOUT,timeout=60)
    record['hatariReturncode']=proc.returncode
    result=out/'PGUNIT.OUT'
    actual=result.read_bytes() if result.is_file() else b''
    if proc.returncode or actual!=expected:
        raise RuntimeError(f'native class setup differs from DOS: {len(actual)}/{len(expected)} bytes; see {out}')
    record.update(status='Verified Poland unit-class contract',bytesCompared=len(actual),resultSha256=sha(result))
    print(f'PASS native unit classes: {len(actual)} DOS bytes, 400 classes / averages / seed / EAX, Falcon030 4MB')
finally:
    (out/'result.json').write_text(json.dumps(record,indent=2)+'\n')
