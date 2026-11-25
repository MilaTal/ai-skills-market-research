# -*- coding: utf-8 -*-
"""Проверка сбора свежей информации: в таблицах только строки со ссылкой и датой внутри окна.

  python check_window.py <сбор.md> --start дд.мм.гггг [--today дд.мм.гггг]
Дата строки берётся из колонки «дата», а если её нет — самая поздняя дата в строке.
Формат даты: дд.мм.гггг или мм.гггг (месяц засчитывается, если он не раньше месяца начала окна —
такие строки помечаются «только месяц»). Таблицы под заголовками «Дата не установлена» и «Источники»
не проверяются. Код выхода 1, если есть строка без ссылки, без даты, раньше окна или позже даты запуска.
"""
import argparse
import datetime as dt
import re
import sys
from pathlib import Path

LINK = re.compile(r"https?://|\]\(|\b[\w-]+\.(ru|com|org|io|ai|net|gov|рф|su|vc|de|co|tech|pro)\b", re.I)
FULL = re.compile(r"\b(\d{2})\.(\d{2})\.(\d{4})\b")
MONTH = re.compile(r"(?<![\d.])(\d{2})\.(\d{4})\b")
SEP = re.compile(r"^\|\s*:?-{2,}")
SKIP_SECTION = re.compile(r"дата не установлена|источник", re.I)
MATRIX = re.compile(r"^(ии-)?функция", re.I)  # матрица «функция × продукт» — без дат и ссылок по строкам


def parse(s: str):
    """(дата, только_месяц) — самая поздняя дата в тексте или None."""
    out = [(dt.date(int(y), int(m), int(d)), False) for d, m, y in FULL.findall(s)]
    rest = FULL.sub(" ", s)
    for m, y in MONTH.findall(rest):
        if 1 <= int(m) <= 12:
            out.append((dt.date(int(y), int(m), 1), True))
    return max(out, key=lambda x: x[0]) if out else None


def d(s: str) -> dt.date:
    dd, mm, yy = map(int, s.split("."))
    return dt.date(yy, mm, dd)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file", type=Path)
    ap.add_argument("--start", required=True)
    ap.add_argument("--today", default=dt.date.today().strftime("%d.%m.%Y"))
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    start, today = d(a.start), d(a.today)
    section, head, date_col = "", None, None
    total = ok = month_only = 0
    bad = {"без ссылки": [], "без даты": [], "раньше окна": [], "позже даты запуска": []}
    for line in a.file.read_text(encoding="utf-8-sig").splitlines():
        s = line.strip()
        if s.startswith("#"):
            section = s
        if not s.startswith("|"):
            head = None
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if head is None:
            head = [c.lower() for c in cells]
            date_col = next((i for i, c in enumerate(head) if c.startswith("дата")), None)
            seen_link = False
            continue
        if SEP.match(s) or SKIP_SECTION.search(section) or MATRIX.match(head[0]):
            continue
        total += 1
        short = s[:100]
        # «там же» наследует ссылку строки выше в той же таблице
        linked = bool(LINK.search(s)) or (seen_link and re.search(r"\b(там|то) же\b", s, re.I) is not None)
        seen_link = seen_link or bool(LINK.search(s))
        if not linked:
            bad["без ссылки"].append(short)
        src = cells[date_col] if date_col is not None and date_col < len(cells) else s
        got = parse(src) or parse(s)
        if not got:
            bad["без даты"].append(short)
            continue
        when, only_month = got
        if only_month:
            month_only += 1
            in_window = (when.year, when.month) >= (start.year, start.month)
        else:
            in_window = when >= start
        if not in_window:
            bad["раньше окна"].append(f"{when:%d.%m.%Y} {short}")
        elif when > today:
            bad["позже даты запуска"].append(f"{when:%d.%m.%Y} {short}")
        elif linked:
            ok += 1
    print(f"{a.file.name}: окно {start:%d.%m.%Y} — {today:%d.%m.%Y}; строк {total}, годных {ok}, "
          + ", ".join(f"{k} {len(v)}" for k, v in bad.items()) + f"; с точностью до месяца {month_only}")
    for k, v in bad.items():
        for x in v[:10]:
            print(f"   {k}: {x}")
    sys.exit(1 if any(bad.values()) else 0)


if __name__ == "__main__":
    main()
