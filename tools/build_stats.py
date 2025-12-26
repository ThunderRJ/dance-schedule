from __future__ import annotations
import os, yaml, re, csv, json
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo

BODYJAM_RE = re.compile(r"BodyJam\s*(\d+)")

root = os.path.dirname(os.path.dirname(__file__))
with open(os.path.join(root,"schedule.yaml"),"r",encoding="utf-8") as f:
    cfg = yaml.safe_load(f)

tz = ZoneInfo(cfg.get("timezone","Asia/Shanghai"))
today = datetime.now(tz).date()
start = today - timedelta(days=365)

counts={}
last_seen={}

for c in cfg["classes"]:
    d = date.fromisoformat(c["date"])
    if not (start <= d <= today): continue
    for x in c.get("content",[]):
        m = BODYJAM_RE.search(x)
        if not m: continue
        name = f"BodyJam {int(m.group(1))}"
        counts[name]=counts.get(name,0)+1
        last_seen[name]=max(last_seen.get(name,d),d)

rows = sorted(counts.keys(), key=lambda k:(counts[k], last_seen[k]))
outdir = os.path.join(root,"docs","stats")
os.makedirs(outdir,exist_ok=True)
year = today.year

with open(os.path.join(outdir,f"bodyjam_rarest_{year}.md"),"w",encoding="utf-8") as f:
    f.write("# BodyJam 稀缺内容榜\n")
    for i,k in enumerate(rows,1):
        f.write(f"{i}. {k} - {counts[k]} 次，最近 {last_seen[k]}\n")

print("generated stats")
