from __future__ import annotations

import json
import os
import re
import shutil
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import yaml


def normalize_bj_item(s: str) -> str | None:
    if not isinstance(s, str):
        return None
    raw = s.strip()
    if not raw:
        return None
    raw2 = re.sub(r"^Body\s*Jam\s*", "", raw, flags=re.IGNORECASE).strip()
    raw2 = raw2.replace(" ", "")  # 73 Bonus -> 73Bonus
    m = re.fullmatch(r"(\d{1,3})([A-Za-z]+)?", raw2)
    if not m:
        return re.sub(r"^Body\s*Jam", "BodyJam", raw, flags=re.IGNORECASE).strip()
    num = int(m.group(1))
    suf = m.group(2) or ""
    return f"BodyJam {num} {suf}".strip()


def pick_list(x) -> list[str]:
    if isinstance(x, list):
        return [str(i).strip() for i in x if isinstance(i, (str, int, float)) and str(i).strip()]
    return []


def format_bodyjam_lines(bj: dict | None) -> dict:
    """
    Return:
      {
        "upper_main": ["BodyJam 104", ...],
        "upper_mix":  ["BodyJam 114", ...],
        "lower_main": ["BodyJam 111", ...],
        "lower_mix":  ["BodyJam 73 Bonus", ...],
        "upper_text": "上：BodyJam 104（mix：BodyJam 114）",
        "lower_text": "下：BodyJam 111（mix：BodyJam 73 Bonus）"
      }
    """
    out = {
        "upper_main": [],
        "upper_mix": [],
        "lower_main": [],
        "lower_mix": [],
        "upper_text": "",
        "lower_text": "",
    }
    if not isinstance(bj, dict):
        return out

    upper = bj.get("upper") if isinstance(bj.get("upper"), dict) else {}
    lower = bj.get("lower") if isinstance(bj.get("lower"), dict) else {}

    um = [normalize_bj_item(i) for i in pick_list(upper.get("main"))]
    ux = [normalize_bj_item(i) for i in pick_list(upper.get("mix"))]
    lm = [normalize_bj_item(i) for i in pick_list(lower.get("main"))]
    lx = [normalize_bj_item(i) for i in pick_list(lower.get("mix"))]

    out["upper_main"] = [x for x in um if x]
    out["upper_mix"] = [x for x in ux if x]
    out["lower_main"] = [x for x in lm if x]
    out["lower_mix"] = [x for x in lx if x]

    def mk_text(prefix: str, main: list[str], mix: list[str]) -> str:
        if not main:
            return ""
        if mix:
            return f"{prefix}：{' / '.join(main)}（mix：{' / '.join(mix)}）"
        return f"{prefix}：{' / '.join(main)}"

    out["upper_text"] = mk_text("上", out["upper_main"], out["upper_mix"])
    out["lower_text"] = mk_text("下", out["lower_main"], out["lower_mix"])
    return out


def find_latest_stats_json(stats_dir: str) -> str | None:
    if not os.path.isdir(stats_dir):
        return None
    items = []
    for fn in os.listdir(stats_dir):
        m = re.fullmatch(r"bodyjam_rarest_(\d{4})\.json", fn)
        if m:
            items.append((int(m.group(1)), os.path.join(stats_dir, fn)))
    if not items:
        return None
    items.sort(key=lambda x: x[0], reverse=True)
    return items[0][1]


def main():
    root = os.path.dirname(os.path.dirname(__file__))
    docs = os.path.join(root, "docs")

    with open(os.path.join(root, "schedule.yaml"), "r", encoding="utf-8") as f:
        obj = yaml.safe_load(f) or {}

    tzname = str(obj.get("timezone", "Asia/Shanghai"))
    tz = ZoneInfo(tzname)

    today = datetime.now(tz).date()
    start = today - timedelta(days=30)
    end = today + timedelta(days=7)

    events = []
    for c in obj.get("classes") or []:
        if not isinstance(c, dict):
            continue
        d = date.fromisoformat(str(c.get("date")))
        if not (start <= d <= end):
            continue

        bj = c.get("bodyjam") if isinstance(c.get("bodyjam"), dict) else None
        bj_lines = format_bodyjam_lines(bj)

        events.append({
            "date": d.isoformat(),
            "start": str(c.get("start", "")).strip(),
            "duration_min": int(c.get("duration_min", 0) or 0),
            "title": str(c.get("title", "")).strip(),
            "location": str(c.get("location", "")).strip(),
            "instructor": str(c.get("instructor", "")).strip(),
            "bodyjam": bj,                 # 原始结构（保留）
            "bodyjam_lines": bj_lines,     # 供前端直观展示（新增）
        })

    events.sort(key=lambda e: (
        e["date"], e["start"], e["title"], e["location"]))

    os.makedirs(docs, exist_ok=True)
    with open(os.path.join(docs, "schedule.json"), "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": datetime.now(tz).isoformat(timespec="seconds"),
            "timezone": tzname,
            "window": {"start_date": start.isoformat(), "end_date": end.isoformat()},
            "events": events,
        }, f, ensure_ascii=False, indent=2)

    stats_dir = os.path.join(docs, "stats")
    latest = find_latest_stats_json(stats_dir)
    if latest:
        shutil.copyfile(latest, os.path.join(
            stats_dir, "bodyjam_rarest_latest.json"))


if __name__ == "__main__":
    main()
