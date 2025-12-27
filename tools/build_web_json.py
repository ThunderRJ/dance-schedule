from __future__ import annotations
import json, os, re, shutil
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
import yaml

def find_latest_stats_json(stats_dir: str) -> str | None:
    if not os.path.isdir(stats_dir):
        return None
    items=[]
    for fn in os.listdir(stats_dir):
        m=re.fullmatch(r"bodyjam_rarest_(\d{4})\.json",fn)
        if m:
            items.append((int(m.group(1)), os.path.join(stats_dir,fn)))
    if not items:
        return None
    items.sort(key=lambda x:x[0], reverse=True)
    return items[0][1]

def main():
    root=os.path.dirname(os.path.dirname(__file__))
    docs=os.path.join(root,"docs")
    with open(os.path.join(root,"schedule.yaml"),"r",encoding="utf-8") as f:
        obj=yaml.safe_load(f) or {}
    tz=ZoneInfo(obj.get("timezone","Asia/Shanghai"))
    today=datetime.now(tz).date()
    start=today-timedelta(days=30)
    end=today+timedelta(days=7)
    events=[]
    for c in obj.get("classes") or []:
        if not isinstance(c,dict): continue
        d=date.fromisoformat(str(c.get("date")))
        if not(start<=d<=end): continue
        events.append({
            "date":d.isoformat(),
            "start":str(c.get("start","")),
            "duration_min":int(c.get("duration_min",0) or 0),
            "title":str(c.get("title","")),
            "location":str(c.get("location","")),
            "instructor":str(c.get("instructor","")),
            "bodyjam":c.get("bodyjam") if isinstance(c.get("bodyjam"),dict) else None,
            "content":c.get("content") if isinstance(c.get("content"),list) else []
        })
    events.sort(key=lambda e:(e["date"],e["start"],e["title"],e["location"]))
    os.makedirs(docs,exist_ok=True)
    with open(os.path.join(docs,"schedule.json"),"w",encoding="utf-8") as f:
        json.dump({
            "generated_at":datetime.now(tz).isoformat(timespec="seconds"),
            "timezone":obj.get("timezone","Asia/Shanghai"),
            "events":events
        },f,ensure_ascii=False,indent=2)

    stats_dir=os.path.join(docs,"stats")
    latest=find_latest_stats_json(stats_dir)
    if latest:
        shutil.copyfile(latest, os.path.join(stats_dir,"bodyjam_rarest_latest.json"))

if __name__=="__main__":
    main()
