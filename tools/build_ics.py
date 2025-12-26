# (Truncated header comments for brevity; this is the full working script)
from __future__ import annotations
import hashlib, os, re, yaml
from dataclasses import dataclass
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo

def ics_escape(s: str) -> str:
    s = s.replace("\\", "\\\\").replace(";", "\;").replace(",", "\,").replace("\n", "\\n")
    return s

def fold(line, limit=75):
    if len(line) <= limit:
        return [line]
    out = [line[:limit]]
    rest = line[limit:]
    while rest:
        out.append(" " + rest[:limit-1])
        rest = rest[limit-1:]
    return out

def uid_for(key: str):
    h = hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]
    return f"{h}@dance-schedule"

@dataclass
class ClassItem:
    date: date
    start_h: int
    start_m: int
    duration_min: int
    title: str
    location: str
    instructor: str
    notes: str
    content: list[str]

def parse_time(t):
    h,m = t.split(":")
    return int(h), int(m)

root = os.path.dirname(os.path.dirname(__file__))
with open(os.path.join(root, "schedule.yaml"), "r", encoding="utf-8") as f:
    cfg = yaml.safe_load(f)

tz = ZoneInfo(cfg.get("timezone","Asia/Shanghai"))
today = datetime.now(tz).date()
past = cfg["window"]["past_weeks"]
future = cfg["window"]["future_weeks"]
start = today - timedelta(weeks=past)
end = today + timedelta(weeks=future)

items=[]
for c in cfg["classes"]:
    h,m = parse_time(c["start"])
    items.append(ClassItem(
        date=date.fromisoformat(c["date"]),
        start_h=h, start_m=m,
        duration_min=int(c["duration_min"]),
        title=c.get("title",""),
        location=c.get("location",""),
        instructor=c.get("instructor",""),
        notes=c.get("notes",""),
        content=[x for x in c.get("content",[]) if isinstance(x,str)]
    ))

lines=["BEGIN:VCALENDAR","VERSION:2.0","PRODID:-//Dance Schedule//CN//EN","CALSCALE:GREGORIAN"]
for it in items:
    if not (start <= it.date <= end): continue
    st = datetime(it.date.year,it.date.month,it.date.day,it.start_h,it.start_m,tzinfo=tz)
    et = st + timedelta(minutes=it.duration_min)
    uid = uid_for(f"{it.date}|{it.start_h}:{it.start_m}|{it.title}|{it.location}")
    desc=[]
    if it.instructor: desc.append(f"教练：{it.instructor}")
    if it.content: desc.append("内容："+" / ".join(it.content))
    if it.notes: desc.append(it.notes)
    ve=[
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTART;TZID=Asia/Shanghai:{st.strftime('%Y%m%dT%H%M%S')}",
        f"DTEND;TZID=Asia/Shanghai:{et.strftime('%Y%m%dT%H%M%S')}",
        f"SUMMARY:{ics_escape(it.title)}",
        f"LOCATION:{ics_escape(it.location)}" if it.location else None,
        f"DESCRIPTION:{ics_escape(chr(10).join(desc))}",
        "END:VEVENT"
    ]
    ve = [x for x in ve if x is not None]
    for l in ve: lines.extend(fold(l))
lines.append("END:VCALENDAR")

out = os.path.join(root,"docs","schedule.ics")
os.makedirs(os.path.dirname(out),exist_ok=True)
open(out,"w",encoding="utf-8").write("\n".join(lines))
print("generated schedule.ics")
