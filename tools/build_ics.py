from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo

import yaml


def ics_escape(s: str) -> str:
    s = s.replace("\\", "\\\\")
    s = s.replace(";", "\\;").replace(",", "\\,")
    s = s.replace("\n", "\\n")
    return s


def fold_ics_line(line: str, limit: int = 75) -> list[str]:
    if len(line) <= limit:
        return [line]
    out = [line[:limit]]
    rest = line[limit:]
    while rest:
        out.append(" " + rest[:limit - 1])
        rest = rest[limit - 1:]
    return out


def stable_uid(key: str, domain: str = "dance-schedule") -> str:
    h = hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]
    return f"{h}@{domain}"


def parse_hhmm(t: str) -> tuple[int, int]:
    m = re.fullmatch(r"(\d{1,2}):(\d{2})", t.strip())
    if not m:
        raise ValueError(f"Invalid time: {t}")
    hh, mm = int(m.group(1)), int(m.group(2))
    if not (0 <= hh <= 23 and 0 <= mm <= 59):
        raise ValueError(f"Invalid time: {t}")
    return hh, mm


def parse_yyyy_mm_dd(d: str) -> date:
    return date.fromisoformat(d.strip())


def vtimezone_asia_shanghai() -> list[str]:
    return [
        "BEGIN:VTIMEZONE",
        "TZID:Asia/Shanghai",
        "BEGIN:STANDARD",
        "TZOFFSETFROM:+0800",
        "TZOFFSETTO:+0800",
        "TZNAME:CST",
        "DTSTART:19700101T000000",
        "END:STANDARD",
        "END:VTIMEZONE",
    ]


def normalize_bj_item(s: str) -> str | None:
    if not isinstance(s, str):
        return None
    raw = s.strip()
    if not raw:
        return None

    raw2 = re.sub(r"^Body\s*Jam\s*", "", raw, flags=re.IGNORECASE).strip()
    raw2 = raw2.replace(" ", "")

    m = re.fullmatch(r"(\d{1,3})([A-Za-z]+)?", raw2)
    if not m:
        return re.sub(r"^Body\s*Jam", "BodyJam", raw, flags=re.IGNORECASE).strip()

    num = int(m.group(1))
    suf = m.group(2) or ""
    if suf:
        return f"BodyJam {num} {suf}"
    return f"BodyJam {num}"


def format_bodyjam_for_description(bj: dict) -> str:
    if not isinstance(bj, dict):
        return ""

    def fmt_part(label: str, p: dict) -> str | None:
        if not isinstance(p, dict):
            return None
        main = [normalize_bj_item(x) for x in (
            p.get("main") or []) if isinstance(x, str)]
        main = [x for x in main if x]
        if not main:
            return None

        mix = [normalize_bj_item(x) for x in (
            p.get("mix") or []) if isinstance(x, str)]
        mix = [x for x in mix if x]

        main_txt = " / ".join(main)
        if mix:
            mix_txt = " / ".join(mix)
            return f"{label}：{main_txt}（mix：{mix_txt}）"
        return f"{label}：{main_txt}"

    lines: list[str] = []
    up = fmt_part("上", bj.get("upper") or {})
    lo = fmt_part("下", bj.get("lower") or {})
    if up:
        lines.append(up)
    if lo:
        lines.append(lo)
    return "\n".join(lines).strip()


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
    bodyjam: dict | None


def load_yaml(path: str) -> tuple[str, int, int, list[ClassItem]]:
    with open(path, "r", encoding="utf-8") as f:
        obj = yaml.safe_load(f) or {}

    tzname = (obj.get("timezone") or "Asia/Shanghai").strip()
    window = obj.get("window") or {}
    past_weeks = int(window.get("past_weeks", 26))
    future_weeks = int(window.get("future_weeks", 1))

    items: list[ClassItem] = []
    for c in obj.get("classes") or []:
        if not isinstance(c, dict):
            continue
        d = parse_yyyy_mm_dd(c["date"])
        hh, mm = parse_hhmm(c["start"])

        content = [
            str(x).strip()
            for x in (c.get("content") or [])
            if isinstance(x, str) and x.strip()
        ]

        bj = c.get("bodyjam")
        if not isinstance(bj, dict):
            bj = None

        items.append(
            ClassItem(
                date=d,
                start_h=hh,
                start_m=mm,
                duration_min=int(c["duration_min"]),
                title=str(c.get("title", "")).strip(),
                location=str(c.get("location", "")).strip(),
                instructor=str(c.get("instructor", "")).strip(),
                notes=str(c.get("notes", "")).strip(),
                content=content,
                bodyjam=bj,
            )
        )

    return tzname, past_weeks, future_weeks, items


def build_ics(tzname: str, past_weeks: int, future_weeks: int, items: list[ClassItem], out_path: str) -> None:
    tz = ZoneInfo(tzname)
    today = datetime.now(tz).date()
    start_date = today - timedelta(weeks=past_weeks)
    end_date = today + timedelta(weeks=future_weeks)

    now_utc = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

    lines: list[str] = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Dance Schedule//CN//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]

    if tzname == "Asia/Shanghai":
        lines += vtimezone_asia_shanghai()

    items_in_window = [it for it in items if start_date <= it.date <= end_date]
    items_in_window.sort(key=lambda x: (
        x.date, x.start_h, x.start_m, x.title, x.location))

    for it in items_in_window:
        start_dt = datetime(it.date.year, it.date.month,
                            it.date.day, it.start_h, it.start_m, tzinfo=tz)
        end_dt = start_dt + timedelta(minutes=it.duration_min)

        def fmt_local(dt: datetime) -> str:
            return dt.strftime("%Y%m%dT%H%M%S")

        uid_key = f"{it.date.isoformat()}|{it.start_h:02d}:{it.start_m:02d}|{it.title}|{it.location}"
        uid = stable_uid(uid_key)

        desc_parts: list[str] = []
        if it.instructor:
            desc_parts.append(f"教练：{it.instructor}")

        if it.bodyjam:
            bj_text = format_bodyjam_for_description(it.bodyjam)
            if bj_text:
                desc_parts.append(bj_text)
        elif it.content:
            desc_parts.append("内容：" + " / ".join(it.content))

        if it.notes:
            desc_parts.append(it.notes)

        description = None
        if desc_parts:
            description = ics_escape("\n".join(desc_parts))

        ve: list[str | None] = [
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{now_utc}",
            f"DTSTART;TZID={tzname}:{fmt_local(start_dt)}",
            f"DTEND;TZID={tzname}:{fmt_local(end_dt)}",
            f"SUMMARY:{ics_escape(it.title)}",
            f"LOCATION:{ics_escape(it.location)}" if it.location else None,
            f"DESCRIPTION:{description}" if description else None,
            "END:VEVENT",
        ]
        for l in [x for x in ve if x is not None]:
            lines += fold_ics_line(l)

    lines.append("END:VCALENDAR")

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")


def main():
    root = os.path.dirname(os.path.dirname(__file__))
    yaml_path = os.path.join(root, "schedule.yaml")
    out_latest = os.path.join(root, "docs", "schedule.ics")
    tzname, past_weeks, future_weeks, items = load_yaml(yaml_path)
    build_ics(tzname, past_weeks, future_weeks, items, out_latest)
    print(f"Generated: {out_latest}")


if __name__ == "__main__":
    main()
