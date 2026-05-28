#!/usr/bin/env python3
"""Read back the CURRENT stored ROM65 on slave 207 and diff it against the expected code from
the CSV, to characterise the verify mismatch (transform vs corruption). Read-only -- no write."""
import subprocess, re, base64, struct, csv, time
PORT="/dev/ttyRS485-2"; SLAVE=207; BANK_TO_RAM=5501
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
subprocess.run(["systemctl","stop","wb-mqtt-serial"],check=True); time.sleep(2)
try:
    mc(["-t0x06","-r%d"%BANK_TO_RAM,"65"])
    got=[]
    n=len(exp)+8; base=2000
    while base<2000+n:
        c=min(125,2000+n-base); got+=parse(mc(["-t0x03","-r%d"%base,"-c%d"%c]))[:c]; base+=c
    got=codepart(got)
    print("expected codepart len:",len(exp),"  read-back codepart len:",len(got))
    diffs=[i for i in range(min(len(exp),len(got))) if exp[i]!=got[i]]
    print("num differing positions:",len(diffs))
    print("expected[0:12]:",exp[:12])
    print("readback[0:12]:",got[:12])
    if diffs:
        i=diffs[0]; lo=max(0,i-3); hi=i+5
        print("first diff at index",i)
        print("  expected[%d:%d]:"%(lo,hi),exp[lo:hi])
        print("  readback[%d:%d]:"%(lo,hi),got[lo:hi])
        print("last 8 expected:",exp[-8:])
        print("last 8 readback:",got[-8:])
finally:
    subprocess.run(["systemctl","start","wb-mqtt-serial"],check=False)
