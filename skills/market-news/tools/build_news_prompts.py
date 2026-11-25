# -*- coding: utf-8 -*-
"""Задания агентам для сбора только свежей информации по направлениям продуктового поиска.

  python build_news_prompts.py --show                         направления реестра (для вопроса оператору)
  python build_news_prompts.py --months 3 --dirs P1,P3 --out plan.json
      --months   окно: столько календарных месяцев до даты запуска (обязательно — спрашивается у оператора)
      --dirs     номера направлений; по умолчанию все со status: active
      --today    дата запуска дд.мм.гггг (по умолчанию сегодня)
      --budget   запросов WebSearch на агента (по умолчанию 20)
Выход: JSON-список {id, description, start, today, save_as, prompt}. Окно печатается — сверить с оператором.
"""
import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from string import Template

import yaml

TPL = Path(__file__).resolve().parent.parent / "templates" / "direction.md"
ROOT = Path.home() / "Documents" / "ITMO_research_info" / "Рынок и темы Copilot"
REGISTRY = ROOT / "00 Реестры и требования" / "Реестр направлений продуктового поиска.yaml"
BASE = ROOT / "04 Продукты — отмеченные направления"
NEWS = ROOT / "05 Свежее"


def minus_months(d: dt.date, n: int) -> dt.date:
    y, m = divmod(d.year * 12 + d.month - 1 - n, 12)
    m += 1
    last = (dt.date(y + (m == 12), m % 12 + 1, 1) - dt.timedelta(days=1)).day
    return dt.date(y, m, min(d.day, last))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--registry", type=Path, default=REGISTRY)
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--months", type=int)
    ap.add_argument("--dirs")
    ap.add_argument("--today", default=dt.date.today().strftime("%d.%m.%Y"))
    ap.add_argument("--budget", type=int, default=20)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    dirs = yaml.safe_load(a.registry.read_text(encoding="utf-8"))["directions"]
    if a.show:
        for d in dirs:
            print(f"{d['id']}. [{d['status']}] {d['short']} — темы {d.get('topics')}\n   {d['coverage']}")
        return
    if not a.months or a.months < 1:
        sys.exit("нужен --months ≥ 1: окно задаёт оператор")
    dd, mm, yy = map(int, a.today.split("."))
    today = dt.date(yy, mm, dd)
    start = minus_months(today, a.months)
    if a.dirs:
        want = a.dirs.split(",")
        sel = [d for d in dirs if d["id"] in want]
        if missing := set(want) - {d["id"] for d in sel}:
            sys.exit(f"нет в реестре: {sorted(missing)}")
    else:
        sel = [d for d in dirs if d["status"] == "active"]
    tpl = Template(TPL.read_text(encoding="utf-8"))
    f = lambda x: x.strftime("%d.%m.%Y")
    plan = []
    for d in sel:
        known = [BASE / d["report"]] + sorted(NEWS.glob(f"* {d['id']} *.md"))
        known_txt = "\n".join(f"- {p}" + ("" if p.exists() else " (файла нет — пропусти)") for p in known)
        plan.append({"id": d["id"], "description": f"Свежее {d['id']}: {d['short']}"[:60],
                     "start": f(start), "today": f(today),
                     "save_as": str(NEWS / f"{today:%Y-%m-%d} {d['id']} {d['short']}.md"),
                     "prompt": tpl.substitute(today=f(today), start=f(start), months=a.months, title=d["short"],
                                              coverage=d["coverage"], seeds=d.get("seeds", ""), known=known_txt,
                                              budget=a.budget)})
    print(f"окно: {f(start)} — {f(today)} ({a.months} мес.), направлений: {len(plan)}, "
          f"запросов поиска до {len(plan) * a.budget}")
    text = json.dumps(plan, ensure_ascii=False, indent=1)
    if a.out:
        a.out.write_text(text, encoding="utf-8")
        for p in plan:
            print(f"  {p['description']} → {Path(p['save_as']).name}")
    else:
        print(text)


if __name__ == "__main__":
    main()
