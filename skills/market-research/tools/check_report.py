# -*- coding: utf-8 -*-
"""Проверка отчёта поиска по рынку: у каждой строки таблицы — ссылка и дата.

  python check_report.py <отчёт.md> [<отчёт.md> ...] [--stale-year 2024]
Считает строки таблиц (кроме заголовков, разделителей и таблиц расчёта оценки),
строки без ссылки, без даты и со старым годом без пометки «устаревает».
Код выхода 1, если есть строки без ссылки — такой отчёт не готов.
"""
import argparse
import re
import sys
from pathlib import Path

# ссылка: адрес, markdown-ссылка, домен или отсылка сводки к строке своего отчёта («отчёт 04, строка 34»)
LINK = re.compile(r"https?://|\]\(|\b[\w-]+\.(ru|com|org|io|ai|net|gov|рф|su|vc)\b|отч[её]т\w*\s+\d{2}", re.I)
DATE = re.compile(r"\b\d{2}\.\d{2}\.\d{4}\b|\b(19|20)\d{2}\b")
YEAR = re.compile(r"\b(20\d{2})\b")
SEP = re.compile(r"^\|\s*:?-{2,}")
# таблицы, где ссылка не обязательна в каждой строке: расчёт оценки, веса, матрица «функция × продукт»
SKIP_HEAD = re.compile(r"критерий|вес\b|балл|^\|\s*функция", re.I)


def tables(text: str):
    """Таблицы с последней непустой строкой текста перед ними (там часто стоит общий источник таблицы)."""
    head, rows, intro, last = None, [], "", ""
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("|"):
            if head is None:
                head, intro = s, last
            elif not SEP.match(s):
                rows.append(s)
        else:
            if head is not None:
                yield head, rows, intro
            head, rows = None, []
            if s:
                last = s
    if head is not None:
        yield head, rows, intro


def check(path: Path, stale_year: int) -> tuple[int, int]:
    text = path.read_text(encoding="utf-8-sig")
    total = no_link = no_date = stale = 0
    bad = []
    for head, rows, intro in tables(text):
        if SKIP_HEAD.search(head):
            continue
        # общий источник в строке над таблицей засчитывается, только если у таблицы нет своей колонки источника
        seen_link = bool(LINK.search(intro)) and not re.search(r"источник|ссылк", head, re.I)
        table_source = seen_link
        for r in rows:
            total += 1
            # «там же» наследует ссылку строки выше — засчитывается, если выше в таблице ссылка была
            if LINK.search(r):
                seen_link = True
            elif not (table_source or (seen_link and re.search(r"\b(там|то) же\b", r, re.I))):
                no_link += 1
                bad.append(r[:110])
            if not DATE.search(r):
                no_date += 1
            years = [int(y) for y in YEAR.findall(r)]
            if years and max(years) < stale_year and "устаревает" not in r.lower():
                stale += 1
    print(f"{path.name}: строк {total}, без ссылки {no_link}, без даты {no_date}, старше {stale_year} без пометки {stale}")
    for b in bad[:10]:
        print(f"   без ссылки: {b}")
    return total, no_link


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument("--stale-year", type=int, default=2024)
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    worst = 0
    for f in a.files:
        _, nl = check(f, a.stale_year)
        worst = max(worst, nl)
    sys.exit(1 if worst else 0)


if __name__ == "__main__":
    main()
