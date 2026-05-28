#!/usr/bin/env python3
"""Read-only: verify EVERY referenced bank in the CSV against what's stored on the device now.
Definitive post-restore check, independent of the restore tool's in-run verify."""
import subprocess, re, base64, struct, csv, time, sys
PORT="/dev/ttyRS485-2"; BANK_TO_RAM=5501; VERIFY_READ_TRIES=6
CSVPATH=sys.argv[1]; SLAVE=int(sys.argv[2])
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
def expected(b64):
    raw=base64.b64decode(b64)
    e=[struct.unpack(">H",raw[i:i+2])[0] for i in range(0,len(raw),2)]
    if e[-2:]!=[0,0]: e+=[0,0]
    return codepart(e)
def readbank(rom,n):
    mc(["-t0x06","-r%d"%BANK_TO_RAM,str(rom)]); got=[]; base=2000
    while base<2000+n:
        c=min(125,2000+n-base); got+=parse(mc(["-t0x03","-r%d"%base,"-c%d"%c]))[:c]; base+=c
    return codepart(got)
rows=[r for r in csv.DictReader(open(CSVPATH)) if r["status"]=="ok"]
subprocess.run(["systemctl","stop","wb-mqtt-serial"],check=True); time.sleep(2)
ok=bad=0
try:
    for r in rows:
        rom=int(r["rom"]); exp=expected(r["code_base64"])
        # Read-back right after a large-code commit can be transiently wrong for several seconds
        # (the bank is correct, the read isn't); retry the verify read before declaring a mismatch.
        got=None
        for _ in range(VERIFY_READ_TRIES):
            got=readbank(rom,len(exp)+8)
            if got==exp: break
            time.sleep(3)
        if len(exp)==len(got) and exp==got: ok+=1
        else:
            bad+=1; print("ROM%-3d MISMATCH exp=%d got=%d"%(rom,len(exp),len(got)),file=sys.stderr)
    print("VERIFIED %d/%d banks match the backup"%(ok,ok+bad))
finally:
    subprocess.run(["systemctl","start","wb-mqtt-serial"],check=False)
sys.exit(1 if bad else 0)
