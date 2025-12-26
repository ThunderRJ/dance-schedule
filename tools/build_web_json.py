from __future__ import annotations
import json, os
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
import yaml

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
            "title":str(c.get("title","")),
            "location":str(c.get("location","")),
            "instructor":str(c.get("instructor","")),
        })
    os.makedirs(docs,exist_ok=True)
    with open(os.path.join(docs,"schedule.json"),"w",encoding="utf-8") as f:
        json.dump({"events":events},f,ensure_ascii=False,indent=2)
    print("generated docs/schedule.json")

if __name__=="__main__":
    main()
