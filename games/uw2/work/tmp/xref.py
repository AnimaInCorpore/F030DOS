import sys,struct
d=open('/Users/saschaspringer/Work/F030Underworld2/work/extracted/D3/UW2.EXE','rb').read()
targets=[int(x,16) for x in sys.argv[1:]]
res={t:[] for t in targets}
for i in range(len(d)-5):
    if d[i]==0x9a:
        off,seg=struct.unpack_from('<HH',d,i+1)
        t=0x2E00+(seg<<4)+off
        if t in res: res[t].append(('far',i))
    if d[i]==0xe8:
        rel=struct.unpack_from('<h',d,i+1)[0]
        t=i+3+rel
        if t in res: res[t].append(('near',i))
for t in targets:
    print(hex(t), [(k,hex(v)) for k,v in res[t]][:40], 'count',len(res[t]))
