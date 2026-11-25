# -*- coding: utf-8 -*-
"""Задания агентам для поиска по рынку — из реестра тем и шаблонов скилла.

  python build_prompts.py --show                      темы реестра (для вопроса оператору)
  python build_prompts.py --topics 1,2,8 --waves 1,2,3 --out plan.json
      --topics  номера тем; по умолчанию все со status: active
      --waves   1 — отраслевое, 2 — финансовая привлекательность, 3 — инвесторы и закупки
      --months  стартовая точка: материалы не ранее стольких месяцев до даты запуска (обязательно, спрашивается у оператора)
      --copilot добавить в волну 1 заготовки по шагам WP01–WP12
      --registry путь к реестру (по умолчанию Documents\\ITMO_research_info\\Рынок и темы Copilot\\00 Реестры и требования\\Реестр тем поиска.yaml)
Выход: JSON-список {wave, description, save_as, prompt}. save_as — путь отчёта относительно папки поиска.
"""
import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from string import Template

import yaml

HERE = Path(__file__).resolve().parent.parent / "templates"
DEFAULT_REGISTRY = Path.home() / "Documents" / "ITMO_research_info" / "Рынок и темы Copilot" / "00 Реестры и требования" / "Реестр тем поиска.yaml"

COPILOT_EXTRA = ("\n5а. Заготовки по шагам проекта WP01–WP12 (задача и ценность, As-Is, граница автоматизации, To-Be и KPI, "
                 "архитектура, человек в контуре, устойчивость, прототип, среда и безопасность, проверка качества, атаки, запуск): "
                 "по 1–2 обезличенных примера ответа на шаг, 3–6 строк, числа только из источников или «оценка».")


WINDOW = ("СТАРТОВАЯ ТОЧКА: учитывать только материалы, опубликованные, и события, произошедшие не ранее {start} "
          "(окно {months} мес. до даты запуска {today}). Более ранние не собирать — ни в таблицы, ни в выводы, "
          "даже если они важны. Если раздел отчёта требует данных раньше окна (например, приток капитала по годам "
          "или «последние 3 года»), пиши «вне окна» и не заполняй. Материал без даты не включать — перечислить "
          "отдельно в разделе «Дата не установлена». Дата в каждой строке таблиц — дд.мм.гггг или мм.гггг.\n\n")


def minus_months(d: dt.date, n: int) -> dt.date:
    y, m = divmod(d.year * 12 + d.month - 1 - n, 12)
    m += 1
    last = (dt.date(y + (m == 12), m % 12 + 1, 1) - dt.timedelta(days=1)).day
    return dt.date(y, m, min(d.day, last))


def tpl(name: str) -> Template:
    return Template((HERE / f"{name}.md").read_text(encoding="utf-8"))


def load(registry: Path) -> list[dict]:
    return yaml.safe_load(registry.read_text(encoding="utf-8"))["topics"]


def topics_list(ts: list[dict]) -> str:
    return "\n".join(f"{t['id']}) {t['title']} — {t['coverage']}" for t in ts)


def short(t: dict) -> str:
    return t.get("short") or t["title"][:50].rsplit(" ", 1)[0].rstrip(" ,—:")


def chunks(xs, n):
    return [xs[i:i + n] for i in range(0, len(xs), n)]


def build(ts: list[dict], waves: set[int], date: str, copilot: bool, start: str, months: int) -> list[dict]:
    common_vars = {"date": date, "period": f"{start} — {date}", "stale_year": start[-4:], "nmck_max": "10–15"}
    tl = topics_list(ts)
    common = tpl("wave3_common").substitute(topics_list=tl, **common_vars)
    out = []
    if 1 in waves:
        for t in ts:
            out.append({"wave": 1, "description": f"Отрасль: тема {t['id']}",
                        "save_as": f"{t['id']:02d} {short(t)}.md",
                        "prompt": tpl("wave1_topic").substitute(title=t["title"], coverage=t["coverage"],
                                                                extra=COPILOT_EXTRA if copilot else "", **common_vars)})
    if 2 in waves:
        for t in ts:
            out.append({"wave": 2, "description": f"Привлекательность, мир: тема {t['id']}",
                        "save_as": f"Финансовая привлекательность/{t['id']:02d} {short(t)} — мир.md",
                        "prompt": tpl("wave2_world").substitute(title=t["title"], coverage=t["coverage"], **common_vars)})
        for part in chunks(ts, 4):
            ids = ",".join(str(t["id"]) for t in part)
            out.append({"wave": 2, "description": f"Привлекательность, Россия: темы {ids}",
                        "save_as": f"Финансовая привлекательность/Россия — темы {ids}.md",
                        "prompt": tpl("wave2_russia").substitute(topics_list=topics_list(part), **common_vars)})
    if 3 in waves:
        keys = "\n".join(f"{t['id']}) " + ", ".join(f"«{k}»" for k in t.get("tender_keys", [])) for t in ts)
        for name, title, fname in [("wave3_angels", "Бизнес-ангелы РФ", "01 Россия — бизнес-ангелы.md"),
                                   ("wave3_funds", "Фонды и господдержка РФ", "02 Россия — фонды, акселераторы и господдержка.md"),
                                   ("wave3_requests", "Запросы инвесторов РФ", "03 Россия — запросы инвесторов и корпораций.md"),
                                   ("wave3_procurement", "Госзакупки РФ", "04 Россия — госзакупки небольших ИИ-разработок.md"),
                                   ("wave3_world", "Инвесторы мира", "05 Мир — инвесторы и программы.md")]:
            out.append({"wave": 3, "description": title, "save_as": f"Инвесторы и закупки/{fname}",
                        "prompt": tpl(name).substitute(common=common, keys_list=keys, **common_vars)})
    window = WINDOW.format(start=start, months=months, today=date)
    for p in out:
        p["prompt"] = window + p["prompt"]
        p["start"] = start
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--topics")
    ap.add_argument("--waves", default="1,2,3")
    ap.add_argument("--date", default=dt.date.today().strftime("%d.%m.%Y"))
    ap.add_argument("--months", type=int)
    ap.add_argument("--copilot", action="store_true")
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    all_t = load(a.registry)
    if a.show:
        for t in all_t:
            mark = "" if t.get("coverage_confirmed", True) else "  [охват не подтверждён]"
            print(f"{t['id']}. [{t['status']}] {t['title']}{mark}\n   охват: {t['coverage']}")
        return
    if a.topics:
        want = [int(x) for x in a.topics.split(",")]
        ts = [t for t in all_t if t["id"] in want]
        missing = set(want) - {t["id"] for t in ts}
        if missing:
            sys.exit(f"нет в реестре: {sorted(missing)}")
    else:
        ts = [t for t in all_t if t["status"] == "active"]
    if not a.months or a.months < 1:
        sys.exit("нужен --months ≥ 1: стартовую точку задаёт оператор")
    dd, mm, yy = map(int, a.date.split("."))
    start = minus_months(dt.date(yy, mm, dd), a.months).strftime("%d.%m.%Y")
    print(f"стартовая точка: не ранее {start} ({a.months} мес. до {a.date})")
    plan = build(ts, {int(w) for w in a.waves.split(",")}, a.date, a.copilot, start, a.months)
    text = json.dumps(plan, ensure_ascii=False, indent=1)
    if a.out:
        a.out.write_text(text, encoding="utf-8")
        print(f"заданий: {len(plan)} → {a.out}")
        for p in plan:
            print(f"  волна {p['wave']}: {p['description']} → {p['save_as']}")
    else:
        print(text)


if __name__ == "__main__":
    main()
