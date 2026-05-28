#!/usr/bin/env python3
"""Read-only: re-read ROM65 on slave 207 with several READ-frame sizes and report where the
read-back first diverges from the CSV. If the first-diff index tracks the chunk size -> the
mismatch is a read-path artifact (verification bug, restore is fine). If it stays put at an
absolute index regardless of chunk size -> the stored content really differs."""
import subprocess, re, base64, struct, csv, time
PORT="/dev/ttyRS485-2"; SLAVE=207; BANK_TO_RAM=5501; ROM=65
CHUNKS=[60,100,125]
def mc(a): return subprocess.run(["modbus_client","-mrtu","-b9600","-pnone","-s2","-o","2000",
    PORT,"-a%d"%SLAVE]+a,capture_output=True,text=True,timeout=15).stdout
def parse(o):
    m=re.search(r"Data:\s*(.*)",o); return [int(t,16) for t in re.findall(r"0x[0-9a-fA-F]+",m.group(1))] if m else []
def codepart(v):
    o=[]
    for k,x in enumerate(v):
        o.append(x)
        if k>=1 and x==0 and v[k-1]==0: break
    return o
row=[r for r in csv.DictReader(open("/tmp/ir_backup_wb-msw-v3_207.csv")) if r["rom"]=="65"][0]
raw=base64.b64decode(row["code_base64"])
exp=[struct.unpack(">H",raw[i:i+2])[0] for i in range(0,len(raw),2)]
if exp[-2:]!=[0,0]: exp+=[0,0]
exp=codepart(exp)
n=len(exp)+8
def readback(chunk):
    mc(["-t0x06","-r%d"%BANK_TO_RAM,str(ROM)])
    got=[]; base=2000
    while base<2000+n:
        c=min(chunk,2000+n-base); got+=parse(mc(["-t0x03","-r%d"%base,"-c%d"%c]))[:c]; base+=c
    return codepart(got)
subprocess.run(["systemctl","stop","wb-mqtt-serial"],check=True); time.sleep(2)
try:
    print("expected codepart len:",len(exp))
    for chunk in CHUNKS:
        got=readback(chunk)
        diffs=[i for i in range(min(len(exp),len(got))) if exp[i]!=got[i]]
        first=diffs[0] if diffs else None
        print("chunk=%-3d  got_len=%-3d  num_diffs=%-3d  first_diff=%s"
              %(chunk,len(got),len(diffs),first))
finally:
    subprocess.run(["systemctl","start","wb-mqtt-serial"],check=False)
