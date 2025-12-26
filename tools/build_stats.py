from __future__ import annotations

import csv
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo

import yaml


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


def extract_bodyjam_items(entry: dict) -> list[str]:
    items: list[str] = []

    bj = entry.get("bodyjam")
    if isinstance(bj, dict):
        for part in ("upper", "lower"):
            p = bj.get(part)
            if not isinstance(p, dict):
                continue
            for key in ("main", "mix"):
                arr = p.get(key, [])
                if isinstance(arr, list):
                    for x in arr:
                        norm = normalize_bj_item(x)
                        if norm:
                            items.append(norm)

    if not items and isinstance(entry.get("content"), list):
        for x in entry["content"]:
            norm = normalize_bj_item(x)
            if norm:
                items.append(norm)

    def sort_key(name: str):
        tail = name.split(" ", 1)[1]
        m = re.match(r"(\d+)", tail)
        return int(m.group(1)) if m else 9999

    return sorted(set(items), key=sort_key)


@dataclass
class StatRow:
    name: str
    count: int
    last_seen: date


def main():
    root = os.path.dirname(os.path.dirname(__file__))
    yaml_path = os.path.join(root, "schedule.yaml")

    with open(yaml_path, "r", encoding="utf-8") as f:
        obj = yaml.safe_load(f) or {}

    tzname = (obj.get("timezone") or "Asia/Shanghai").strip()
    tz = ZoneInfo(tzname)

    today = datetime.now(tz).date()
    start_date = today - timedelta(days=365)

    classes = obj.get("classes") or []

    counts: dict[str, int] = {}
    last_seen: dict[str, date] = {}

    for c in classes:
        if not isinstance(c, dict):
            continue
        if str(c.get("title", "")).strip() != "BodyJam":
            continue

        d = date.fromisoformat(str(c.get("date")))
        if not (start_date <= d <= today):
            continue

        items = extract_bodyjam_items(c)
        if not items:
            continue

        for item in items:
            counts[item] = counts.get(item, 0) + 1
            if item not in last_seen or d > last_seen[item]:
                last_seen[item] = d

    rows: list[StatRow] = [StatRow(k, v, last_seen[k]) for k, v in counts.items()]

    def sort_key(r: StatRow):
        m = re.search(r"BodyJam\s+(\d+)", r.name)
        num = int(m.group(1)) if m else 9999
        return (r.count, r.last_seen, num)

    rows.sort(key=sort_key)

    out_dir = os.path.join(root, "docs", "stats")
    os.makedirs(out_dir, exist_ok=True)

    year = today.year
    out_md = os.path.join(out_dir, f"bodyjam_rarest_{year}.md")
    out_csv = os.path.join(out_dir, f"bodyjam_rarest_{year}.csv")
    out_json = os.path.join(out_dir, f"bodyjam_rarest_{year}.json")

    with open(out_md, "w", encoding="utf-8", newline="\n") as f:
        f.write("# BodyJam 内容稀缺榜（过去一年）\n\n")
        f.write(f"- 统计区间：{start_date.isoformat()} ～ {today.isoformat()}\n")
        f.write("- 排序规则：出现次数最少优先；若次数相同，越久没出现优先\n\n")
        f.write("| 排名 | 内容 | 出现次数 | 最近出现 |\n")
        f.write("|---:|---|---:|---|\n")
        for i, r in enumerate(rows, start=1):
            f.write(f"| {i} | {r.name} | {r.count} | {r.last_seen.isoformat()} |\n")

        f.write("\n## Top 10（最稀缺优先）\n\n")
        for r in rows[:10]:
            days_ago = (today - r.last_seen).days
            f.write(f"- **{r.name}**：{r.count} 次；最近出现 {r.last_seen.isoformat()}（{days_ago} 天前）\n")

    with open(out_csv, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["rank", "item", "count", "last_seen"])
        for i, r in enumerate(rows, start=1):
            w.writerow([i, r.name, r.count, r.last_seen.isoformat()])

    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(
            {
                "range": {"start": start_date.isoformat(), "end": today.isoformat()},
                "timezone": tzname,
                "rows": [
                    {
                        "rank": i,
                        "item": r.name,
                        "count": r.count,
                        "last_seen": r.last_seen.isoformat(),
                        "days_since_last_seen": (today - r.last_seen).days,
                    }
                    for i, r in enumerate(rows, start=1)
                ],
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    print("Generated stats in docs/stats/")


if __name__ == "__main__":
    main()
